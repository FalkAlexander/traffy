from ..models import RegistrationKey, Traffic, Identity, IpAddress
from ..util import generate_registration_key
from datetime import datetime
import config
import random
import string
import time


class DevModeTest():
    db = NotImplemented

    def __init__(self, db):
        self.db = db

    def add_reg_key(self):
        self.__build_reg_key(self.__generate_random_name(),
                           self.__generate_random_name(),
                           self.__generate_random_mail())

    def register_device(self, api, reg_key_query, user_agent):
        self.__build_device(api, reg_key_query.key, self.__generate_random_ip(), user_agent)

    def __build_reg_key(self, first_name, surname, mail):
        try:
            session = self.db.create_session()

            session.add(Identity(first_name=first_name, last_name=surname, mail=mail))
            identity = session.query(Identity).filter_by(first_name=first_name, last_name=surname, mail=mail).first()
            reg_key = generate_registration_key.generate()

            session.add(RegistrationKey(key=reg_key, identity=identity.id))
            reg_key_query = session.query(RegistrationKey).filter_by(key=reg_key).first()

            session.add(Traffic(reg_key=reg_key_query.id, timestamp=datetime.today().date(), credit=config.DAILY_TOPUP_VOLUME, ingress=0, egress=0, ingress_shaped=0, egress_shaped=0))

            session.commit()
        except:
            session.rollback()
        finally:
            session.close()

    def __build_device(self, api, key, ip_address, user_agent):
        api.register_device(key, ip_address, user_agent)

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

        session = self.db.create_session()
        ip_address_query = session.query(IpAddress).filter_by(address_v4=ip_address).first()

        if ip_address_query is not None:
            session.close()
            return self.__generate_random_ip()
        session.close()

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

