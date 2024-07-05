import socket
import threading
import signal

import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox

import enum
import struct

class MsgType(enum.Enum):
    none       = enum.auto()
    quit       = enum.auto()
    server     = enum.auto()
    usersinfo  = enum.auto()
    empty      = enum.auto()


class NothingReceived(Exception):
    pass

def send_message(sock, msg, msg_type = MsgType.none):
    body = msg.encode('utf8')
    header = struct.pack('<IB', len(body), msg_type.value)
    sock.sendall(header + body)

def receive_message(sock):
    header = sock.recv(5)
    length, msg_type_code = struct.unpack('<IB', header)
    try:
        msg_type = MsgType(msg_type_code)
    except ValueError:
        raise ValueError('Invalid message type')

    buf_size = 8192
    received_bytes = 0
    data = bytes()
    while received_bytes + buf_size < length:
        buf = sock.recv(buf_size)
        if not buf:
            return MsgType.empty, None
        data += buf
        received_bytes += buf_size

    if length > 0 and received_bytes != length:
        buf = sock.recv(length - received_bytes)
        if not buf:
            return MsgType.empty, None
        data += buf

    return msg_type, data.decode('utf8')


class BaseChatClient:
    def __init__(self, host='localhost', port=5555):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))
        signal.signal(signal.SIGINT, self.terminate)

        self.username = self.askusername()
        while True:
            send_message(self.sock, self.username)
            _, ok = receive_message(self.sock)
            if ok == "1":
                break
            else:
                self.username = self.askusername(newtry=True)

        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()


    def askusername(self, newtry=False):
        raise NotImplementedError("This method should be overridden in subclasses")


    def receive_messages(self):
        while True:
            try:
                msg_type, message = receive_message(self.sock)
                if msg_type == MsgType.none:
                    self.display_message(message)
                elif msg_type == MsgType.empty:
                    break
                else:
                    self.display_message('Special message')
            except:
                print("An error occurred!")
                self.sock.close()
                break

    def display_message(self, message):
        raise NotImplementedError("This method should be overridden in subclasses")

    def send_chatmessage(self, message):
        send_message(self.sock, message)

    def quit(self):
        send_message(self.sock, "", MsgType.quit)
        self.sock.close()

    def terminate(self, signum, frame):
        self.quit()
        exit(0)

class GUIChatClient(BaseChatClient):
    def __init__(self, master, host='s-ia.ru', port=21):
        self.master = master
        self.master.title("Chat Client")

        self.chat_label = tk.Label(master, text="Chat:")
        self.chat_label.pack(padx=20, pady=5)

        self.text_area = scrolledtext.ScrolledText(master)
        self.text_area.pack(padx=20, pady=5)
        self.text_area.config(state='disabled')

        self.msg_label = tk.Label(master, text="Message:")
        self.msg_label.pack(padx=20, pady=5)

        self.input_area = tk.Text(master, height=3)
        self.input_area.pack(padx=20, pady=5)

        self.send_button = tk.Button(master, text="Send", command=self.write)
        self.send_button.pack(padx=20, pady=5)

        self.exit_button = tk.Button(master, text="Exit", command=self.quit)
        self.exit_button.pack(padx=20, pady=5)

        super().__init__(host, port)


    def askusername(self, newtry = False):
        if newtry:
            return simpledialog.askstring("Username", f'Username "{self.username}" is already used. Please try again', parent=self.master)
        else:
            return simpledialog.askstring("Username", "Please choose a nickname", parent=self.master)

    def display_message(self, message):
        self.text_area.config(state='normal')
        self.text_area.insert('end', message + '\n'+'\n')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')

    def write(self):
        message = self.input_area.get('1.0', 'end').strip()
        self.send_chatmessage(message)
        # self.display_message(message)  # Дублирование сообщения отправителю
        self.input_area.delete('1.0', 'end')

    def quit(self):
        super().quit()
        self.master.quit()

if __name__ == "__main__":
    root = tk.Tk()
    client = GUIChatClient(root)
    root.mainloop()
