import socket
import threading
import signal
import sys

from message import *

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(5)
        self.history = []
        self.clients = {}
        signal.signal(signal.SIGINT, self.shutdown)
        print(f"Server started on port {port}")

    def broadcast(self, message, msg_type = MsgType.none):
        self.history.append((message, msg_type))

        for user, client_socket in self.clients.items():
            try:
                send_message(client_socket, message, msg_type)
                print(f'Sended message "{message}" ({msg_type.name})')
            except:
                self.remove_client(user)

    def remove_client(self, user):
        if user in self.clients:
            self.clients[user].close()
            del self.clients[user]
            print(f'Removed user {user}')
            self.broadcast(f'SERVER: "{user}" has left the chat')


    def handle_client(self, user, client_socket):
        for msg, msg_type in self.history:
            send_message(client_socket, msg, msg_type)

        while True:
            try:
                msg_type, message = receive_message(client_socket)
                print(f'Received message "{message}" ({msg_type.name}) from {user}')
                if msg_type == MsgType.none:
                    self.broadcast(f'{user}: {message}')
                elif  msg_type == MsgType.usersinfo:
                    answer = "\0".join(self.clients.keys())
                    send_message(client_socket, answer, MsgType.usersinfo)
                elif msg_type == MsgType.empty:
                    self.remove_client(user)
                    break
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
            if username in self.clients:
                send_message(client_socket, '0')
            else:
                send_message(client_socket, '1')
                return username

    def start(self):
        # threading.Thread(target=self.exec_commands).start()

        while True:
            client_socket, addr = self.server.accept()
            username = self.setusername(client_socket)
            if username is None:
                continue
            print(f"Accepted connection from {addr}")
            print(f'New user added: "{username}"')
            self.broadcast(f'SERVER: User "{username}" has joined the chat!')
            self.clients[username] = client_socket
            client_handler = threading.Thread(target=self.handle_client, args=(username, client_socket), daemon = True)
            client_handler.start()

    def shutdown(self, signum, frame):
        print("\nShutting down server...")
        for client in self.clients.values():
            try:
                send_message(client, "", MsgType.srv_shutdown)
                client.close()
            except:
                pass
        self.server.close()
        sys.exit(0)

if __name__ == "__main__":
    server = ChatServer()
    # server = ChatServer(port = 55555)
    server.start()
