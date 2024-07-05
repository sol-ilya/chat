import socket
import threading
import signal
import sys

class ChatServer:
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.bind((host, port))
        self.server.listen(5)
        self.clients = []
        signal.signal(signal.SIGINT, self.shutdown)
        print(f"Server started on port {port}")

    def broadcast(self, message, current_client):
        for client in self.clients:
            try:
                client.send(message.encode('utf-8'))
            except:
                self.remove_client(client)

    def remove_client(self, client_socket):
        if client_socket in self.clients:
            self.clients.remove(client_socket)
            client_socket.close()

    def handle_client(self, client_socket):
        while True:
            try:
                message = client_socket.recv(1024).decode('utf-8')
                if message.endswith("has left the chat."):
                    self.broadcast(message, client_socket)
                    self.remove_client(client_socket)
                    break
                print(f"Received message: {message}")
                self.broadcast(message, client_socket)
            except:
                self.remove_client(client_socket)
                break

    def start(self):
        while True:
            client_socket, addr = self.server.accept()
            print(f"Accepted connection from {addr}")
            self.clients.append(client_socket)
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
            client_handler.start()

    def shutdown(self, signum, frame):
        print("\nShutting down server...")
        for client in self.clients:
            try:
                client.send("Server is shutting down.".encode('utf-8'))
                client.close()
            except:
                pass
        self.server.close()
        sys.exit(0)

if __name__ == "__main__":
    server = ChatServer()
    server.start()
