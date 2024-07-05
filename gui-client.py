#!/bin/python

import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, filedialog
from base_client import BaseChatClient

class GUIChatClient(BaseChatClient):
    def _wrapper(self, func):
        return lambda event = None: func()

    def __init__(self, master, host='localhost', port=5555):
        self.master = master
        self.master.title("Chat Client")

        master.protocol("WM_DELETE_WINDOW", self._wrapper(self.quit))

        self.make_menu()
        self.set_hotkeys()

        self.chat_label = tk.Label(master, text="Chat:")
        self.chat_label.pack(padx=20, pady=5)

        self.text_area = scrolledtext.ScrolledText(master)
        self.text_area.pack(padx=20, pady=5)
        self.text_area.config(state='disabled')

        self.msg_label = tk.Label(master, text="Message:")
        self.msg_label.pack(padx=20, pady=5)

        self.input_area = tk.Text(master, height=3)
        self.input_area.pack(padx=20, pady=5)

        self.send_button = tk.Button(master, text="Send", command=self._wrapper(self.write))
        self.send_button.pack(padx=20, pady=5)

        super().__init__(host, port)

    def make_menu(self):
        menu = tk.Menu(self.master)
        menu.add_command(label="Exit", command=self._wrapper(self.quit))
        menu.add_command(label="Users Online Info", command=self._wrapper(self.usersinfo_request))
        menu.add_command(label="Send file", command=self._wrapper(self.send_file))
        self.master.config(menu=menu)

    def set_hotkeys(self):
        self.master.bind('<Control-q>', self._wrapper(self.quit))
        self.master.bind('<Control-s>', self._wrapper(self.write))
        self.master.bind('<Control-Return>', self._wrapper(self.write))


    def askusername(self, newtry = False):
        if newtry:
            return simpledialog.askstring("Username", f'Username "{self.username}" is already used. Please try again', parent=self.master)
        else:
            return simpledialog.askstring("Username", "Please choose a nickname", parent=self.master)

    def display_message(self, message):
        self.text_area.config(state='normal')
        self.text_area.insert('end', message + '\n'+'\n')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')

    def write(self):
        message = self.input_area.get('1.0', 'end').strip()
        self.send_chatmessage(message)
        self.input_area.delete('1.0', 'end')

    def selectfile(self):
        file_path = filedialog.askopenfilename(title="Open a file", filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
        return file_path

    def report_error(self, text):
        messagebox.showerror('Error', text)

    def prepare_quit(self):
        self.master.quit()


if __name__ == "__main__":
    root = tk.Tk()
    client = GUIChatClient(root)
    # client = GUIChatClient(root, port = 55555)
    root.mainloop()
