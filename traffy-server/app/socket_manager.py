"""
 Copyright (C) 2020 Falk Seidl <hi@falsei.de>
 
 Author: Falk Seidl <hi@falsei.de>
 
 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as
 published by the Free Software Foundation; either version 2 of the
 License, or (at your option) any later version.
 
 This program is distributed in the hope that it will be useful, but
 WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.
 
 You should have received a copy of the GNU General Public License
 along with this program; if not, see <http://www.gnu.org/licenses/>.
"""

from app.api.server import ServerAPI
from xmlrpc.server import SimpleXMLRPCServer
from random import randint
import threading


class SocketManager():
    run = True
    server = NotImplemented
    rpc = NotImplemented
    server_api = NotImplemented

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

