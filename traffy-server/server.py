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

from app.database_manager import DatabaseManager
from app.socket_manager import SocketManager
from app.models import RegistrationKey, IpAddress, MacAddress, AddressPair
from app.tests.dev_mode import DevModeTest
from app.util import shaping_manager, arp_manager, nftables_manager
from app.util.mail_helper import MailHelper
from datetime import datetime
from app.accounting_manager import AccountingService
from app.housekeeping_service import HousekeepingService
import os
import logging
import threading
import config
import signal
import sys


class Server():
    boot_timestamp = NotImplemented
    db = NotImplemented
    mail_helper = NotImplemented
    accounting_srv = NotImplemented
    sm = NotImplemented
    dev_mode_test = NotImplemented
    housekeeping_srv = NotImplemented

    def __init__(self):
        self.boot_timestamp = datetime.now()
        self.setup_logging()
        self.db = DatabaseManager()

        self.mail_helper = MailHelper()
        self.accounting_srv = AccountingService(self.db, self.mail_helper)
        self.housekeeping_srv = HousekeepingService(self.db)
        self.sm = SocketManager(self)

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
        self.startup()
        signal.pause()

    def setup_logging(self):
        logging.basicConfig(format="[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S %z", level=logging.INFO)

    def unlock_registered_devices(self):
        session = self.db.create_session()
        ip_address_query = session.query(IpAddress).all()

        registered_devices = []
        for address in ip_address_query:
            address_pair_query = session.query(AddressPair).filter_by(ip_address=address.id).first()
            reg_key_query = session.query(RegistrationKey).filter_by(id=address_pair_query.reg_key).first()
            if reg_key_query.active is True:
                registered_devices.append(address.address_v4)
        
        if len(registered_devices) != 0:
            nftables_manager.add_ips_to_registered_set(registered_devices)

        session.close()

    def setup_accounting_rules(self):
        session = self.db.create_session()
        address_pair_query = session.query(AddressPair.reg_key).filter(AddressPair.reg_key).distinct()
        for reg_key_fk in address_pair_query:
            if reg_key_fk is None:
                return

            reg_key_query = session.query(RegistrationKey).filter_by(id=reg_key_fk.reg_key).first()
            if reg_key_query is None:
                return

            if reg_key_query.active is True:
                nftables_manager.add_reg_key_set(reg_key_query.id)

                query = session.query(AddressPair.ip_address).filter_by(reg_key=reg_key_fk.reg_key).distinct()

                for ip_address_fk in query:
                    if ip_address_fk is None:
                        return

                    ip_address_query = session.query(IpAddress).filter_by(id=ip_address_fk.ip_address).first()
                    if ip_address_query is None:
                        return

                    address_pair_query = session.query(AddressPair).filter_by(ip_address=ip_address_fk.ip_address).first()
                    ip_address_query = session.query(IpAddress).filter_by(id=address_pair_query.ip_address).first()

                    nftables_manager.add_ip_to_reg_key_set(ip_address_query.address_v4, reg_key_query.id)

                    # Spoofing Protection
                    mac_address_query = session.query(MacAddress).filter_by(id=address_pair_query.mac_address).first()
                    arp_manager.add_static_arp_entry(ip_address_query.address_v4, mac_address_query.address)

                nftables_manager.add_accounting_matching_rules(reg_key_query.id)

        session.close()

    def shutdown(self, signal, frame):
        # Stop Housekeeping
        if not config.STATELESS:
            self.housekeeping_srv.stop()

        # Disable Socket
        self.sm.stop()

        if not config.STATELESS:
            # Stop Accounting
            #self.accounting_srv.stop()

            # Shutdown Shaping
            shaping_manager.shutdown_shaping()

            # Clear traffy table
            nftables_manager.delete_traffy_table()

            logging.info("Network not managed anymore")

    def startup(self):
        if not config.STATELESS:
            # Setup shaping
            shaping_manager.setup_shaping()

            # Setup basic requirements
            nftables_manager.setup_base_configuration()

            # Setup captive portal routing
            nftables_manager.setup_captive_portal_configuration()
            self.unlock_registered_devices()

            # Setup accounting requirements
            logging.info("Preparing accounting…")
            nftables_manager.setup_accounting_configuration()
            self.setup_accounting_rules()
            logging.info("Finished preparing accounting")

            # Start accounting manager            
            #self.accounting_srv.start(10)
            logging.info("Started accounting services")

            self.dev_mode_test = DevModeTest(self.db)

        # Enable Socket
        self.sm.start()

        # Start Housekeeping
        if not config.STATELESS:
            self.housekeeping_srv.start(20, self.sm.server_api)

        logging.info("Network now fully managed")
        logging.info("Traffy server ready after " + str((datetime.now() - self.boot_timestamp).total_seconds()) + "s")


server = Server()

