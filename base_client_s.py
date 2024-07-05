import socket
import threading

class BaseChatClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((host, port))
        self.receive_thread = threading.Thread(target=self.receive_messages)
        self.receive_thread.start()


    def receive_messages(self):
        while True:
            try:
                message = self.client_socket.recv(1024).decode('utf-8')
                if not message:
                    break
                self.display_message(message)
            except:
                print("An error occurred!")
                self.client_socket.close()
                break

    def display_message(self, message):
        raise NotImplementedError("This method should be overridden in subclasses")

    def send_message(self, message):
        message = '0' + message
        self.client_socket.send(message.encode('utf-8'))

    def send_special(self, message):
        message = '1' + message
        self.client_socket.send(message.encode('utf-8'))

    def close_connection(self):
        self.client_socket.close()
