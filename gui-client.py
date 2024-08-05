import tkinter as tk
from tkinter import scrolledtext, simpledialog, messagebox, filedialog
from base_client import ThreadSafeChatClient, thread_safe
from message import SpecElems

@thread_safe
class GUIChatClient(ThreadSafeChatClient):

    def _wrapper(self, func, *args, **kwargs):
        return lambda event=None: func(*args, **kwargs)

    def __init__(self, master, host='localhost', port=5555):
        super().__init__(host, port)
        self.master = master
        self.master.title("Chat Client")
        self.master.protocol("WM_DELETE_WINDOW", self._wrapper(self.quit))
        
        self.create_widgets()
        self.start()
        self.input_area.focus_set()
    
    def schedule(self, call):
        self.master.after(100, call)
        
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
        menu.add_command(label="Shared edit", command=self._wrapper(self.open_shared_edit))
        self.master.config(menu=menu)

    def set_hotkeys(self):
        self.master.bind('<Control-q>', self._wrapper(self.quit))
        self.master.bind('<Control-s>', self._wrapper(self.write))
        self.master.bind('<Control-Return>', self._wrapper(self.write))
        self.master.bind('<Control-o>', self._wrapper(self.get_usersinfo))
        self.master.bind('<Control-p>', self._wrapper(self.upload_file))
        self.master.bind('<Control-g>', self._wrapper(self.download_file))
        self.master.bind('<Control-e>', self._wrapper(self.open_shared_edit))
        
        
    def create_chat_interface(self):
        self.chat_label = tk.Label(self.master, text="Chat:")
        self.chat_label.pack(padx=20, pady=5)

        self.text_area = scrolledtext.ScrolledText(self.master, wrap=tk.WORD)
        
        self.text_area.tag_configure('green', foreground='green')
        self.text_area.tag_configure('blue', foreground='blue')
        self.text_area.tag_configure('red', foreground='red')
        self.text_area.tag_configure('normal')
        self.text_area.pack(padx=20, pady=5, expand=True, fill='both')
        self.text_area.config(state='disabled')

    def create_input_interface(self):
        self.msg_label = tk.Label(self.master, text="Message:")
        self.msg_label.pack(padx=20, pady=5)

        self.input_area = scrolledtext.ScrolledText(self.master, height=3, wrap=tk.WORD)
        self.input_area.pack(padx=20, pady=5, expand=True, fill='both')
        
        self.input_area.bind('<Control-u>', self._wrapper(self.clear_entry))

        self.send_button = tk.Button(self.master, text="Send", command=self._wrapper(self.write))
        self.send_button.pack(padx=20, pady=5)
    
    def open_shared_edit(self):
        self.toggle_shared_edit_involve()
        self.locked = True
        self.edit_capture = False
        self.shared_edit_window = tk.Toplevel(self.master)
        self.shared_edit_window.title("Shared edit")
        
        self.capture_info_label = tk.Label(self.shared_edit_window)
        self.capture_info_label.pack(padx=20, pady=5)
                
        self.shared_edit = scrolledtext.ScrolledText(self.shared_edit_window, wrap=tk.NONE)
        self.shared_edit.pack(padx=20, pady=5, expand=True, fill='both')
        self.shared_edit.config(state='disabled')
        self.toggle_capture_button = tk.Button(self.shared_edit_window, text="Сapture", command=self._wrapper(self.toggle_shared_edit_capture))
        self.toggle_capture_button.pack(padx=20, pady=5)
        self.shared_edit_window.bind('<Escape>', self._wrapper(self.toggle_shared_edit_capture))
        
        def save_buffer():
            data = self.shared_edit.get('1.0', 'end').encode('utf-8')
            filename = self._save_file(parent = self.shared_edit_window, default_name="shared_buffer")
            if not filename:
                return
            try:
                with open(filename, "wb") as f:
                    f.write(data)
            except OSError:
                self.display_error('Cannot save buffer')
        
        menu = tk.Menu(self.shared_edit_window)
        menu.add_command(label="Save", command=self._wrapper(save_buffer))
        self.shared_edit_window.config(menu=menu)
        self.shared_edit_window.bind('<Control-s>', self._wrapper(save_buffer))
        
        
        def close():
            self.toggle_shared_edit_involve()
            self.shared_edit_window.destroy()
            
        self.shared_edit_window.protocol("WM_DELETE_WINDOW", self._wrapper(close))
        self.shared_edit_window.bind('<Control-q>', self._wrapper(close))
        
        def send_buffer_loop():
            if self.edit_capture:
                data = self.shared_edit.get('1.0', 'end')
                self.send_shared_edit_buffer(data)
            self.shared_edit_window.after(100, send_buffer_loop)
        
        self.shared_edit_window.after(100, send_buffer_loop)
        
    
    def on_edit_captured(self, user):
        self.locked = True
        self.toggle_capture_button.configure(state='disabled')
        self.capture_info_label.configure(text=f"Buffer is captured by user '{user}'")
    
    def on_edit_released(self):
        self.locked = False
        self.toggle_capture_button.configure(state='normal')
        self.capture_info_label.configure(text="Buffer is released")

    def toggle_shared_edit_capture(self):
        if self.locked:
            return
        
        if self.edit_capture:
            self.edit_capture = False
            self.shared_edit.config(state='disabled')
            self.toggle_capture_button.configure(text="Capture")
            self.capture_info_label.configure(text="Buffer is released")
            self.shared_edit_window.focus_set()
        else:
            self.edit_capture = True
            self.shared_edit.config(state='normal')
            self.toggle_capture_button.configure(text="Release")
            self.capture_info_label.configure(text="Buffer is captured by you")
            self.shared_edit.focus_set()
            
        super().toggle_shared_edit_capture()
    
    def update_shared_edit(self, data):
        if not self.edit_capture:
            self.shared_edit.config(state='normal')
            self.shared_edit.delete('1.0', tk.END)
            self.shared_edit.insert(tk.INSERT, data)
            #self.shared_edit.yview('1.0')
            self.shared_edit.config(state='disabled')

    def askusername(self, is_used=False, is_not_valid=False):
        if is_used:
            prompt = f'Username "{self.username}" is already used. Please try again'
        elif is_not_valid:
            prompt = f'Username "{self.username}" is not valid. Please try again'
        else:
            prompt = "Enter username"
        self.username = simpledialog.askstring("Username", prompt, parent=self.master)
        if not self.username:
            self.username = ""

    def display_message(self, user, message):
        self.text_area.config(state='normal')
        self.text_area.insert('end', f'{user}> ', 'blue')
        self.text_area.insert('end', f'{message}\n\n', 'normal')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')

    def display_special_message(self, elems):
        
        
        self.text_area.config(state='normal')
        for frmt, text in elems:
            if frmt == SpecElems.TXT:
                self.text_area.insert('end', text, 'green')
            elif frmt == SpecElems.USER:
                self.text_area.insert('end', text, 'blue')
            elif frmt == SpecElems.FILE:
                self.text_area.insert('end', f'"{text}"', 'red')
        self.text_area.insert('end', '\n\n')
        self.text_area.yview('end')
        self.text_area.config(state='disabled')
            

    def display_info(self, text):
        messagebox.showinfo('Information', text)
    
    def display_error(self, text):
        messagebox.showerror('Error', text)

    def write(self):
        message = self.input_area.get('1.0', 'end').strip()
        self.send_chatmessage(message)
        self.clear_entry()
    
    def clear_entry(self):
        self.input_area.delete('1.0', 'end')

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open a file",
            initialdir='.',
            filetypes=(("All files", "*.*"), ("Text files", "*.txt"))
        )
        if not file_path:
            return None
        return file_path

    def save_file(self, default_name):
        return self._save_file(self.master, default_name)
    
    def _save_file(self, parent, default_name):
        file_path = filedialog.asksaveasfilename(
                parent=parent,
                title="Save a file",
                initialdir='.',
                initialfile=default_name,
                defaultextension=".txt",
                filetypes=(("All files", "*.*"), ("Text files", "*.txt"))
        )
        if not file_path:
            return None
        return file_path

    def select_file(self, filenames):
        res = -1
        
        popup = tk.Toplevel(self.master)
        popup.title("File selection")
        
        label = tk.Label(popup, text="Select file to download")
        label.pack(pady=10)

        listbox = tk.Listbox(popup)
        for filename in filenames: 
            listbox.insert(tk.END, filename)
        listbox.select_set(0)
        listbox.pack(padx=20, pady=10)
        
        def close():
            popup.grab_release()
            popup.destroy()
        
        def on_select():
            nonlocal res
            selected = listbox.curselection()
            if selected:
                res = selected[0]
            close()

        popup.bind('<Return>', self._wrapper(on_select))
        popup.bind('<Escape>', self._wrapper(close))

        button_frame = tk.Frame(popup)
        button_frame.pack(pady=10)
        
        select_button = tk.Button(button_frame, text="Select", command=self._wrapper(on_select))
        select_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=self._wrapper(close))
        cancel_button.pack(side=tk.LEFT, padx=5)

        popup.protocol("WM_DELETE_WINDOW", self._wrapper(close))
        
        popup.grab_set()
        popup.wait_window()
    

        return res

    def prepare_quit(self):
        self.master.quit()


if __name__ == "__main__":
    root = tk.Tk()
    client = GUIChatClient(root)
    # client = GUIChatClient(root, port = 55555)
    # client = GUIChatClient(root, host = 's-ia.ru', port = 5555)
    root.mainloop()
