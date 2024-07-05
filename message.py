import enum
import struct
import socket

class MsgType(enum.Enum):
    none         = enum.auto()
    srv_shutdown = enum.auto()
    ban          = enum.auto()
    usersinfo    = enum.auto()
    empty        = enum.auto()


class NothingReceived(Exception):
    pass

def send_message(sock, msg, msg_type = MsgType.none):
    body = msg.encode('utf8')
    header = struct.pack('<IB', len(body), msg_type.value)
    sock.sendall(header + body)

def receive_message(sock):
    header = sock.recv(5)
    if not header:
        return MsgType.empty, ""

    length, msg_type_code = struct.unpack('<IB', header)
    try:
        msg_type = MsgType(msg_type_code)
    except ValueError:
        raise ValueError('Invalid message type')

    buf_size = 8192
    received_bytes = 0
    data = bytes()
    while received_bytes + buf_size < length:
        buf = sock.recv(buf_size)
        if not buf:
            return MsgType.empty, ""
        data += buf
        received_bytes += buf_size

    if length > 0 and received_bytes != length:
        buf = sock.recv(length - received_bytes)
        if not buf:
            return MsgType.empty, ""
        data += buf

    return msg_type, data.decode('utf8')



