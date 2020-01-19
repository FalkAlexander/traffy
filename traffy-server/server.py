from app.database_manager import DatabaseManager
from app.socket_manager import SocketManager
from app.models import RegistrationKey, IpAddress, MacAddress, AddressPair
from app.util import iptables_rules_manager, iptables_accounting_manager, shaping_manager, arp_manager
from datetime import datetime
from app.accounting_manager import AccountingService
from app.util.dnsmasq_manager import DnsmasqService
import os
import logging
import threading
import config
import signal
import sys


class Server():
    boot_timestamp = NotImplemented
    thread_count = 0
    db = NotImplemented
    dnsmasq_srv = NotImplemented
    accounting_srv = NotImplemented
    sm = NotImplemented

    def __init__(self):
        self.boot_timestamp = datetime.now()
        self.setup_logging()
        self.init_configs()
        self.db = DatabaseManager()

        self.dnsmasq_srv = DnsmasqService()
        self.accounting_srv = AccountingService(self.db)
        self.sm = SocketManager(self)

        signal.signal(signal.SIGINT, self.shutdown)
        self.startup()
        signal.pause()

    def setup_logging(self):
        logging.basicConfig(format="[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S %z", level=logging.INFO)

    def init_configs(self):
        configs = [config.DNSMASQ_CONFIG_FILE, config.DNSMASQ_HOSTS_FILE, config.DNSMASQ_LEASE_FILE]

        for cfile in configs:
            if not os.path.exists(os.path.dirname(cfile)):
                try:
                    os.makedirs(os.path.dirname(cfile))
                except e:
                    raise

            if not os.path.exists(cfile):
                try:
                    open(cfile, "a").close()
                except e:
                    raise

    def firewall_unlock_registered_devices(self):
        address_column = self.db.session.query(IpAddress.address_v4).all()
        for row in address_column:
            # thread = threading.Thread(target=self.__unlock_device_thread, args=[row])
            # thread.daemon = True
            # thread.start()
            # thread.join()
            self.__unlock_device_thread(row)

    def __unlock_device_thread(self, row):
        ip_address = row[0]
        ip_address_query = self.db.session.query(IpAddress).filter_by(address_v4=ip_address).first()
        address_pair_query = self.db.session.query(AddressPair).filter_by(ip_address=ip_address_query.id).first()
        reg_key_query = self.db.session.query(RegistrationKey).filter_by(id=address_pair_query.reg_key).first()
        if reg_key_query.active is True:
            iptables_rules_manager.unlock_registered_device(ip_address)

    def firewall_relock_unregistered_devices(self):
        address_column = self.db.session.query(IpAddress.address_v4).all()
        #address_column = IpAddress.query.with_entities(IpAddress.address_v4).all()
        for row in address_column:
            # thread = threading.Thread(target=self.__relock_device_thread, args=[row])
            # thread.daemon = True
            # thread.start()
            # thread.join()
            self.__relock_device_thread(row)

    def __relock_device_thread(self, row):
        ip_address = row[0]
        ip_address_query = self.db.session.query(IpAddress).filter_by(address_v4=ip_address).first()
        #ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
        address_pair_query = self.db.session.query(AddressPair).filter_by(ip_address=ip_address_query.id).first()
        #address_pair_query = AddressPair.query.filter_by(ip_address=ip_address_query.id).first()
        reg_key_query = self.db.session.query(RegistrationKey).filter_by(id=address_pair_query.reg_key).first()
        #reg_key_query = RegistrationKey.query.filter_by(id=address_pair_query.reg_key).first()
        if reg_key_query.active is True:
            iptables_rules_manager.relock_registered_device(ip_address)

    def setup_accounting_chains(self):
        address_pair_query = self.db.session.query(AddressPair.reg_key).filter(AddressPair.reg_key).distinct()
        for reg_key_fk in address_pair_query:
            if reg_key_fk is None:
                continue

            #reg_key_query = RegistrationKey.query.filter_by(id=reg_key_fk.reg_key).first()
            reg_key_query = self.db.session.query(RegistrationKey).filter_by(id=reg_key_fk.reg_key).first()
            if reg_key_query is None:
                continue

            if reg_key_query.active is True:
                iptables_accounting_manager.add_accounter_chain(reg_key_query.id)

        address_pair_query = self.db.session.query(AddressPair.ip_address).filter(AddressPair.ip_address).distinct()
        for ip_address_fk in address_pair_query:
            if ip_address_fk is None:
                continue

            #ip_address_query = IpAddress.query.filter_by(id=ip_address_fk.ip_address).first()
            ip_address_query = self.db.session.query(IpAddress).filter_by(id=ip_address_fk.ip_address).first()
            if ip_address_query is None:
                continue

            #address_pair_query = AddressPair.query.filter_by(ip_address=ip_address_fk.ip_address).first()
            address_pair_query = self.db.session.query(AddressPair).filter_by(ip_address=ip_address_fk.ip_address).first()
            #reg_key_query = RegistrationKey.query.filter_by(id=address_pair_query.reg_key).first()
            reg_key_query = self.db.session.query(RegistrationKey).filter_by(id=address_pair_query.reg_key).first()
            #ip_address_query = IpAddress.query.filter_by(id=address_pair_query.ip_address).first()
            ip_address_query = self.db.session.query(IpAddress).filter_by(id=address_pair_query.ip_address).first()

            if reg_key_query.active is True:
                iptables_accounting_manager.add_ip_to_box(reg_key_query.id, ip_address_query.address_v4)
            # Spoofing Protection
            #mac_address_query = MacAddress.query.filter_by(id=address_pair_query.mac_address).first()
            mac_address_query = self.db.session.query(MacAddress).filter_by(id=address_pair_query.mac_address).first()
            arp_manager.add_static_arp_entry(ip_address_query.address_v4, mac_address_query.address)

    def remove_accounting_chains(self):
        address_pair_query = self.db.session.query(AddressPair.ip_address).filter(AddressPair.ip_address).distinct()
        for ip_address_fk in address_pair_query:
            # thread = threading.Thread(target=self.__remove_ip_thread, args=[ip_address_fk])
            # thread.daemon = False
            # thread.start()
            # self.thread_count += 1
            self.__remove_ip_thread(ip_address_fk)

        address_pair_query = self.db.session.query(AddressPair.reg_key).filter(AddressPair.reg_key).distinct()
        for reg_key_fk in address_pair_query:
            if reg_key_fk is None:
                continue

            #reg_key_query = RegistrationKey.query.filter_by(id=reg_key_fk.reg_key).first()
            reg_key_query = self.db.session.query(RegistrationKey).filter_by(id=reg_key_fk.reg_key).first()
            if reg_key_query is None:
                continue

            if reg_key_query.active is True:
                iptables_accounting_manager.remove_accounter_chain(reg_key_query.id)

    def __remove_ip_thread(self, ip_address_fk):
        if ip_address_fk is None:
            return

        #ip_address_query = IpAddress.query.filter_by(id=ip_address_fk.ip_address).first()
        ip_address_query = self.db.session.query(IpAddress).filter_by(id=ip_address_fk.ip_address).first()
        if ip_address_query is None:
            return

        #address_pair_query = AddressPair.query.filter_by(ip_address=ip_address_fk.ip_address).first()
        address_pair_query = self.db.session.query(AddressPair).filter_by(ip_address=ip_address_fk.ip_address).first()
        #reg_key_query = RegistrationKey.query.filter_by(id=address_pair_query.reg_key).first()
        reg_key_query = self.db.session.query(RegistrationKey).filter_by(id=address_pair_query.reg_key).first()
        #ip_address_query = IpAddress.query.filter_by(id=address_pair_query.ip_address).first()
        ip_address_query = self.db.session.query(IpAddress).filter_by(id=address_pair_query.ip_address).first()

        if reg_key_query.active is True:
            iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address_query.address_v4)
        # Spoofing Protection
        arp_manager.remove_static_arp_entry(ip_address_query.address_v4)
        self.thread_count = self.thread_count - 1

    def shutdown(self, signal, frame):
        self.sm.stop()

        # Stop Accounting
        #self.accounting_srv.stop()

        # Stop dnsmasq
        self.dnsmasq_srv.stop()

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

        # Shutdown Shaping
        shaping_manager.shutdown_shaping()

        logging.info("Network not managed anymore")

    def startup(self):
        # Start dnsmasq
        self.dnsmasq_srv.start()

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
        #self.accounting_srv.start(10)
        logging.info("Started accounting services")

        self.sm.start()

        logging.info("Network now fully managed")
        logging.info("Traffy server ready after " + str((datetime.now() - self.boot_timestamp).total_seconds()) + "s")


server = Server()

