import socket
import threading
import signal
import sys
import re
import os

from message import *

class User():
    count = 0
    users = {}
    
    def  __init__(self, name, sock):
        self.name = name
        self.sock = sock
        self.id   = User.count
        User.count += 1
        User.users[self.id] = self


    def __str__(self):
        return self.name

    # def __del__(self):
    #     self.log('In del')
    #     self.log(len(User.users))
    #     del User.users[self.id]
    #     self.log(len(User.users))

    @classmethod
    def list(cls):
        return User.users.values() 
    
    @classmethod
    def names(cls):
        return map(lambda x: x.name, User.list())

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        self.history = []
        
        os.makedirs('./files', exist_ok=True)
        self.files = {}
        self.files_count = 0
        
        signal.signal(signal.SIGINT, self.shutdown)
        self.log(f"Server started on port {port}")

    def log(self, text):
        print(text)
    

    def broadcast(self, message, msg_type = MsgType.chatmsg, inbytes=False):
        self.history.append((message, msg_type))

        for user in User.list():
            try:
                if inbytes:
                    send_byte_message(user.sock, message, msg_type)
                else:
                    send_message(user.sock, message, msg_type)
                    
                # self.log(f'Sent message "{message}" ({msg_type.name}) to {user}')
            except:
                self.remove_client(user)

        self.log(f'Sent message "{message}" ({msg_type.name})')

    def remove_client(self, user, banned = False):
        if user.id in User.users:
            if not banned:
                msg = f'"{user}" has left the chat'
            else:
                msg = f'"{user}" was banned'

            user.sock.close()
            del User.users[user.id]
            self.broadcast(msg, MsgType.special)
            self.log(f'User "{user}" removed')


    def handle_client(self, user):
        for msg, msg_type in self.history:
            send_message(user.sock, msg, msg_type)
        self.log(f'Sent History to "{user}"')

        while True:
            try:
                msg_type, message = receive_message(user.sock)
                self.log(f'Received message "{message}" ({msg_type.name}) from {user}')
                if msg_type == MsgType.chatmsg:
                    self.broadcast(f'{user}\0{message}')
                elif msg_type == MsgType.usersinfo:
                    answer = "\0".join(User.names())
                    send_message(user.sock, answer, MsgType.usersinfo)
                elif msg_type == MsgType.put_file:
                    t, data = receive_byte_message(user.sock)
                    if t == MsgType.error:
                        self.log('Stopped file getting procedure')
                        continue
                    self.files[str(self.files_count)] = message
                    with open(f'./files/id{self.files_count}', 'wb') as f:
                        f.write(data)
                    self.broadcast(f'"{user}" sent file "{message}"', MsgType.special)
                    self.files_count += 1
                elif msg_type == MsgType.get_file:
                    msg = "\0".join(f'{i}\0{f}' for i, f in self.files.items())
                    send_message(user.sock, msg, MsgType.get_file)
                    self.log(f'Filelist: {repr(msg)}')
                    self.log(f'Sent file list to {user}')
                    _, i = receive_message(user.sock)
                    if not i:
                        self.log('Stopped file sending procedure')
                        continue
                    self.log(f'User {user} asks to get file #{i}')
                    if i in self.files:
                        try:
                            with open(f'./files/id{i}', 'rb') as f:
                                data = f.read()
                                send_byte_message(user.sock, data)
                                self.log(f'Sent file #{i} to "{user}"')
                        except IOError:
                            send_byte_message(user.sock, b'', MsgType.error)
                    else:
                        send_byte_message(user.sock, b'', MsgType.error)
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

    def check_username(self, username):
        pattern = r'^[a-zA-Z0-9_-]+$'
        return 1 < len(username) < 30 and re.match(pattern, username) is not None

    def setusername(self, client_socket):
        while True:
            t, username = receive_message(client_socket, throw_empty=False)
            if t == MsgType.empty:
                client_socket.close()
                return None
            elif not self.check_username(username):
                send_message(client_socket, '2')
            elif username in User.names():
                send_message(client_socket, '1')
            else:
                send_message(client_socket, '0')
                return username

    def start(self):
        threading.Thread(target=self.exec_commands, daemon = True).start()
        while True:
            try:
                client_socket, addr = self.server.accept()
                self.log(f"Accepted connection from {addr}")
                username = self.setusername(client_socket)
                if username is None:
                    continue
                self.log(f'New user added: "{username}"')
                self.broadcast(f'User "{username}" has joined the chat!', MsgType.special)
                newuser = User(username, client_socket)
                client_handler = threading.Thread(target=self.handle_client, args=(newuser,), daemon = True)
                client_handler.start()
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
                    self.broadcast(f'SERVER: {text}')

                elif cmd == 'sendto' and args:
                    user_id = int(args[0])
                    if user_id in User.users:
                        user = User.users[user_id]
                        text = input('Message: ')
                        send_message(user.sock, f'SERVER (only for you): {text}')
                    else:
                        print(f'User with id {user_id} does not exist')

                elif cmd == 'users':
                    for i, user in User.users.items():
                        print(f'{i}: {user}')

                elif cmd == 'files':
                    for i, file in self.files.items():
                        print(f'{i}: {file}')

                elif cmd == 'kill' and args:
                    user_id = int(args[0])
                    if user_id in User.users:
                        user = User.users[user_id]
                        send_message(user.sock, "", MsgType.ban)
                        self.remove_client(user, banned=True)
                    else:
                        print(f'User with id {user_id} does not exist')

                elif cmd == 'clear':
                    if os.name == 'posix':  # для UNIX-подобных систем (Linux, MacOS)
                        os.system('clear')
                    elif os.name == 'nt':  # для Windows
                        os.system('cls')

                else:
                    print('Unknown command')

            except Exception as e:
                self.log(f'Exception in exec_commands(): {e}')
                continue


    def shutdown(self, signum, frame):
        self.log("\nShutting down server...")
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
    # server = ChatServer(port = 55555)
    server.start()
