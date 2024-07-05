import socket
import threading
import signal
import sys
import re

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
    #     print('In del')
    #     print(len(User.users))
    #     del User.users[self.id]
    #     print(len(User.users))

    @classmethod
    def list(cls):
        return User.users.values() 
    
    @classmethod
    def names(cls):
        return map(lambda x: x.name, User.list())

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(5)
        self.history = []
        signal.signal(signal.SIGINT, self.shutdown)
        print(f"Server started on port {port}")

    def broadcast(self, message, msg_type = MsgType.none):
        self.history.append((message, msg_type))

        for user in User.list():
            try:
                send_message(user.sock, message, msg_type)
                print(f'Sended message "{message}" ({msg_type.name})')
            except:
                self.remove_client(user)

    def remove_client(self, user, banned = False):
        if user.id in User.users:
            if not banned:
                msg = f'SERVER: "{user}" has left the chat'
            else:
                msg = f'SERVER: "{user}" was banned'

            user.sock.close()
            del User.users[user.id]
            self.broadcast(msg)


    def handle_client(self, user):
        for msg, msg_type in self.history:
            send_message(user.sock, msg, msg_type)

        while True:
            try:
                msg_type, message = receive_message(user.sock, throw_error=True)
                print(f'Received message "{message}" ({msg_type.name}) from {user}')
                if msg_type == MsgType.none:
                    self.broadcast(f'{user}: {message}')
                elif msg_type == MsgType.usersinfo:
                    answer = "\0".join(User.names())
                    send_message(user.sock, answer, MsgType.usersinfo)
                elif msg_type == MsgType.file:
                    _, data = receive_message(user.sock, throw_error=True)
                    with open(f'./{message}', "w") as f:
                        f.write(data)
                else:
                    print('Message of unknown type')
            except:
                self.remove_client(user)
                break

    def setusername(self, client_socket):
        while True:
            t, username = receive_message(client_socket)
            if t == MsgType.empty:
                client_socket.close()
                return None
            if username in User.names():
                send_message(client_socket, '0')
            else:
                send_message(client_socket, '1')
                return username

    def start(self):
        threading.Thread(target=self.exec_commands, daemon = True).start()

        while True:
            client_socket, addr = self.server.accept()
            username = self.setusername(client_socket)
            if username is None:
                continue
            print(f"Accepted connection from {addr}")
            print(f'New user added: "{username}"')
            self.broadcast(f'SERVER: User "{username}" has joined the chat!')
            newuser = User(username, client_socket)
            client_handler = threading.Thread(target=self.handle_client, args=(newuser,), daemon = True)
            client_handler.start()

    def exec_commands(self):
        while True:
            cmd = input('>>').strip()
            if not cmd:
                continue
            cmd, *args = re.split(r'\s+', cmd)

            if cmd == 'send':
                text = input('Message: ')
                self.broadcast(f'SERVER: {text}')

            elif cmd == 'sendto':
                user = User.users[int(args[0])]
                text = input('Message: ')
                send_message(user.sock, f'SERVER (only for you): {text} (personal)')

            elif cmd == 'users':
                for id, user in User.users.items():
                    print(f'{id}: {user}')
            
            elif cmd == 'kill' and args:
                user = User.users[int(args[0])]
                send_message(user.sock, "", MsgType.ban)
                self.remove_client(user, banned = True)


    def shutdown(self, signum, frame):
        print("\nShutting down server...")
        for user in User.list():
            try:
                send_message(user.sock, "", MsgType.srv_shutdown)
                user.sock.close()
            except:
                pass
        self.server.close()
        sys.exit(0)

if __name__ == "__main__":
    server = ChatServer()
    # server = ChatServer(port = 55555)
    server.start()
