import socket
import threading
import signal
import sys
import re
import os
from datetime import datetime

from message import *

class User:
    count = 0
    users = {}

    def __init__(self, name, sock):
        self.name = name
        self.sock = sock
        self.id = User.count
        User.count += 1
        User.users[self.id] = self

    def __str__(self):
        return f"'{self.name}'"

    @classmethod
    def list(cls):
        return User.users.values()

    @classmethod
    def names(cls):
        return map(lambda x: x.name, User.list())

    @classmethod
    def get_user_by_id(cls, user_id):
        return User.users.get(user_id)

    @classmethod
    def remove_user(cls, user):
        del User.users[user.id]

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        
        self.show_log = True
        self.hidden_log = []
        self.history = []
        
        self.files_directory = './files'
        os.makedirs(self.files_directory, exist_ok=True)
        self.files = {}
        self.files_count = 0
        
        signal.signal(signal.SIGINT, self.shutdown)
        self.log(f"Server started on port {port}")

    def log(self, text, must_show=False):
        text = f'{datetime.now().strftime("%H:%M:%S")}    {text}'
        if must_show or self.show_log:
            print(text)
        else:
            self.hidden_log.append(text)
    
    def show_hidden_log(self):
        for msg in self.hidden_log:
            print(msg)

    def broadcast(self, message, msg_type=MsgType.chatmsg, inbytes=False):
        self.history.append((message, msg_type))

        for user in User.list():
            try:
                if inbytes:
                    send_byte_message(user.sock, message, msg_type)
                else:
                    send_message(user.sock, message, msg_type)
                    
                # self.log(f'Sent message "{message}" ({msg_type.name}) to {user}')
            except Exception as e:
                self.log(f'Error broadcasting to {user}: {e}')
                self.remove_client(user)

        self.log(f'Sent message "{message}" ({msg_type.name})')

    def remove_client(self, user, banned=False):
        if user.id in User.users:
            if not banned:
                msg = f'{user} has left the chat'
            else:
                msg = f'{user} was banned'

            user.sock.close()
            User.remove_user(user)
            self.broadcast(msg, MsgType.special)
            self.log(f'{user} removed')

    def handle_client(self, client_socket):
        username = self.set_username(client_socket)
        if username is None:
            self.log('New user not added')
            client_socket.close()
            return
        
        
        user = User(username, client_socket)
        self.log(f'New user added: {user}')
        for msg, msg_type in self.history:
            send_message(user.sock, msg, msg_type)
        self.broadcast(f'{user} has joined the chat!', MsgType.special)
        

        while True:
            try:
                msg_type, message = receive_message(user.sock)
                self.log(f'Received message "{message}" ({msg_type.name}) from {user}')
                if msg_type == MsgType.chatmsg:
                    if message:
                        self.broadcast(f'{user.name}\0{message}')
                elif msg_type == MsgType.usersinfo:
                    answer = "\0".join(User.names())
                    send_message(user.sock, answer, MsgType.usersinfo)
                elif msg_type == MsgType.put_file:
                    self.receive_file(user, message)
                elif msg_type == MsgType.get_file:
                    self.send_filelist(user)
                    _, fileid = receive_message(user.sock)
                    if not fileid:
                        self.log('Stopped file sending procedure')
                        continue
                    self.send_file(user, fileid)
                else:
                    self.log('Error: Message of unknown type')
            except Empty:
                self.log(f'Connection with "{user}" lost')
                self.remove_client(user)
                break
            except Exception as e:
                self.log(f'Catched exception while handling user "{user}": {e}')
                self.remove_client(user)
                break
    
    def receive_file(self, user, filename):
        t, data = receive_byte_message(user.sock)
        if t == MsgType.error:
            self.log('Stopped file getting procedure')
            return
        try:
            fileid = self.add_file(filename, data)
        except OSError:
            send_message(user.sock, "Your file was not saved", MsgType.error)
        else:
            self.broadcast(f'{user} uploaded file "{filename}" ({fileid})', MsgType.special)
    
    def add_file(self, filename, data):
        fileid = str(self.files_count)
        with open(f'{self.files_directory}/id{fileid}', 'wb') as f:
            f.write(data)
            
        self.files[fileid] = filename
        self.files_count += 1
        
        return fileid
    
    def send_filelist(self, user):
        msg = "\0".join(f'{i}\0{f}' for i, f in self.files.items())
        send_message(user.sock, msg, MsgType.get_file)
        self.log(f'Filelist: {repr(msg)}')
        self.log(f'Sent file list to {user}')
    
    def send_file(self, user, fileid):
        self.log(f'{user} asks to get file #{fileid}')
        if fileid in self.files:
            try:
                with open(f'{self.files_directory}/id{fileid}', 'rb') as f:
                    data = f.read()
                    send_byte_message(user.sock, data)
                    self.log(f'Sent file #{fileid} to "{user}"')
            except IOError:
                send_byte_message(user.sock, b'', MsgType.error)
        else:
            send_byte_message(user.sock, b'', MsgType.error)

    def check_username(self, username):
        pattern = r'^[a-zA-Z0-9_-]+$'
        return 1 <= len(username) <= 30 and re.match(pattern, username) is not None

    def set_username(self, client_socket):
        while True:
            t, username = receive_message(client_socket, throw_empty=False)
            if t == MsgType.empty or not username:
                client_socket.close()
                return None
            elif not self.check_username(username):
                send_message(client_socket, '2')
            elif username in User.names() or username == 'admin':
                send_message(client_socket, '1')
            else:
                send_message(client_socket, '0')
                return username

    def start(self):
        threading.Thread(target=self.exec_commands, daemon=True).start()
        while True:
            try:
                client_socket, addr = self.server.accept()
                self.log(f"Accepted connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
                
            except ConnectionResetError as e:
                self.log(f'Connection reset error: {e}')
                continue

    def exec_commands(self):
        while True:
            try:
                cmd = input('>>').strip()
                if not cmd:
                    continue
                cmd, *args = re.split(r'\s+', cmd)

                if cmd == 'send':
                    text = input('Message: ')
                    self.broadcast(f'admin\0{text}')

                elif cmd == 'sendto' and args:
                    user_id = int(args[0])
                    user = User.get_user_by_id(user_id)
                    if user:
                        text = input('Message: ')
                        send_message(user.sock, f'admin (only for you)\0{text}', MsgType.chatmsg)
                    else:
                        print(f'User with id {user_id} does not exist')

                elif cmd == 'users':
                    for user in User.list():
                        print(f'{user.id}: {user}')

                elif cmd == 'kill' and args:
                    user_id = int(args[0])
                    user = User.get_user_by_id(user_id)
                    if user:
                        send_message(user.sock, "", MsgType.ban)
                        self.remove_client(user, banned=True)
                    else:
                        print(f'User with id {user_id} does not exist')

                elif cmd == 'clear':
                    if os.name == 'posix':
                        os.system('clear')
                    elif os.name == 'nt':
                        os.system('cls')

                elif cmd == 'log':
                    if self.show_log:
                        self.show_log = False
                    else:
                        self.show_log = True
                        self.show_hidden_log()
                        
                elif cmd == 'files':
                    for i, file in self.files.items():
                        print(f'{i}: {file}')
                
                elif cmd == 'load':
                    filename = input('Enter filename: ')
                    with open(filename, "rb") as f:
                        data = f.read()
                    
                    self.add_file(os.path.basename(filename), data)
                    self.broadcast(f'admin sent file "{filename}"', MsgType.special)
                    
                elif cmd == 'rm' and args:
                    fileid = args[0]
                    if fileid not in self.files:
                        print(f'File with id {fileid} does not exist')
                    os.remove(f'{self.files_directory}/id{fileid}')
                    self.log(f'File #{fileid} was removed')
                    filename = self.files.pop(fileid)
                    self.broadcast(f'File "{filename}" ({fileid}) was removed', MsgType.special)
                    

                else:
                    print('Unknown command')

            except Exception as e:
                self.log(f'Exception in exec_commands(): {e}')
                continue

    def shutdown(self, signum, frame):
        self.log("Shutting down server...")
        for user in list(User.list()):
            try:
                send_message(user.sock, "", MsgType.srv_shutdown)
                user.sock.close()
            except Exception as e:
                self.log(f'Error shutting down user {user}: {e}')
                continue
        self.server.close()
        sys.exit(0)

if __name__ == "__main__":
    server = ChatServer()
    server.start()
