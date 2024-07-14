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
            else:
                return MsgType.empty, b""
        header.extend(chunk)

    length, msg_type_code = struct.unpack('<IB', header)

    try:
        msg_type = MsgType(msg_type_code)
    except ValueError:
        raise ValueError('Invalid message type')

    buf_size = 2048
    data = bytearray()
    while len(data) < length:
        to_read = min(buf_size, length - len(data))
        buf = sock.recv(to_read)
        if not buf:
            if throw_empty:
                raise Empty
            else:
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
import signal
import sys
import os



class BaseChatClient:
    def __init__(self, host, port):
        
        self.exit_code = 1
        signal.signal(signal.SIGTERM, self.terminate)
        
        self.connect_to_server(host, port)
        # signal.signal(signal.SIGINT, self.terminate)
        
    def start(self):
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
        self.receive_thread = threading.Thread(target=self.receiving_loop, daemon=True)
        self.receive_thread.start()

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


import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, filedialog
import queue

class GUIChatClient(BaseChatClient):
    #def _wrapper(self, func, *func_args, **func_kwargs):
    #    return lambda event=None: self.add_task_to_queue(func,func_args, func_kwargs )
    
    def _wrapper(self, func, *args, **kwargs):
       return lambda event=None: func(*args, **kwargs)

    def __init__(self, master, host='localhost', port=5555):
        self.master = master
        self.master.title("Chat Client")
        self.master.protocol("WM_DELETE_WINDOW", self._wrapper(self.quit))
        self.init_queue()
        self.create_widgets()
        super().__init__(host, port)
        
        self.start()
        self.input_area.focus_set()

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
        self.master.config(menu=menu)

    def set_hotkeys(self):
        self.master.bind('<Control-q>', self._wrapper(self.quit))
        self.master.bind('<Control-s>', self._wrapper(self.write))
        self.master.bind('<Control-Return>', self._wrapper(self.write))
        self.master.bind('<Control-o>', self._wrapper(self.get_usersinfo))
        self.master.bind('<Control-p>', self._wrapper(self.upload_file))
        self.master.bind('<Control-g>', self._wrapper(self.download_file))
        
        
        

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
        
        #self.input_area.focus_set()
        
        self.input_area.bind('<Control-u>', self._wrapper(self.clear_entry))

        self.send_button = tk.Button(self.master, text="Send", command=self._wrapper(self.write))
        self.send_button.pack(padx=20, pady=5)
    
    def init_queue(self):
        self.queue = queue.Queue()
        self.check_queue()
    
    def check_queue(self):
        try:
            while True:
                func, result_queue, args, kwargs = self.queue.get_nowait()
                result = func(*args, **kwargs)
                if result_queue:
                    result_queue.put(result)
        except queue.Empty:
            pass
        self.master.after(100, self.check_queue)

    def run_in_main_thread(self, func, *args, **kwargs):
        result_queue = queue.Queue()
        self.queue.put((func, result_queue, args, kwargs))
        return result_queue.get()

    def askusername(self, is_used=False, is_not_valid=False):
        if is_used:
            prompt = f'Username "{self.username}" is already used. Please try again'
        elif is_not_valid:
            prompt = f'Username "{self.username}" is not valid. Please try again'
        else:
            prompt = "Enter username"
        self.username = simpledialog.askstring("Username", prompt, parent=self.master)

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
        file_path = filedialog.asksaveasfilename(
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
        return self.run_in_main_thread(self._select_file, filenames)

    def _select_file(self, filenames):
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

    def display_error(self, text):
        messagebox.showerror('Error', text)

    def prepare_quit(self):
        self.master.quit()


if __name__ == "__main__":
    root = tk.Tk()
    # client = GUIChatClient(root)
    # client = GUIChatClient(root, port = 55555)
    client = GUIChatClient(root, host = 's-ia.ru', port = 21)
    root.mainloop()
