import enum
import struct
import socket
import zlib


class MsgType(enum.Enum):
    none = enum.auto()
    chatmsg = enum.auto()
    special = enum.auto()
    error = enum.auto()
    srv_shutdown = enum.auto()
    ban = enum.auto()
    usersinfo = enum.auto()
    put_file = enum.auto()
    get_file = enum.auto()
    empty = enum.auto()


class Empty(Exception):
    pass


def send_byte_message(sock, data, msg_type=MsgType.none):
    body = zlib.compress(data)
    header = struct.pack('<IB', len(body), msg_type.value)
    sock.sendall(header + body)


def receive_byte_message(sock, throw_empty=True):
    header_size = 5  # Размер заголовка
    header = bytearray()
    
    # Получаем заголовок
    while len(header) < header_size:
        chunk = sock.recv(header_size - len(header))
        if not chunk:
            if throw_empty:
                raise Empty
            else:
                return MsgType.empty, b""
        header.extend(chunk)

    length, msg_type_code = struct.unpack('<IB', header)

    try:
        msg_type = MsgType(msg_type_code)
    except ValueError:
        raise ValueError('Invalid message type')

    buf_size = 2048
    data = bytearray()
    while len(data) < length:
        to_read = min(buf_size, length - len(data))
        buf = sock.recv(to_read)
        if not buf:
            if throw_empty:
                raise Empty
            else:
                return MsgType.empty, b""
        data.extend(buf)

    data = zlib.decompress(data)
    return msg_type, data


def send_message(sock, msg, msg_type=MsgType.none, encoding='utf8'):
    send_byte_message(sock, msg.encode(encoding), msg_type)


def receive_message(sock, throw_empty=True, encoding='utf8'):
    msg_type, data = receive_byte_message(sock, throw_empty)
    return msg_type, data.decode(encoding)
