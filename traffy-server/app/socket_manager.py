from app.api.server import ServerAPI
from xmlrpc.server import SimpleXMLRPCServer
from random import randint
import threading


class SocketManager():
    run = True
    server = NotImplemented
    rpc = NotImplemented
    user_api = NotImplemented
    admin_api = NotImplemented

    def __init__(self, server):
        self.server = server

    def start(self):
        thread = threading.Thread(target=self.__server_start, args=[])
        thread.daemon = True
        thread.start()

    def stop(self):
        self.run = False
        self.rpc.shutdown()
        self.rpc.server_close()

    def __server_start(self):
        while self.run:
            self.server_api = ServerAPI(self.server)
            self.rpc = SimpleXMLRPCServer(addr=("127.0.0.1", 40404), allow_none=True)
            self.rpc.register_instance(self.server_api)
            self.rpc.serve_forever()

