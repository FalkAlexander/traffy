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
from app.util import iptables_rules_manager, iptables_accounting_manager, shaping_manager, arp_manager
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

    def firewall_unlock_registered_devices(self):
        session = self.db.create_session()
        address_column = session.query(IpAddress.address_v4).all()
        for row in address_column:
            thread = threading.Thread(target=self.__unlock_device_thread, args=[row])
            thread.daemon = True
            thread.start()
            thread.join()

        session.close()

    def __unlock_device_thread(self, row):
        session = self.db.create_session()
        ip_address = row[0]
        ip_address_query = session.query(IpAddress).filter_by(address_v4=ip_address).first()
        address_pair_query = session.query(AddressPair).filter_by(ip_address=ip_address_query.id).first()
        reg_key_query = session.query(RegistrationKey).filter_by(id=address_pair_query.reg_key).first()
        if reg_key_query.active is True:
            iptables_rules_manager.unlock_registered_device(ip_address)
        session.close()

    def firewall_relock_unregistered_devices(self):
        session = self.db.create_session()
        address_column = session.query(IpAddress.address_v4).all()
        for row in address_column:
            thread = threading.Thread(target=self.__relock_device_thread, args=[row])
            thread.daemon = True
            thread.start()
            thread.join()

        session.close()

    def __relock_device_thread(self, row):
        session = self.db.create_session()
        ip_address = row[0]
        ip_address_query = session.query(IpAddress).filter_by(address_v4=ip_address).first()
        address_pair_query = session.query(AddressPair).filter_by(ip_address=ip_address_query.id).first()
        reg_key_query = session.query(RegistrationKey).filter_by(id=address_pair_query.reg_key).first()
        if reg_key_query.active is True:
            iptables_rules_manager.relock_registered_device(ip_address)
        session.close()

    def setup_accounting_chains(self):
        session = self.db.create_session()
        address_pair_query = session.query(AddressPair.reg_key).filter(AddressPair.reg_key).distinct()
        for reg_key_fk in address_pair_query:
            thread = threading.Thread(target=self.__add_accounter_chain, args=[reg_key_fk])
            thread.daemon = True
            thread.start()
            thread.join()

        session.close()

    def __add_accounter_chain(self, reg_key_fk):
        session = self.db.create_session()

        if reg_key_fk is None:
            return

        reg_key_query = session.query(RegistrationKey).filter_by(id=reg_key_fk.reg_key).first()
        if reg_key_query is None:
            return

        if reg_key_query.active is True:
            iptables_accounting_manager.add_accounter_chain(reg_key_query.id)

            query = session.query(AddressPair.ip_address).filter_by(reg_key=reg_key_fk.reg_key).distinct()

            for ip_address_fk in query:
                if ip_address_fk is None:
                    return

                ip_address_query = session.query(IpAddress).filter_by(id=ip_address_fk.ip_address).first()
                if ip_address_query is None:
                    return

                address_pair_query = session.query(AddressPair).filter_by(ip_address=ip_address_fk.ip_address).first()
                ip_address_query = session.query(IpAddress).filter_by(id=address_pair_query.ip_address).first()

                iptables_accounting_manager.add_ip_to_box(reg_key_query.id, ip_address_query.address_v4)

                # Spoofing Protection
                mac_address_query = session.query(MacAddress).filter_by(id=address_pair_query.mac_address).first()
                arp_manager.add_static_arp_entry(ip_address_query.address_v4, mac_address_query.address)

        session.close()

    def remove_accounting_chains(self):
        session = self.db.create_session()
        address_pair_query = session.query(AddressPair.reg_key).filter(AddressPair.reg_key).distinct()
        for reg_key_fk in address_pair_query:
            thread = threading.Thread(target=self.__remove_accounter_chain, args=[reg_key_fk])
            thread.daemon = True
            thread.start()
            thread.join()

        session.close()

    def __remove_accounter_chain(self, reg_key_fk):
        session = self.db.create_session()

        if reg_key_fk is None:
            return

        reg_key_query = session.query(RegistrationKey).filter_by(id=reg_key_fk.reg_key).first()
        if reg_key_query is None:
            return

        if reg_key_query.active is True:
            query = session.query(AddressPair.ip_address).filter_by(reg_key=reg_key_fk.reg_key).distinct()

            for ip_address_fk in query:
                if ip_address_fk is None:
                    return

                ip_address_query = session.query(IpAddress).filter_by(id=ip_address_fk.ip_address).first()
                if ip_address_query is None:
                    return

                address_pair_query = session.query(AddressPair).filter_by(ip_address=ip_address_fk.ip_address).first()
                ip_address_query = session.query(IpAddress).filter_by(id=address_pair_query.ip_address).first()

                iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address_query.address_v4)

                # Spoofing Protection
                arp_manager.remove_static_arp_entry(ip_address_query.address_v4)

            iptables_accounting_manager.remove_accounter_chain(reg_key_query.id)

        session.close()

    def shutdown(self, signal, frame):
        # Stop Housekeeping
        self.housekeeping_srv.stop()

        # Disable Socket
        self.sm.stop()

        # Stop Accounting
        self.accounting_srv.stop()

        # Shutdown Shaping
        shaping_manager.shutdown_shaping()

        # Clear Firewall Rules
        iptables_rules_manager.apply_block_rule(delete=True)
        iptables_rules_manager.apply_redirect_rule(delete=True)
        iptables_rules_manager.apply_dns_rule(delete=True)
        self.firewall_relock_unregistered_devices()
        iptables_rules_manager.attach_traffic_to_portal(delete=True)
        iptables_rules_manager.create_portal_route(delete=True)
        iptables_rules_manager.create_portal_box(delete=True)

        logging.info("Clearing accounting chains…")
        self.remove_accounting_chains()
        logging.info("Stopped accounting services")

        logging.info("Network not managed anymore")

    def startup(self):
        # Setup Shaping
        shaping_manager.setup_shaping()

        # Apply Firewall Rules
        iptables_rules_manager.create_portal_box(delete=False)
        iptables_rules_manager.create_portal_route(delete=False)
        iptables_rules_manager.attach_traffic_to_portal(delete=False)
        iptables_rules_manager.apply_block_rule(delete=False)
        iptables_rules_manager.apply_redirect_rule(delete=False)
        iptables_rules_manager.apply_dns_rule(delete=False)
        self.firewall_unlock_registered_devices()

        # Start Accounting
        logging.info("Preparing accounting chains…")
        self.setup_accounting_chains()
        self.accounting_srv.start(10)
        logging.info("Started accounting services")

        self.dev_mode_test = DevModeTest(self.db)

        # Enable Socket
        self.sm.start()

        # Start Housekeeping
        self.housekeeping_srv.start(20, self.sm.server_api)

        logging.info("Network now fully managed")
        logging.info("Traffy server ready after " + str((datetime.now() - self.boot_timestamp).total_seconds()) + "s")


server = Server()

