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


from app.socket_manager import SocketManager
from app import tc_manager, nftables_manager
from datetime import datetime
import logging
import os
import signal


class Commander():
    boot_timestamp = NotImplemented
    sm = NotImplemented

    def __init__(self):
        self.boot_timestamp = datetime.now()
        self.setup_logging()

        self.sm = SocketManager(self)

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

        self.startup()
        signal.pause()

    def setup_logging(self):
        logging.basicConfig(format="[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S %z", level=logging.INFO)

    def shutdown(self, signal, frame):
        # Disable socket
        self.sm.stop()

        # Shutdown shaping
        tc_manager.shutdown_shaping()

        # Clear traffy table
        nftables_manager.delete_traffy_table()

        logging.info("Traffy commander powered off")

    def startup(self):
        # Setup shaping requirements
        tc_manager.setup_shaping()

        # Setup basic requirements
        nftables_manager.setup_base_configuration()

        # Prepare captive portal requirements
        nftables_manager.setup_captive_portal_configuration()

        # Prepare accounting requirements
        nftables_manager.setup_accounting_configuration()

        # Enable socket
        self.sm.start()

        logging.info("Traffy commander ready after " + str((datetime.now() - self.boot_timestamp).total_seconds()) + "s")


commander = Commander()

