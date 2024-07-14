import curses
from base_client import BaseChatClient

class TUIChatClient(BaseChatClient):
    def __init__(self, host='localhost', port=5555):
        super().__init__(host, port)
        self.screen = None
        self.msg_win = None
        self.input_win = None
        self.max_y, self.max_x = 0, 0

    def start(self):
        curses.wrapper(self.curses_main)

    def curses_main(self, stdscr):
        self.screen = stdscr
        self.max_y, self.max_x = self.screen.getmaxyx()
        curses.curs_set(1)  # Show cursor

        # Initialize color pairs
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Special messages
        curses.init_pair(2, curses.COLOR_BLUE, curses.COLOR_BLACK)   # Info messages
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)    # Error messages

        # Create a window for messages
        self.msg_win = curses.newwin(self.max_y - 2, self.max_x, 0, 0)
        self.msg_win.scrollok(True)
        self.msg_win.idlok(True)

        # Create a window for user input
        self.input_win = curses.newwin(1, self.max_x, self.max_y - 1, 0)
        self.input_win.keypad(True)

        self.screen.clear()
        self.screen.refresh()
        self.login()
        self.start_receive_thread()
        self.chat_loop()

    def askusername(self, is_used=False, is_not_valid=False):
        self.screen.clear()
        self.screen.addstr(0, 0, "Enter your username: ")
        if is_used:
            self.screen.addstr(1, 0, "Username is already taken. Try again.", curses.color_pair(3))
        if is_not_valid:
            self.screen.addstr(1, 0, "Username is not valid. Try again.", curses.color_pair(3))
        self.screen.refresh()
        curses.echo()
        self.username = self._get_input(self.screen, 2, 0)
        curses.noecho()

    def display_message(self, user, message):
        try:
            self.msg_win.addstr(f"{user}> ", curses.color_pair(2))
            self.msg_win.refresh()
            self.msg_win.addstr(f"{message}\n")
            self.msg_win.refresh()
        except curses.error:
            self.msg_win.clear()
            self.msg_win.addstr(f"{user}> ", curses.color_pair(2))
            self.msg_win.refresh()
            self.msg_win.addstr(f"{message}\n")
            self.msg_win.refresh()

    def display_special_message(self, message):
        try:
            self.msg_win.addstr(f"{message}\n", curses.color_pair(1))
            self.msg_win.refresh()
        except curses.error:
            self.msg_win.clear()
            self.msg_win.addstr(f"{message}", curses.color_pair(1))
            self.msg_win.refresh()

    def display_info(self, text):
        try:
            self.msg_win.addstr(f"{text}\n", curses.color_pair(2))
            self.msg_win.refresh()
        except curses.error:
            self.msg_win.clear()
            self.msg_win.addstr(f"{text}", curses.color_pair(2))
            self.msg_win.refresh()

    def open_file(self):
        self.msg_win.addstr("Enter the file path to upload: ")
        self.msg_win.refresh()
        curses.echo()
        filename = self._get_input(self.input_win, 0, 0)
        curses.noecho()
        return filename

    def save_file(self, default_name):
        self.msg_win.addstr(f"Enter the file name to save as (default: {default_name}): ")
        self.msg_win.refresh()
        curses.echo()
        filename = self._get_input(self.input_win, 0, 0)
        curses.noecho()
        if not filename:
            filename = default_name
        return filename

    def select_file(self, filenames):
        self.msg_win.clear()
        self.msg_win.addstr("Select a file to download:\n")
        for i, filename in enumerate(filenames):
            self.msg_win.addstr(f"{i + 1}. {filename}\n")
        self.msg_win.addstr("Enter the number of the file: ")
        self.msg_win.refresh()
        curses.echo()
        try:
            index = int(self._get_input(self.input_win, 0, 0)) - 1
        except ValueError:
            index = -1
        curses.noecho()
        return index

    def chat_loop(self):
        while True:
            self.input_win.clear()
            self.input_win.addstr("> ")
            self.input_win.refresh()
            curses.echo()
            try:
                message = self._get_input(self.input_win, 0, 2)
            except curses.error:
                message = ""
            curses.noecho()
            if message.lower() == '/quit':
                self.quit()
                break
            self.send_chatmessage(message)

    def _get_input(self, window, y, x):
        """Helper function to get input from the user, handling Unicode characters correctly."""
        input_str = ""
        window.move(y, x)
        while True:
            char = window.get_wch()
            if char == "\n":
                break
            elif char in (curses.KEY_BACKSPACE, '\b', '\x7f'):
                if len(input_str) > 0:
                    input_str = input_str[:-1]
                    y, x = window.getyx()
                    window.move(y, x - 1)
                    window.delch()
            else:
                input_str += char
                window.addch(char)
            window.refresh()
        return input_str

if __name__ == "__main__":
    client = TUIChatClient()
    client.start()
