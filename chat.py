import enum
import struct
import socket
import zlib


class MsgType(enum.Enum):
    none = enum.auto()
    chatmsg = enum.auto()
    special = enum.auto()
    error = enum.auto()
    srv_shutdown = enum.auto()
    ban = enum.auto()
    usersinfo = enum.auto()
    put_file = enum.auto()
    get_file = enum.auto()
    shared_edit = enum.auto()
    empty = enum.auto()


class Empty(Exception):
    pass


def send_byte_message(sock, data, msg_type=MsgType.none):
    body = zlib.compress(data)
    header = struct.pack('<IB', len(body), msg_type.value)
    sock.sendall(header + body)


def receive_byte_message(sock, throw_empty=True):
    header_size = 5  # Размер заголовка
    header = bytearray()
    
    # Получаем заголовок
    while len(header) < header_size:
        chunk = sock.recv(header_size - len(header))
        if not chunk:
            if throw_empty:
                raise Empty
            return MsgType.empty, b""
        header.extend(chunk)

    length, msg_type_code = struct.unpack('<IB', header)

    try:
        msg_type = MsgType(msg_type_code)
    except ValueError as e:
        raise ValueError('Invalid message type') from e

    buf_size = 2048
    data = bytearray()
    while len(data) < length:
        to_read = min(buf_size, length - len(data))
        buf = sock.recv(to_read)
        if not buf:
            if throw_empty:
                raise Empty
            return MsgType.empty, b""
        data.extend(buf)

    data = zlib.decompress(data)
    return msg_type, data


def send_message(sock, msg, msg_type=MsgType.none, encoding='utf8'):
    send_byte_message(sock, msg.encode(encoding), msg_type)


def receive_message(sock, throw_empty=True, encoding='utf8'):
    msg_type, data = receive_byte_message(sock, throw_empty)
    return msg_type, data.decode(encoding)
import socket
import threading
import queue
import signal
import sys
import os

from abc import ABC, abstractmethod


class BaseChatClient(ABC):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.username = ""
        
        self.exit_code = 1
        signal.signal(signal.SIGTERM, self.terminate)
        
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
        elif msg_type == MsgType.shared_edit:
            t, data = message[0], message[1:]
            if t == '0':
                self.on_edit_released()
            elif t == '1':
                self.on_edit_captured(data)
            elif t == '2':
                self.update_shared_edit(data)
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
            
    def toggle_shared_edit_involve(self):
        self.send_message("0", MsgType.shared_edit)
    
    def toggle_shared_edit_capture(self):
        self.send_message("1", MsgType.shared_edit)
    
    def send_shared_edit_buffer(self, data):
        self.send_message("2"+data, MsgType.shared_edit)

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

    def close_connection(self):
        if self.opened:
            self.opened = False
            try:
                self.sock.shutdown(socket.SHUT_RDWR)  # Закрываем сокет для приема и передачи данных
            except:
                pass  # Игнорируем возможные ошибки при shutdown
            finally:
                self.sock.close()


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
        
    
    @abstractmethod
    def askusername(self, is_used = False, is_not_valid = False):
        pass
    
    @abstractmethod   
    def on_edit_captured(self, user):
        pass
    
    @abstractmethod
    def on_edit_released(self):
        pass
        
    @abstractmethod
    def update_shared_edit(self, data):
        pass
    
    @abstractmethod    
    def display_message(self, user, message):
        pass
    
    @abstractmethod
    def display_special_message(self, message):
        pass
    
    def display_error(self, text):
        print(text)

    @abstractmethod
    def display_info(self, text):
        pass
    
    @abstractmethod
    def open_file(self):
        pass

    @abstractmethod
    def save_file(self, default_name):
        pass

    @abstractmethod
    def select_file(self, filenames): # returns selected index from files
        pass
    
    def prepare_quit(self):
        pass

    def prepare_abort(self):
        self.prepare_quit()


class ThreadSafeChatClient(BaseChatClient):
    def __init__(self, host, port):
        self.queue = queue.Queue()
        self._login_done = threading.Event()
        super().__init__(host, port)
    
    @abstractmethod
    def schedule(self, call):
        pass
    
    
    def main_loop(self):
        self.main_loop_iteration()
        self.schedule(self.main_loop)

    
    def main_loop_iteration(self):
        while not self.queue.empty():
            obj, func, result_queue, args, kwargs = self.queue.get()
            #print(func.__name__)
            result = func(obj, *args, **kwargs)
            if result_queue:
                result_queue.put(result)

    @staticmethod
    def run_in_main_thread(call):
        def wrapper(self, *args, **kwargs):
            if threading.current_thread() == threading.main_thread():
                call(*args, **kwargs)
                return
            self.queue.put((self, call, None, args, kwargs))
        return wrapper
    
    @staticmethod
    def run_in_main_thread_with_result(call):
        def wrapper(self, *args, **kwargs):
            if threading.current_thread() == threading.main_thread():
                return call(self, *args, **kwargs)
            result_queue = queue.Queue()
            self.queue.put((self, call, result_queue, args, kwargs))
            return result_queue.get()
        return wrapper
    
    # @staticmethod
    # def run_in_new_thread(call):
    #     def wrapper(self, *args, **kwargs):
    #         thread =  threading.Thread(target=call, args=(self,)+args, kwargs=kwargs, daemon=True)
    #         thread.start()
    #         return thread
    #     return wrapper
    
        
    def start(self):
        super().start()
        self.main_loop()
    
    # @run_in_new_thread
    # def upload_file(self):
    #     return super().upload_file()
    
    # def quit(self, signum=None, frame=None):
    #     return super().quit(signum, frame)

    # def abort(self, text = "", exit_code=1):
    #     return super().abort(text, exit_code)
    
    

def thread_safe(client_class):
    class Wrapper(client_class):
        @ThreadSafeChatClient.run_in_main_thread
        def on_edit_captured(self, user):
            return super().on_edit_captured(user)
    
        @ThreadSafeChatClient.run_in_main_thread
        def on_edit_released(self):
            return super().on_edit_released()
        
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
        
        @ThreadSafeChatClient.run_in_main_thread
        def update_shared_edit(self, data):
            return super().update_shared_edit(data)
        
        @ThreadSafeChatClient.run_in_main_thread_with_result
        def open_file(self):
            return super().open_file()

        @ThreadSafeChatClient.run_in_main_thread_with_result
        def save_file(self, default_name):
            return super().save_file(default_name)

        @ThreadSafeChatClient.run_in_main_thread_with_result
        def select_file(self, filenames):
            return super().select_file(filenames)
        
        @ThreadSafeChatClient.run_in_main_thread_with_result
        def prepare_quit(self):
            return super().prepare_quit()
        
        @ThreadSafeChatClient.run_in_main_thread_with_result
        def prepare_abort(self):
            return super().prepare_abort()

    return Wrapper

import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, filedialog

@thread_safe
class GUIChatClient(ThreadSafeChatClient):

    def _wrapper(self, func, *args, **kwargs):
       return lambda event=None: func(*args, **kwargs)

    def __init__(self, master, host='localhost', port=5555):
        super().__init__(host, port)
        self.master = master
        self.master.title("Chat Client")
        self.master.protocol("WM_DELETE_WINDOW", self._wrapper(self.quit))
        
        self.create_widgets()
        self.start()
        self.input_area.focus_set()
    
    def schedule(self, call):
        self.master.after(100, call)
        
    def create_widgets(self):
        self.create_menu()
        self.set_hotkeys()
        self.create_chat_interface()
        self.create_input_interface()

    def create_menu(self):
        menu = tk.Menu(self.master)
        menu.add_command(label="Exit", command=self._wrapper(self.quit))
        menu.add_command(label="Users Online Info", command=self._wrapper(self.get_usersinfo))
        menu.add_command(label="Upload file", command=self._wrapper(self.upload_file))
        menu.add_command(label="Download file", command=self._wrapper(self.download_file))
        menu.add_command(label="Shared edit", command=self._wrapper(self.open_shared_edit))
        self.master.config(menu=menu)

    def set_hotkeys(self):
        self.master.bind('<Control-q>', self._wrapper(self.quit))
        self.master.bind('<Control-s>', self._wrapper(self.write))
        self.master.bind('<Control-Return>', self._wrapper(self.write))
        self.master.bind('<Control-o>', self._wrapper(self.get_usersinfo))
        self.master.bind('<Control-p>', self._wrapper(self.upload_file))
        self.master.bind('<Control-g>', self._wrapper(self.download_file))
        self.master.bind('<Control-e>', self._wrapper(self.open_shared_edit))
        
        
    def create_chat_interface(self):
        self.chat_label = tk.Label(self.master, text="Chat:")
        self.chat_label.pack(padx=20, pady=5)

        self.text_area = scrolledtext.ScrolledText(self.master, wrap=tk.WORD)
        
        self.text_area.tag_configure('special', foreground='green')
        self.text_area.tag_configure('user', foreground='blue')
        self.text_area.tag_configure('normal')
        self.text_area.pack(padx=20, pady=5, expand=True, fill='both')
        self.text_area.config(state='disabled')

    def create_input_interface(self):
        self.msg_label = tk.Label(self.master, text="Message:")
        self.msg_label.pack(padx=20, pady=5)

        self.input_area = scrolledtext.ScrolledText(self.master, height=3, wrap=tk.WORD)
        self.input_area.pack(padx=20, pady=5, expand=True, fill='both')
        
        self.input_area.bind('<Control-u>', self._wrapper(self.clear_entry))

        self.send_button = tk.Button(self.master, text="Send", command=self._wrapper(self.write))
        self.send_button.pack(padx=20, pady=5)
    
    def open_shared_edit(self):
        self.toggle_shared_edit_involve()
        self.locked = True
        self.edit_capture = False
        self.shared_edit_window = tk.Toplevel(self.master)
        self.shared_edit_window.title("Shared edit")
        
        self.capture_info_label = tk.Label(self.shared_edit_window)
        self.capture_info_label.pack(padx=20, pady=5)
                
        self.shared_edit = scrolledtext.ScrolledText(self.shared_edit_window, wrap=tk.NONE)
        self.shared_edit.pack(padx=20, pady=5, expand=True, fill='both')
        self.shared_edit.config(state='disabled')
        self.toggle_capture_button = tk.Button(self.shared_edit_window, text="Сapture", command=self._wrapper(self.toggle_shared_edit_capture))
        self.toggle_capture_button.pack(padx=20, pady=5)
        self.shared_edit_window.bind('<Escape>', self._wrapper(self.toggle_shared_edit_capture))
        
        def save_buffer():
            data = self.shared_edit.get('1.0', 'end').encode('utf-8')
            filename = self._save_file(parent = self.shared_edit_window, default_name="shared_buffer")
            if not filename:
                return
            try:
                with open(filename, "wb") as f:
                    f.write(data)
            except OSError:
                self.display_error('Cannot save buffer')
        
        menu = tk.Menu(self.shared_edit_window)
        menu.add_command(label="Save", command=self._wrapper(save_buffer))
        self.shared_edit_window.config(menu=menu)
        self.shared_edit_window.bind('<Control-s>', self._wrapper(save_buffer))
        
        
        def close():
            self.toggle_shared_edit_involve()
            self.shared_edit_window.destroy()
            
        self.shared_edit_window.protocol("WM_DELETE_WINDOW", self._wrapper(close))
        self.shared_edit_window.bind('<Control-q>', self._wrapper(save_buffer))
        
        def send_buffer_loop():
            if self.edit_capture:
                data = self.shared_edit.get('1.0', 'end')
                self.send_shared_edit_buffer(data)
            self.shared_edit_window.after(100, send_buffer_loop)
        
        self.shared_edit_window.after(100, send_buffer_loop)
        
    
    def on_edit_captured(self, user):
        self.locked = True
        self.toggle_capture_button.configure(state='disabled')
        self.capture_info_label.configure(text=f"Buffer is captured by user '{user}'")
    
    def on_edit_released(self):
        self.locked = False
        self.toggle_capture_button.configure(state='normal')
        self.capture_info_label.configure(text="Buffer is released")

    def toggle_shared_edit_capture(self):
        if self.locked:
            return
        
        if self.edit_capture:
            self.edit_capture = False
            self.shared_edit.config(state='disabled')
            self.toggle_capture_button.configure(text="Capture")
            self.capture_info_label.configure(text="Buffer is released")
            self.shared_edit_window.focus_set()
        else:
            self.edit_capture = True
            self.shared_edit.config(state='normal')
            self.toggle_capture_button.configure(text="Release")
            self.capture_info_label.configure(text="Buffer is captured by you")
            self.shared_edit.focus_set()
            
        super().toggle_shared_edit_capture()
    
    def update_shared_edit(self, data):
        if not self.edit_capture:
            self.shared_edit.config(state='normal')
            self.shared_edit.delete('1.0', tk.END)
            self.shared_edit.insert(tk.INSERT, data)
            #self.shared_edit.yview('1.0')
            self.shared_edit.config(state='disabled')

    def askusername(self, is_used=False, is_not_valid=False):
        if is_used:
            prompt = f'Username "{self.username}" is already used. Please try again'
        elif is_not_valid:
            prompt = f'Username "{self.username}" is not valid. Please try again'
        else:
            prompt = "Enter username"
        self.username = simpledialog.askstring("Username", prompt, parent=self.master)
        if not self.username:
            self.username = ""

    def display_message(self, user, message):
        self.text_area.config(state='normal')
        self.text_area.insert('end', f'{user}> ', 'user')
        self.text_area.insert('end', f'{message}\n\n', 'normal')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')

    def display_special_message(self, message):
        self.text_area.config(state='normal')
        self.text_area.insert('end', message + '\n\n', 'special')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')

    def display_info(self, text):
        messagebox.showinfo('Information', text)
    
    def display_error(self, text):
        messagebox.showerror('Error', text)

    def write(self):
        message = self.input_area.get('1.0', 'end').strip()
        self.send_chatmessage(message)
        self.clear_entry()
    
    def clear_entry(self):
        self.input_area.delete('1.0', 'end')

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open a file", 
            initialdir='.',
            filetypes=(("All files", "*.*"), ("Text files", "*.txt"))
        )
        if not file_path:
            return None
        return file_path

    def save_file(self, default_name):
        return self._save_file(self.master, default_name)
    
    def _save_file(self, parent, default_name):
        file_path = filedialog.asksaveasfilename(
                parent=parent,
                title="Save a file",
                initialdir='.',
                initialfile=default_name,
                defaultextension=".txt",
                filetypes=(("All files", "*.*"), ("Text files", "*.txt"))
        )
        if not file_path:
            return None
        return file_path

    def select_file(self, filenames):
        res = -1
        
        popup = tk.Toplevel(self.master)
        popup.title("File selection")
        
        label = tk.Label(popup, text="Select file to download")
        label.pack(pady=10)

        listbox = tk.Listbox(popup)
        for filename in filenames: 
            listbox.insert(tk.END, filename)
        listbox.select_set(0)
        listbox.pack(padx=20, pady=10)
        
        def close():
            popup.grab_release()
            popup.destroy()
        
        def on_select():
            nonlocal res
            selected = listbox.curselection()
            if selected:
                res = selected[0]
            close()

        popup.bind('<Return>', self._wrapper(on_select))
        popup.bind('<Escape>', self._wrapper(close))

        button_frame = tk.Frame(popup)
        button_frame.pack(pady=10)
        
        select_button = tk.Button(button_frame, text="Select", command=self._wrapper(on_select))
        select_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=self._wrapper(close))
        cancel_button.pack(side=tk.LEFT, padx=5)

        popup.protocol("WM_DELETE_WINDOW", self._wrapper(close))
        
        popup.grab_set()
        popup.wait_window()
    

        return res

    def prepare_quit(self):
        self.master.quit()


if __name__ == "__main__":
    root = tk.Tk()
    # client = GUIChatClient(root)
    # client = GUIChatClient(root, port = 55555)
    client = GUIChatClient(root, host = 's-ia.ru', port = 21)
    root.mainloop()
