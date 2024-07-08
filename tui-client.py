import curses
from base_client import BaseChatClient

class TUIChatClient(BaseChatClient):
    def __init__(self, host='localhost', port=5555):
        self.host = host
        self.port = port
        self.screen = None
        self.chat_window = None
        self.input_window = None
        self.info_window = None
        self.input_buffer = ''
        self.username = None
        super().__init__(host, port)

    def start_interface(self):
        curses.wrapper(self.run)

    def run(self, stdscr):
        try:
            self.screen = stdscr
            curses.curs_set(1)  # Show the cursor
            self.screen.clear()

            # Setup chat window
            self.chat_window = curses.newwin(curses.LINES - 3, curses.COLS, 0, 0)
            self.chat_window.scrollok(True)
            self.chat_window.idlok(True)

            # Setup input window
            self.input_window = curses.newwin(3, curses.COLS, curses.LINES - 3, 0)
            self.input_window.scrollok(True)
            self.input_window.idlok(True)
            self.input_window.keypad(True)
            
            self.info_window = curses.newwin(1, curses.COLS, curses.LINES - 4, 0)

            self.screen.refresh()
            self.chat_window.refresh()
            self.input_window.refresh()

            self.get_valid_username()

            while True:
                self.input_window.clear()
                self.input_window.addstr(0, 0, 'Message: ')
                self.input_window.refresh()
                self.input_buffer = self.input_window.getstr(1, 0, 256).decode('utf-8').strip()
                self.write()
        except Exception as e:
            self.prepare_quit()
            print(f"Error: {e}")

    def display_message(self, user, message):
        self.chat_window.addstr(f'{user}> {message}\n')
        self.chat_window.refresh()

    def display_special_message(self, message):
        self.chat_window.addstr(message + '\n', curses.A_BOLD)
        self.chat_window.refresh()

    def display_info(self, text):
        self.info_window.clear()
        self.info_window.addstr(0, 0, text)
        self.info_window.refresh()
        self.screen.refresh()

    def report_error(self, text):
        self.display_info(f'Error: {text}')

    def prompt_username(self, is_used=False, is_not_valid=False):
        self.input_window.clear()
        prompt = "Enter username: "
        if is_used:
            prompt = f'Username "{self.username}" is already used. Please try again\nEnter username: '
        elif is_not_valid:
            prompt = f'Username "{self.username}" is not valid. Please try again\nEnter username: '

        self.input_window.addstr(0, 0, prompt)
        self.input_window.refresh()
        self.username = self.input_window.getstr(1, 0, 256).decode('utf-8').strip()
        self.input_window.clear()

    def askusername(self, is_used=False, is_not_valid=False):
        self.prompt_username(is_used, is_not_valid)

    def open_file(self):
        # File dialog is not implemented in TUI; stub for compliance with the base class.
        return None

    def save_file(self, initname):
        # File dialog is not implemented in TUI; stub for compliance with the base class.
        return None

    def select_file(self, filenames):
        # File selection dialog is not implemented in TUI; stub for compliance with the base class.
        return -1

    def write(self):
        message = self.input_buffer
        self.send_chatmessage(message)
        self.input_buffer = ''

    def prepare_quit(self):
        self.screen.clear()
        self.screen.refresh()
        curses.endwin()

    def __del__(self):
        self.close_connection()

if __name__ == "__main__":
    client = TUIChatClient(host='localhost', port=5555)
    client.start_interface()
