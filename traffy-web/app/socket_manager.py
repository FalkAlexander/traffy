import socket
from xmlrpc.client import ServerProxy


class SocketManager():
    server = NotImplemented

    def __init__(self):
        socket.setdefaulttimeout(30)
        self.server = ServerProxy(uri="http://127.0.0.1:40404/", allow_none=True)

