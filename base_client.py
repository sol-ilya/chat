import socket
import threading
import queue
import signal
import sys
import os


from message import *

class BaseChatClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.username = ""
        
        self.exit_code = 1
        signal.signal(signal.SIGTERM, self.terminate)
        
        self.queue = queue.Queue()
        
        # signal.signal(signal.SIGINT, self.terminate)
    
    def start(self):
        self.connect_to_server(self.host, self.port)
        self.login()
        threading.Thread(target=self.receiving_loop, daemon=True).start()

    def connect_to_server(self, host, port):
        self.opened = False
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            #self.sock.settimeout(3)
            self.sock.connect((host, port))
            self.opened = True
        except Exception as e:
            self.abort(f'Cannot connect to the server: {e}')

    def login(self):
        self.askusername()
        while True:
            if not self.username:
                self.send_message(self.username)
                self.quit()
            self.send_message(self.username)
            t, ok = receive_message(self.sock, throw_empty=False)
            if t == MsgType.empty:
                self.abort('Cannot connect to the server')
            if ok == "0":
                break
            elif ok == "1":
                self.askusername(is_used = True)
            elif ok == "2":
                self.askusername(is_not_valid = True)
            else:
                self.abort('Unexpected message received')

    def __del__(self):
        self.close_connection()

    def askusername(self, is_used = False, is_not_valid = False):
        raise NotImplementedError("This method should be overridden in subclasses")

    
    class StopReceiving(Exception):
        pass
    
    class InvalidMessageType(Exception):
        pass
    
    def receiving_loop(self):
        while True:
            try:
                msg_type, message = receive_message(self.sock)
                self.handle_message(msg_type, message)
            
            except self.StopReceiving:
                break
                
            except Empty:
                if self.opened:
                    self.abort('Connection lost')
                break

            except Exception as e:
                self.abort(f'Error receiving messages: {e}')
                break

    def handle_message(self, msg_type, message):
        if msg_type == MsgType.chatmsg:
            self.display_message(*message.split('\0'))
        elif msg_type == MsgType.special:
            self.display_special_message(message)
        elif msg_type == MsgType.error:
            self.display_error(message)
        elif msg_type == MsgType.srv_shutdown:
            self.abort('Server was shut down')
            raise self.StopReceiving
        elif msg_type == MsgType.ban:
            self.abort('You are banned')
            raise self.StopReceiving
        elif msg_type == MsgType.usersinfo:
            self.display_usersinfo(message.split('\0'))
        elif msg_type == MsgType.get_file:
            self.handle_file_transfer(message)
        else:
            raise self.InvalidMessageType('Received invalid message')
    
    def handle_file_transfer(self, message):
        if not message:
                self.display_info('Nothing to download')
                self.send_message('')
                return
            
        filelist = message.split('\0')
        fileids = filelist[::2]
        filenames = filelist[1::2]

        if len(fileids) != len(filenames):
            self.display_error('Invalid data received')
            self.send_message('')
            return

        #files = tuple(zip(fileids, filenames))

        index = self.select_file(filenames)

        if index == -1:
            self.send_message('')
            return
        
        fileid, filename = fileids[index], filenames[index]

        self.send_message(fileid)
        
        t, data = receive_byte_message(self.sock)

        if t == MsgType.error:
            self.display_error('File cannot be downloaded')
            return

        filename = self.save_file(default_name=filename)
        
        if not filename:
            return

        try:
            with open(filename, "wb") as f:
                f.write(data)
        except OSError:
            self.display_error('Cannot save file')

    def display_message(self, user, message):
        raise NotImplementedError("This method should be overridden in subclasses")
    
    def display_special_message(self, message):
        raise NotImplementedError("This method should be overridden in subclasses")
    
    def display_error(self, text):
        print(text)

    def display_info(self, text):
        raise NotImplementedError("This method should be overridden in subclasses") 

    def send_message(self, message, msg_type = MsgType.none):
        try:
            send_message(self.sock, message, msg_type)
        except Exception as e:
            self.abort(f'An error occured while sending messages {e}')

    def download_file(self):
        self.send_message("", MsgType.get_file)

    def get_usersinfo(self):
        self.send_message("", MsgType.usersinfo)

    def display_usersinfo(self, users_online):
        answer = "Now online are: \n" + "\n".join(map(lambda s: f'"{s}"', users_online))
        self.display_info(answer)

    def send_chatmessage(self, message):
        if message:
            self.send_message(message, MsgType.chatmsg)

    def upload_file(self):
        filename = self.open_file()
        if not filename:
            return

        basename = os.path.basename(filename)
        self.send_message(basename, MsgType.put_file)

        try:
            with open(filename, "rb") as f:
                data = f.read()
                send_byte_message(self.sock, data)
        except OSError:
            self.send_message("", MsgType.error)
        

    def open_file(self):
        raise NotImplementedError("This method should be overridden in subclasses")

    def save_file(self, default_name):
        raise NotImplementedError("This method should be overridden in subclasses") 

    def select_file(self, filenames): # returns selected index from files
        raise NotImplementedError("This method should be overridden in subclasses") 

    def close_connection(self):
        if self.opened:
            self.opened = False
            try:
                self.sock.shutdown(socket.SHUT_RDWR)  # Закрываем сокет для приема и передачи данных
            except:
                pass  # Игнорируем возможные ошибки при shutdown
            finally:
                self.sock.close()

    def prepare_quit(self):
        pass

    def prepare_abort(self):
        self.prepare_quit()

    def quit(self, signum=None, frame=None):
        self.close_connection()
        self.prepare_quit()
        
        self.exit_code = 0
        os.kill(os.getpid(), signal.SIGTERM)

    def abort(self, text = "", exit_code=1):
        if text:
            self.display_error(text)

        self.close_connection()
        self.prepare_abort()
        self.exit_code = exit_code
        os.kill(os.getpid(), signal.SIGTERM)

    def terminate(self, signum, frame):
        sys.exit(self.exit_code)


class ThreadSafeChatClient(BaseChatClient):
    def __init__(self, host, port):
        self.queue = queue.Queue()
        self._login_done = threading.Event()
        super().__init__(host, port)
    
    
    def main_loop(self):
        self.main_loop_iteration()
        self.schedule(self.main_loop)
    
    def schedule(self, call, now = False):
        raise NotImplementedError("This method should be overridden in subclasses")
    
    def main_loop_iteration(self):
        
        while not self.queue.empty():
            object, func, result_queue, args, kwargs = self.queue.get()
            result = func(object, *args, **kwargs)
            if result_queue:
                result_queue.put(result)

    @staticmethod
    def run_in_main_thread(call):
        def wrapper(self, *args, **kwargs):
            self.queue.put((self, call, None, args, kwargs))
        return wrapper
    
    # @staticmethod
    # def run_in_main_thread2(call):
    #     def wrapper(self, *args, **kwargs):
    #         self.schedule(lambda: call(self, *args, **kwargs), now=True)
    #     return wrapper
    
    @staticmethod
    def run_in_main_thread_with_result(call):
        def wrapper(self, *args, **kwargs):
            result_queue = queue.Queue()
            self.queue.put((self, call, result_queue, args, kwargs))
            return result_queue.get()
        return wrapper
    
    @staticmethod
    def run_in_new_thread(call):
        def wrapper(self, *args, **kwargs):
            thread =  threading.Thread(target=call, args=(self,)+args, kwargs=kwargs, daemon=True)
            thread.start()
            return thread
        return wrapper
    
        
    def start(self):
        self._start()
        self.main_loop()
    
    
    
    @run_in_new_thread
    def _start(self):
        self.connect_to_server(self.host, self.port)
        self.login()
        self.receiving_loop()
    
    @run_in_main_thread_with_result
    def wait_login(self):
        self._login_done.wait()
       
    def on_login_done(self):
        pass
    
    def login(self):
        super().login()
        self.on_login_done()
    
    @run_in_new_thread
    def upload_file(self):
        return super().upload_file()
    
    @run_in_new_thread
    def quit(self, signum=None, frame=None):
        return super().quit(signum, frame)

    @run_in_new_thread
    def abort(self, text = "", exit_code=1):
        return super().abort(text, exit_code)
    
    

def thread_safe(client_class):
    class Wrapper(client_class):
        @ThreadSafeChatClient.run_in_main_thread
        def on_login_done(self):
            return super().on_login_done()
        
        @ThreadSafeChatClient.run_in_main_thread_with_result
        def askusername(self, is_used=False, is_not_valid=False):
            return super().askusername(is_used, is_not_valid)

        @ThreadSafeChatClient.run_in_main_thread
        def display_message(self, user, message):
            return super().display_message(user, message)

        @ThreadSafeChatClient.run_in_main_thread    
        def display_special_message(self, message):
            return super().display_special_message(message)

        @ThreadSafeChatClient.run_in_main_thread    
        def display_info(self, text):
            return super().display_info(text)
        
        @ThreadSafeChatClient.run_in_main_thread_with_result
        def display_error(self, text):
            return super().display_error(text)

        @ThreadSafeChatClient.run_in_main_thread_with_result
        def open_file(self):
            return super().open_file()

        @ThreadSafeChatClient.run_in_main_thread_with_result
        def save_file(self, default_name):
            return super().save_file(default_name)

        @ThreadSafeChatClient.run_in_main_thread_with_result
        def select_file(self, filenames):
            return super().select_file(filenames)

        # @ThreadSafeChatClient.run_in_main_thread_with_result
        # def prepare_quit(self):
        #     return super().prepare_quit()
        #
        # @ThreadSafeChatClient.run_in_main_thread_with_result
        # def prepare_abort(self):
        #     return super().prepare_abort()

    return Wrapper

