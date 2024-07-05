import socket
import threading
import signal
import sys


from message import *

class BaseChatClient:
    def __init__(self, host='localhost', port=5555):
        self.opened = False
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
        except:
            self.abort('Cannot connect to the server')

        self.opened = True

        signal.signal(signal.SIGINT, self.terminate)

        self.username = self.askusername()
        while True:
            if self.username == None: self.quit()
            send_message(self.sock, self.username)
            t, ok = receive_message(self.sock)
            if t == MsgType.empty:
                self.abort('Cannot connect to the server')
            if ok == "1":
                break
            elif ok == "0":
                self.username = self.askusername(newtry=True)
            else:
                self.abort('Unexpected message received')


        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()

    def __del__(self):
        self.close_connection()

    def askusername(self, newtry=False):
        raise NotImplementedError("This method should be overridden in subclasses")

    def receive_messages(self):
        while True:
            try:
                msg_type, message = receive_message(self.sock)
                if msg_type == MsgType.none:
                    self.display_message(message)
                elif msg_type == MsgType.srv_shutdown:
                    self.server_shutdown_handler()
                elif msg_type == MsgType.ban:
                    self.abort('You are banned')
                elif msg_type == MsgType.usersinfo:
                    self.userinfo_answer_handler(message.split('\0'))
                elif msg_type == MsgType.empty:
                    break
                else:
                    self.display_message('Special message')
            except:
                self.abort('An error occured while receiving messages')

    def server_shutdown_handler(self):
        self.abort('Server was shutted down')

    def display_message(self, message):
        raise NotImplementedError("This method should be overridden in subclasses")

    def send_message(self, message, msg_type):
        try:
            send_message(self.sock, message, msg_type)
        except:
            self.abort('An error occured while sending messages')

    def send_chatmessage(self, message):
        if message:
            self.send_message(message, MsgType.none)

    def usersinfo_request(self):
        self.send_message("", MsgType.usersinfo)

    def userinfo_answer_handler(self, users_online):
        answer = "SERVER: Online are: " + ", ".join(map(lambda s: f'"{s}"', users_online))
        self.display_message(answer)

    def close_connection(self):
        if self.opened:
            self.sock.close()
        self.opened = False

    def prepare_quit(self):
        pass

    def prepare_abort(self):
        self.prepare_quit()

    def quit(self):
        self.close_connection()
        self.prepare_quit()
        sys.exit(0)

    def abort(self, text = None):
        if text is not None:
            self.report_error(text)

        self.close_connection()
        self.prepare_abort()
        sys.exit(1)

    def report_error(self, text):
        print(text)

    def terminate(self, signum, frame):
        self.quit()








