import enum
import struct
import zlib


class MsgType(enum.Enum):
    NONE = enum.auto()
    CHATMSG = enum.auto()
    SPECIAL = enum.auto()
    ERROR = enum.auto()
    SRV_SHUTDOWN = enum.auto()
    BAN = enum.auto()
    USERSINFO = enum.auto()
    PUT_FILE = enum.auto()
    GET_FILE = enum.auto()
    SHARED_EDIT = enum.auto()
    EMPTY = enum.auto()

class SpecElems:
    TXT  = 't'
    USER = 'u'
    FILE = 'f'


class Empty(Exception):
    pass


def send_byte_message(sock, data, msg_type=MsgType.NONE):
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
            return MsgType.EMPTY, b""
        header.extend(chunk)

    length, msg_type_code = struct.unpack('<IB', header)

    try:
        msg_type = MsgType(msg_type_code)
    except ValueError as e:
        raise ValueError('Invalid message type') from e

    buf_size = 2048
    data = bytearray()
    while len(data) < length:
        to_read = min(buf_size, length - len(data))
        buf = sock.recv(to_read)
        if not buf:
            if throw_empty:
                raise Empty
            return MsgType.EMPTY, b""
        data.extend(buf)

    data = zlib.decompress(data)
    return msg_type, data


def send_message(sock, msg, msg_type=MsgType.NONE, encoding='utf8'):
    send_byte_message(sock, msg.encode(encoding), msg_type)


def receive_message(sock, throw_empty=True, encoding='utf8'):
    msg_type, data = receive_byte_message(sock, throw_empty)
    return msg_type, data.decode(encoding)
