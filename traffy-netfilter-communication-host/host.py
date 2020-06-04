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

from socket_manager import SocketManager
from datetime import datetime
import logging
import signal
import os


class Host():
    boot_timestamp = NotImplemented
    sm = NotImplemented

    def __init__(self):
        self.setup_logging()

        if os.geteuid() != 0:
            logging.error("Need to run as root! Exiting…")
            return

        self.boot_timestamp = datetime.now()

        self.sm = SocketManager(self)

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        self.startup()
        signal.pause()
    
    def setup_logging(self):
        logging.basicConfig(format="[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S %z", level=logging.INFO)
    
    def shutdown(self, signal, frame):
        # Disable Socket
        self.sm.stop()

        logging.info("Traffy netfilter communication host powered off")

    def startup(self):
        # Enable Socket
        self.sm.start()

        logging.info("Traffy netfilter communication host ready to listen")
        logging.info("Traffy netfilter communication host ready after " + str((datetime.now() - self.boot_timestamp).total_seconds()) + "s")

host = Host()
