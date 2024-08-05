import socket
import threading
import signal
import sys
import re
import os
#import time
from datetime import datetime

from message import *

class User:
    count = 0
    users = {}

    def __init__(self, name, sock):
        self.name = name
        self.sock = sock
        self.id = User.count
        User.count += 1
        User.users[self.id] = self

    def __str__(self):
        return self.name

    @classmethod
    def list(cls):
        return User.users.values()

    @classmethod
    def names(cls):
        return map(lambda x: x.name, User.list())

    @classmethod
    def get_user_by_id(cls, user_id):
        return User.users.get(user_id)

    @classmethod
    def remove_user(cls, user):
        del User.users[user.id]

class ChatServer:
    class InvalidMessage(Exception):
        def __init__(self, message = None):
            if not message:
                message = 'Received unexpected message'
            super().__init__(message)
    
    class InvalidMessageType(InvalidMessage):
        def __init__(self, message = None):
            if not message:
                message = 'Received message with unknown type'
            super().__init__(message)
    
    
    def __init__(self, host='0.0.0.0', port=5555):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        #self.server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.server.bind((host, port))
        self.server.listen(5)
        
        self.show_log = True
        self.hidden_log = []
        self.history = []
        
        self.files_directory = './files'
        os.makedirs(self.files_directory, exist_ok=True)
        self.files = {}
        self.files_count = 0
        
        self.shared_buffer = ""
        self.shared_edit_users = set()
        self.active_editor = None
        
        signal.signal(signal.SIGINT, self.shutdown)
        self.log(f"Server started on port {port}")

    def log(self, text, must_show=False):
        text = f'{datetime.now().strftime("%H:%M:%S")}    {text}'
        if must_show or self.show_log:
            print(text)
        else:
            self.hidden_log.append(text)
    
    def show_hidden_log(self):
        for msg in self.hidden_log:
            print(msg)

    def broadcast(self, message, msg_type=MsgType.CHATMSG, inbytes=False):
        self.history.append((message, msg_type))

        for user in User.list():
            try:
                if inbytes:
                    send_byte_message(user.sock, message, msg_type)
                else:
                    send_message(user.sock, message, msg_type)
                    
                # self.log(f'Sent message "{message}" ({msg_type.name}) to {user}')
            except Exception as e:
                self.log(f'Error broadcasting to {user}: {e}')
                self.remove_client(user)

        self.log(f'Sent message "{message}" ({msg_type.name})')

    def remove_client(self, user, banned=False):
        if user.id in User.users:
            if not banned:
                msg = self.pack_special_message((SpecElems.USER, str(user)),
                                                (SpecElems.TXT, ' has left the chat'))
            else:
                msg = self.pack_special_message((SpecElems.USER, str(user)),
                                                (SpecElems.TXT, ' was banned'))

            user.sock.close()
            if user in self.shared_edit_users:
                self.shared_edit_users.remove(user)
            if user is self.active_editor:
                self.active_editor = None
                self.send_capture_info()
            
            User.remove_user(user)
            self.broadcast(msg, MsgType.SPECIAL)
            self.log(f'{user} removed')

    def handle_client(self, client_socket):
        username = self.set_username(client_socket)
        if username is None:
            self.log('New user not added')
            client_socket.close()
            return
        
        
        user = User(username, client_socket)
        self.log(f'New user added: {user}')
        for msg, msg_type in self.history:
            send_message(user.sock, msg, msg_type)
        msg = self.pack_special_message((SpecElems.USER, str(user)),
                                        (SpecElems.TXT, ' has joined the chat!'))
        self.broadcast(msg, MsgType.SPECIAL)
        

        while True:
            try:
                msg_type, message = receive_message(user.sock)
                #self.log(f'Received message "{message}" ({msg_type.name}) from {user}')
                if msg_type == MsgType.CHATMSG:
                    if message:
                        self.broadcast(f'{user.name}\0{message}')
                elif msg_type == MsgType.USERSINFO:
                    answer = "\0".join(User.names())
                    send_message(user.sock, answer, MsgType.USERSINFO)
                elif msg_type == MsgType.PUT_FILE:
                    self.receive_file(user, message)
                elif msg_type == MsgType.GET_FILE:
                    self.send_filelist(user)
                    _, fileid = receive_message(user.sock)
                    if not fileid:
                        self.log('Stopped file sending procedure')
                        continue
                    self.send_file(user, fileid)
                elif msg_type == MsgType.SHARED_EDIT:
                    self.handle_shared_edit_requests(user, message)
                        
                else:
                    raise ChatServer.InvalidMessageType
                
            except Empty:
                self.log(f'Connection with "{user}" lost')
                self.remove_client(user)
                break
            except Exception as e:
                self.log(f'Catched exception while handling user "{user}": {e}')
                self.remove_client(user)
                break

    def check_username(self, username):
        pattern = r'^[a-zA-Z0-9_-]+$'
        return 1 <= len(username) <= 30 and re.match(pattern, username) is not None

    def set_username(self, client_socket):
        while True:
            t, username = receive_message(client_socket, throw_empty=False)
            if t == MsgType.EMPTY or not username:
                client_socket.close()
                return None
            if not self.check_username(username):
                send_message(client_socket, '2')
            elif username in User.names() or username == 'admin':
                send_message(client_socket, '1')
            else:
                send_message(client_socket, '0')
                return username
    
    def pack_special_message(self, *elems):
        message = "\31".join(f'{t}\31{x}' for t, x in elems)
        return message
    
    def send_shared_edit_message(self, msg, user = None, excepting = None):
        if user is None:
            for u in self.shared_edit_users:
                if u is not self.active_editor or u is excepting:
                    send_message(u.sock, msg, MsgType.SHARED_EDIT)
        else:
            send_message(user.sock, msg, MsgType.SHARED_EDIT)
    
    def send_capture_info(self, user = None, excepting = None):
        if self.active_editor is None:
            self.send_shared_edit_message("0", user, excepting)
        else:
            self.send_shared_edit_message(f"1{self.active_editor.name}", user, excepting)
    
    def send_shared_buffer(self, user = None, excepting=None):
        self.send_shared_edit_message("2"+self.shared_buffer, user, excepting)
    
    def handle_shared_edit_requests(self, user, message):
        if not message:
            send_message(user.sock, "You have sent invalid message", MsgType.ERROR)
            raise ChatServer.InvalidMessage
        
        operation, data = message[0], message[1:]
        if operation == "0":
            if user not in self.shared_edit_users:
                self.log(f"{user} wants to open shared edit")
                self.shared_edit_users.add(user)
                self.send_capture_info(user)
                self.send_shared_buffer(user)
                
                msg = self.pack_special_message((SpecElems.USER, str(user)),
                                        (SpecElems.TXT, ' started editing shared buffer'))
                
                self.broadcast(msg, MsgType.SPECIAL)
            else:
                self.shared_edit_users.remove(user)
                if user is self.active_editor:
                    self.active_editor = None
                    self.send_capture_info()
                msg = self.pack_special_message((SpecElems.USER, str(user)),
                                        (SpecElems.TXT, ' stopped editing shared buffer'))
                self.broadcast(msg, MsgType.SPECIAL)
        elif operation == "1":
            if user is self.active_editor:
                self.log(f'{user} released editor')
                self.active_editor = None
                self.send_capture_info(excepting=user)
            else:
                self.log(f'{user} captured editor')
                self.active_editor = user
                self.send_capture_info()
        
        elif operation == "2":
            if user is self.active_editor:
                self.shared_buffer = data
                self.send_shared_buffer()
            else:
                send_message(user.sock, "You are not allowed to update shared edit buffer", MsgType.ERROR)
            
            
    def receive_file(self, user, filename):
        t, data = receive_byte_message(user.sock)
        if t == MsgType.ERROR:
            self.log('Stopped file getting procedure')
            return
        try:
            fileid = self.add_file(filename, data)
        except OSError:
            send_message(user.sock, "Your file was not saved", MsgType.ERROR)
        else:
            msg = self.pack_special_message((SpecElems.USER, str(user)),
                                            (SpecElems.TXT, ' uploaded file '),
                                            (SpecElems.FILE, filename),
                                            (SpecElems.TXT, f' ({fileid})'))
            self.broadcast(msg, MsgType.SPECIAL)
    
    def add_file(self, filename, data):
        fileid = str(self.files_count)
        with open(f'{self.files_directory}/id{fileid}', 'wb') as f:
            f.write(data)
            
        self.files[fileid] = filename
        self.files_count += 1
        
        return fileid
    
    def send_filelist(self, user):
        msg = "\0".join(f'{i}\0{f}' for i, f in self.files.items())
        send_message(user.sock, msg, MsgType.GET_FILE)
        self.log(f'Filelist: {repr(msg)}')
        self.log(f'Sent file list to {user}')
    
    def send_file(self, user, fileid):
        self.log(f'{user} asks to get file #{fileid}')
        if fileid in self.files:
            try:
                with open(f'{self.files_directory}/id{fileid}', 'rb') as f:
                    data = f.read()
                    send_byte_message(user.sock, data)
                    self.log(f'Sent file #{fileid} to "{user}"')
            except IOError:
                send_byte_message(user.sock, b'', MsgType.ERROR)
        else:
            send_byte_message(user.sock, b'', MsgType.ERROR)

    def start(self):
        threading.Thread(target=self.exec_commands, daemon=True).start()
        while True:
            try:
                client_socket, addr = self.server.accept()
                self.log(f"Accepted connection from {addr}")
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
                
            except ConnectionResetError as e:
                self.log(f'Connection reset error: {e}')
                continue

    def exec_commands(self):
        while True:
            try:
                cmd = input('>>').strip()
                if not cmd:
                    continue
                cmd, *args = re.split(r'\s+', cmd)

                if cmd == 'send':
                    text = input('Message: ')
                    self.broadcast(f'admin\0{text}')

                elif cmd == 'sendto' and args:
                    user_id = int(args[0])
                    user = User.get_user_by_id(user_id)
                    if user:
                        text = input('Message: ')
                        send_message(user.sock, f'admin (only for you)\0{text}', MsgType.CHATMSG)
                    else:
                        print(f'User with id {user_id} does not exist')

                elif cmd == 'users':
                    for user in User.list():
                        print(f'{user.id}: {user}')

                elif cmd == 'kill' and args:
                    user_id = int(args[0])
                    user = User.get_user_by_id(user_id)
                    if user:
                        send_message(user.sock, "", MsgType.BAN)
                        self.remove_client(user, banned=True)
                    else:
                        print(f'User with id {user_id} does not exist')

                elif cmd == 'clear':
                    if os.name == 'posix':
                        os.system('clear')
                    elif os.name == 'nt':
                        os.system('cls')

                elif cmd == 'log':
                    if self.show_log:
                        self.show_log = False
                    else:
                        self.show_log = True
                        self.show_hidden_log()
                        
                elif cmd == 'files':
                    for i, file in self.files.items():
                        print(f'{i}: {file}')
                
                elif cmd == 'load':
                    filename = input('Enter filename: ')
                    with open(filename, "rb") as f:
                        data = f.read()
                    
                    fileid = self.add_file(os.path.basename(filename), data)
                    msg = self.pack_special_message((SpecElems.USER, 'admin'),
                                            (SpecElems.TXT, ' uploaded file '),
                                            (SpecElems.FILE, filename),
                                            (SpecElems.TXT, f'({fileid})'))
                    self.broadcast(msg, MsgType.SPECIAL)
                    
                elif cmd == 'rm' and args:
                    fileid = args[0]
                    if fileid not in self.files:
                        print(f'File with id {fileid} does not exist')
                    os.remove(f'{self.files_directory}/id{fileid}')
                    self.log(f'File #{fileid} was removed')
                    filename = self.files.pop(fileid)
                    msg = self.pack_special_message((SpecElems.USER, 'admin'),
                                            (SpecElems.TXT, ' removed file '),
                                            (SpecElems.FILE, filename),
                                            (SpecElems.TXT, f'({fileid})'))
                    self.broadcast(msg, MsgType.SPECIAL)
                    

                else:
                    print('Unknown command')

            except Exception as e:
                self.log(f'Exception in exec_commands(): {e}')
                continue

    def shutdown(self, signum, frame):
        self.log("Shutting down server...")
        for user in list(User.list()):
            try:
                send_message(user.sock, "", MsgType.SRV_SHUTDOWN)
                user.sock.close()
            except Exception as e:
                self.log(f'Error shutting down user {user}: {e}')
                continue
        self.server.close()
        sys.exit(0)

if __name__ == "__main__":
    server = ChatServer()
    server.start()
