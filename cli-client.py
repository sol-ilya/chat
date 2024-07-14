import signal
import os
from colorama import init, Fore, Style

from base_client import BaseChatClient

class CLIChatClient(BaseChatClient):
    def __init__(self, host='localhost', port=5555):
        init() # colorama
        signal.signal(signal.SIGINT, self.quit)
        super().__init__(host, port)
        #sending = threading.Thread(target=self.send_messages, daemon=True)
        #sending.start()
        #sending.join()
        self.start()
        
        self.sending_loop()


    def askusername(self, is_used = False, is_not_valid = False):
        if is_used:
            print(f'Username {self.username} is already used. Please try again')
        elif is_not_valid:
            print(f'Username {self.username} is not valid. Please try again')
        self.username = input("Please enter your username: ")
        

    def display_message(self, user, message):
        print(f'{Fore.BLUE+Style.BRIGHT}{user}>{Style.RESET_ALL} {message}')
    
    def display_special_message(self, message):
        return print(f'{Fore.GREEN+Style.BRIGHT}{message}{Style.RESET_ALL}')
    
    def display_error(self, text):
        return print(f'{Fore.RED+Style.BRIGHT}{text}{Style.RESET_ALL}')
    
    def display_info(self, text):
        return print(f'{Fore.BLUE+Style.BRIGHT}{text}{Style.RESET_ALL}')
    
    def open_file(self):
        filename = input('Enter filename: ')
        if os.path.isfile(filename):
            return filename
        else:
            return None
    
    def select_file(self, filenames):
        for i, f in enumerate(filenames):
            print(f'{i}: {f}')
        i = input('Select file (<Enter> for cancel): ')
        if not i:
            return -1
        i = int(i)
        return i
    
    def save_file(self, default_name):
        filename = input(f'Save file as (default: {default_name}) ')
        if not filename:
            return default_name
        return filename
        

    def sending_loop(self):
        while True:
            message = input()
            if not message:
                continue
            if message[0] == '/':
                if message == '/quit':
                    self.quit()
                elif message == '/usersinfo':
                    self.get_usersinfo()
                elif message == '/upload':
                    self.upload_file()
                elif message == '/download':
                    self.download_file()
                else:
                    self.display_error('Invalid command')
            else:
                self.send_chatmessage(message)
        # self.quit()

if __name__ == "__main__":
    client = CLIChatClient()
