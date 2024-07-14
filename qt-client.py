import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QTextEdit, QPushButton, QMessageBox, QFileDialog, QMenuBar, QAction, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence

from base_client import ThreadSafeChatClient, thread_safe

@thread_safe
class GUIChatClient(ThreadSafeChatClient):
    def _wrapper(self, func, *args, **kwargs):
       return lambda *l_args, **l_kwargs: func(*args, **kwargs)
    
    def __init__(self, host='localhost', port=5555):
        super().__init__(host, port)
        
        self.app = QApplication(sys.argv)
        self.app.setFont(QFont('Arial', 13))
        self.window = QWidget()
        self.window.setWindowTitle("Chat Client")
        self.window.resize(800, 600)
        # self.window.setFont(QFont('Arial', 13))
        self.layout = QVBoxLayout()

        self.create_menu()
        self.create_chat_interface()
        self.create_input_interface()
        
        self.start()

        self.window.setLayout(self.layout)
        self.window.show()
        sys.exit(self.app.exec_())
    
    def on_login_done(self):
        self.input_area.setFocus()
    
    def schedule(self, call, now = False):
        self.timer = QTimer()
        self.timer.timeout.connect(call)
        if now:
            self.timer.start(0)
        else:
            self.timer.start(100)


    def create_menu(self):
        self.menu_bar = QMenuBar(self.window)
        self.layout.setMenuBar(self.menu_bar)

        exit_action = QAction("Exit", self.window)
        exit_action.triggered.connect(self._wrapper(self.quit))
        exit_action.setShortcut(QKeySequence('Ctrl+Q'))
        self.menu_bar.addAction(exit_action)

        users_info_action = QAction("Users Online Info", self.window)
        users_info_action.triggered.connect(self._wrapper(self.get_usersinfo))
        users_info_action.setShortcut(QKeySequence('Ctrl+O'))
        self.menu_bar.addAction(users_info_action)

        upload_file_action = QAction("Upload File", self.window)
        upload_file_action.triggered.connect(self._wrapper(self.upload_file))
        upload_file_action.setShortcut(QKeySequence('Ctrl+P'))
        self.menu_bar.addAction(upload_file_action)

        download_file_action = QAction("Download File", self.window)
        download_file_action.triggered.connect(self._wrapper(self.download_file))
        download_file_action.setShortcut(QKeySequence('Ctrl+G'))
        self.menu_bar.addAction(download_file_action)

    def create_chat_interface(self):
        self.chat_label = QLabel("Chat:")
        self.layout.addWidget(self.chat_label)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.layout.addWidget(self.text_area)

    def create_input_interface(self):
        self.msg_label = QLabel("Message:")
        self.layout.addWidget(self.msg_label)

        self.input_area = QTextEdit()
        self.input_area.setFixedHeight(50)
        self.layout.addWidget(self.input_area)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.write)
        self.send_button.setShortcut(QKeySequence('Ctrl+S'))
        self.layout.addWidget(self.send_button)
    
    
    def askusername(self, is_used=False, is_not_valid=False):
        prompt = "Enter username"
        if is_used:
            prompt = f'Username "{self.username}" is already used. Please try again'
        elif is_not_valid:
            prompt = f'Username "{self.username}" is not valid. Please try again'
        self.username, ok = QInputDialog.getText(self.window, "Username", prompt)
        if not ok or not self.username:
            self.username = ""

    def display_message(self, user, message):
        self.text_area.append(f'<span style="color: blue;"><b>{user}> </b></span> {message}')

    def display_special_message(self, message):
        self.text_area.append(f'<span style="color: green;"><b>{message}</b></span>')

    def display_info(self, text):
        QMessageBox.information(self.window, "Information", text)
 
    def display_error(self, text):
        QMessageBox.critical(self.window, "Error", text)

    def write(self):
        message = self.input_area.toPlainText().strip()
        self.send_chatmessage(message)
        self.input_area.clear()

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self.window, "Open a file", "", "All Files (*)")
        return file_path if file_path else None

    def save_file(self, default_name):
        file_path, _ = QFileDialog.getSaveFileName(self.window, "Save a file", default_name, "All Files (*)")
        return file_path if file_path else None

    def select_file(self, filenames):
        res, ok = QInputDialog.getItem(self.window, "Select file to download", "Files", filenames, 0, False)
        return filenames.index(res) if ok else -1

    def prepare_quit(self):
        self.app.quit()

if __name__ == "__main__":
    client = GUIChatClient()
