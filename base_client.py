import socket
import threading
import signal
import sys
import os


from message import *

class BaseChatClient:
    def __init__(self, host='localhost', port=5555):
        self.connect_to_server(host, port)
        # signal.signal(signal.SIGINT, self.terminate)
        self.login()
        self.start_receive_thread()
    
    def connect_to_server(self, host, port):
        self.opened = False
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
            self.opened = True
        except Exception as e:
            self.abort(f'Cannot connect to the server: {e}')

    def login(self):
        self.username = None
        self.askusername()
        while True:
            if self.username is None: self.quit()
            send_message(self.sock, self.username)
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

    def start_receive_thread(self):
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()

    def __del__(self):
        self.close_connection()

    def askusername(self, is_used = False, is_not_valid = False):
        raise NotImplementedError("This method should be overridden in subclasses")

    
    class StopReceiving(Exception):
        pass
    
    class InvalidMessageType(Exception):
        pass
    
    def receive_messages(self):
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
            self.abort('Server was shutted down')
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
        if not filename: return

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
            self.sock.close()

    def prepare_quit(self):
        pass

    def prepare_abort(self):
        self.prepare_quit()

    def quit(self):
        self.close_connection()
        self.prepare_quit()
        os._exit(0)

    def abort(self, text = ""):
        if text:
            self.display_error(text)

        self.close_connection()
        self.prepare_abort()
        os._exit(1)

    def terminate(self, signum, frame):
        self.quit()








