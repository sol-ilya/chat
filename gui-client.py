#!/bin/python

import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, filedialog
import threading as th
import queue
from base_client import BaseChatClient

class GUIChatClient(BaseChatClient):
    #def _wrapper(self, func, *func_args, **func_kwargs):
    #    return lambda event=None: self.add_task_to_queue(func,func_args, func_kwargs )
    
    def _wrapper(self, func, *args, **kwargs):
       return lambda event=None: func(*args, **kwargs)

    def __init__(self, master, host='localhost', port=5555):
        self.master = master
        self.master.title("Chat Client")
        self.master.protocol("WM_DELETE_WINDOW", self._wrapper(self.quit))
        self.init_queue()
        self.create_widgets()
        super().__init__(host, port)
        
    def init_queue(self):
        self.queue = queue.Queue()
        self.check_queue()
    
    def check_queue(self):
        try:
            while True:
                func, args, kwargs, result_queue = self.queue.get_nowait()
                result = func(*args, **kwargs)
                if result_queue:
                    result_queue.put(result)
        except queue.Empty:
            pass
        self.master.after(100, self.check_queue)

    def add_task_to_queue(self, func, *args, result_queue=None, **kwargs):
        self.queue.put((func, args, kwargs, result_queue))
    
    def run_in_main_thread(self, func, *args, **kwargs):
        result_queue = queue.Queue()
        self.add_task_to_queue(func, *args, result_queue=result_queue, **kwargs)
        return result_queue.get()

    def create_widgets(self):
        self.create_menu()
        self.set_hotkeys()
        self.create_chat_interface()
        self.create_input_interface()

    def create_menu(self):
        menu = tk.Menu(self.master)
        menu.add_command(label="Exit", command=self._wrapper(self.quit))
        menu.add_command(label="Users Online Info", command=self._wrapper(self.get_usersinfo))
        menu.add_command(label="Upload file", command=self._wrapper(self.upload_file))
        menu.add_command(label="Download file", command=self._wrapper(self.download_file))
        self.master.config(menu=menu)

    def set_hotkeys(self):
        self.master.bind('<Control-q>', self._wrapper(self.quit))
        self.master.bind('<Control-s>', self._wrapper(self.write))
        self.master.bind('<Control-Return>', self._wrapper(self.write))

    def create_chat_interface(self):
        self.chat_label = tk.Label(self.master, text="Chat:")
        self.chat_label.pack(padx=20, pady=5)

        self.text_area = scrolledtext.ScrolledText(self.master)
        
        self.text_area.tag_configure('special', foreground='green')
        self.text_area.tag_configure('user', foreground='blue')
        self.text_area.tag_configure('normal')
        self.text_area.pack(padx=20, pady=5)
        self.text_area.config(state='disabled')

    def create_input_interface(self):
        self.msg_label = tk.Label(self.master, text="Message:")
        self.msg_label.pack(padx=20, pady=5)

        self.input_area = tk.Text(self.master, height=3)
        self.input_area.pack(padx=20, pady=5)

        self.send_button = tk.Button(self.master, text="Send", command=self._wrapper(self.write))
        self.send_button.pack(padx=20, pady=5)

    def askusername(self, is_used=False, is_not_valid=False):
        if is_used:
            prompt = f'Username "{self.username}" is already used. Please try again'
        elif is_not_valid:
            prompt = f'Username "{self.username}" is not valid. Please try again'
        else:
            prompt = "Enter username"
        self.username = simpledialog.askstring("Username", prompt, parent=self.master)

    def display_message(self, user, message):
        self.text_area.config(state='normal')
        self.text_area.insert('end', f'{user}> ', 'user')
        self.text_area.insert('end', f'{message}\n\n', 'normal')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')
    
    def display_special_message(self, message):
        self.text_area.config(state='normal')
        self.text_area.insert('end', message + '\n\n', 'special')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')

    def display_info(self, text):
        messagebox.showinfo('Information', text)

    def write(self):
        message = self.input_area.get('1.0', 'end').strip()
        self.send_chatmessage(message)
        self.input_area.delete('1.0', 'end')

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open a file", 
            initialdir='.',
            filetypes=(("All files", "*.*"), ("Text files", "*.txt"))
        )
        return file_path

    def save_file(self, default_name):
        file_path = filedialog.asksaveasfilename(
                title="Save a file",
                initialdir='.',
                initialfile=default_name,
                defaultextension=".txt",
                filetypes=(("All files", "*.*"), ("Text files", "*.txt"))
        )
        return file_path
    
    def select_file(self, filenames):
        return self.run_in_main_thread(self._select_file, filenames)

    def _select_file(self, filenames):
        self._res = -1
        self._selection_complete = tk.BooleanVar(value=False)
        
        self._popup = tk.Toplevel(self.master)
        self._popup.title("File selection")
        
        label = tk.Label(self._popup, text="Select file to download")
        label.pack(pady=10)

        self._listbox = tk.Listbox(self._popup)
        for filename in filenames: 
            self._listbox.insert(tk.END, filename)
        self._listbox.select_set(0)
        self._listbox.pack(padx=20, pady=10)

        self._popup.protocol("WM_DELETE_WINDOW", self._wrapper(self._kill_win))

        button_frame = tk.Frame(self._popup)
        button_frame.pack(pady=10)

        select_button = tk.Button(button_frame, text="Select", command=self._wrapper(self._on_select))
        select_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=self._wrapper(self._kill_win))
        cancel_button.pack(side=tk.LEFT, padx=5)

        # self._popup.wait_visibility()   # <<< NOTE
        self._popup.grab_set()          # <<< NOTE
        # self._popup.transient(self.master)   # <<< NOTE
        
        
        self._popup.wait_window()

        return self._res

    def _kill_win(self):
        self._popup.grab_release()
        self._popup.destroy()
        
    def _on_select(self):
        selected = self._listbox.curselection()
        if selected:
            self._res = selected[0]
        self._kill_win()

    def display_error(self, text):
        messagebox.showerror('Error', text)

    def prepare_quit(self):
        self.master.quit()


if __name__ == "__main__":
    root = tk.Tk()
    client = GUIChatClient(root)
    # client = GUIChatClient(root, port = 55555)
    # client = GUIChatClient(root, host = 's-ia.ru', port = 21)
    root.mainloop()
