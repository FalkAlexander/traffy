from .. import db
from ..user import user_functions
from ..models import RegistrationKey, Traffic, Identity, IpAddress
from ..util import generate_registration_key
from datetime import datetime
import config
import random
import string
import time


class DevModeTest():
    def add_reg_key(self):
        self.__build_reg_key(self.__generate_random_name(),
                           self.__generate_random_name(),
                           self.__generate_random_mail())

    def register_device(self, reg_key_query, request):
        self.__build_device(reg_key_query.key, self.__generate_random_ip(), request)

    def __build_reg_key(self, first_name, surname, mail):
        db.session.add(Identity(first_name=first_name, last_name=surname, mail=mail))
        identity = Identity.query.filter_by(first_name=first_name, last_name=surname, mail=mail).first()
        reg_key = generate_registration_key.generate()

        db.session.add(RegistrationKey(key=reg_key, identity=identity.id))
        reg_key_query = RegistrationKey.query.filter_by(key=reg_key).first()

        db.session.add(Traffic(reg_key=reg_key_query.id, timestamp=datetime.today().date(), credit=config.DAILY_TOPUP_VOLUME, ingress=0, egress=0, ingress_shaped=0, egress_shaped=0))

        db.session.commit()

    def __build_device(self, key, ip_address, request):
        user_functions.register_device(key, ip_address, request)

    def __generate_random_name(self):
        return "".join(random.choice(string.ascii_lowercase) for i in range(random.randrange(4, 25)))

    def __generate_random_mail(self):
        mail = "".join(random.choice(string.ascii_lowercase) for i in range(random.randrange(3, 10)))
        mail = mail + "@example.com"
        return mail

    def __generate_random_ip(self):
        network = str(random.randrange(0, 1))
        host = str(random.randrange(2, 254))
        ip_address = "10.90." + network + "." + host
        ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()

        if ip_address_query is not None:
            self.__generate_random_ip()

        self.__add_random_fake_lease(ip_address)

        return ip_address

    def __generate_random_mac(self):
        return "%02x:%02x:%02x:%02x:%02x:%02x" % (
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255),
            random.randint(0, 255))

    def __generate_random_hostname(self):
        return "".join(random.choice(string.ascii_lowercase) for i in range(random.randrange(3, 8)))

    def __add_random_fake_lease(self, ip_address):
        with open(config.DNSMASQ_LEASE_FILE, "a") as lease_file:
            random_mac = self.__generate_random_mac()
            lease_file.write(str(int(time.time())) + " " + random_mac + " " + ip_address + " " + self.__generate_random_hostname() + " " + "01:" + random_mac + "\n")

