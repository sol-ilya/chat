from base_client import BaseChatClient

class ConsoleChatClient(BaseChatClient):
    def __init__(self, host='localhost', port=5555):
        super().__init__(host, port)


    def askusername(self, newtry = False):
        if newtry:
            print(f'Username {self.username} is already used try again')
        return input("Please enter your username: ")
        

    def display_message(self, message):
        print(message)

    def send_messages(self):
        while True:
            message = input()
            if not message:
                continue
            if message == '/exit':
                break
            self.send_chatmessage(message)
        self.quit()

if __name__ == "__main__":
    client = ConsoleChatClient()
    client.send_messages()
