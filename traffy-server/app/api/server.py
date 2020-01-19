from app.exceptions.user_exceptions import RegistrationError, DatabaseError, DeregistrationError
from ..models import RegistrationKey, IpAddress, MacAddress, AddressPair, Traffic, Identity
from ..util import arp_manager, generate_registration_key, dnsmasq_manager, lease_parser, iptables_rules_manager, iptables_accounting_manager, shaping_manager
from datetime import datetime, timedelta
from dateutil import rrule
from user_agents import parse
import time
import config


class ServerAPI:
    db = NotImplemented
    accounting_srv = NotImplemented
    dnsmasq_srv = NotImplemented

    def __init__(self, server):
        self.db = server.db
        self.accounting_srv = server.accounting_srv
        self.dnsmasq_srv = server.dnsmasq_srv

    #
    # Config
    #

    def reg_key_exists(self, reg_key):
        if self.get_reg_key_query_by_key(reg_key) is None:
            return False
        return True


    #
    # Database Generic
    #

    def database_commit(self):
        try:
            self.db.session.commit()
        except:
            raise DatabaseError(100)

    def delete_query(self, query):
        self.db.session.delete(query)

    #
    # Queries
    #

    def get_reg_key_query_by_key(self, reg_key):
        return self.db.session.query(RegistrationKey).filter_by(key=reg_key).first()

    def get_reg_key_query_by_id(self, reg_key_id):
        return self.db.session.query(RegistrationKey).filter_by(id=reg_key_id).first()

    def get_ip_address_query_by_ip(self, ip_address):
        return self.db.session.query(IpAddress).filter_by(address_v4=ip_address).first()

    def get_ip_address_query_by_id(self, ip_address_id):
        return self.db.session.query(IpAddress).filter_by(id=ip_address_id).first()

    def get_mac_address_query_by_mac(self, mac_address):
        return self.db.session.query(MacAddress).filter_by(address=mac_address).first()

    def get_mac_address_query_by_id(self, mac_address_id):
        return self.db.session.query(MacAddress).filter_by(id=mac_address_id).first()

    def get_address_pair_query_by_ip(self, ip_address_query):
        return self.db.session.query(AddressPair).filter_by(ip_address=ip_address_query.id).first()

    def get_address_pair_query_by_mac_ip(self, mac_address_query, ip_address_query):
        return self.db.session.query(AddressPair).filter_by(mac_address=mac_address_query.id, ip_address=ip_address_query.id).first()

    #
    # Registration
    #

    def register_device(self, reg_key, ip_address, user_agent):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)

        # Rahmennetzordnung
        self.__set_reg_key_eula_accepted(reg_key_query, True)

        # Create IP Entry
        self.__create_ip_entry(ip_address)

        # Create MAC Entry
        mac_address = self.__get_mac_pair_for_ip(ip_address)
        self.__create_mac_entry(mac_address, user_agent)

        # Create AddressPair
        ip_address_query = self.__create_address_pair(reg_key_query, mac_address, ip_address)

        # Write DB
        self.database_commit()

        # Create Static Lease
        self.__add_static_lease(mac_address, ip_address)

        # Setup Firewall
        self.__unlock_registered_device_firewall(ip_address)

        # Setup Accounting
        self.__enable_device_accounting(reg_key_query, ip_address)

        # Spoofing Protection
        self.__enable_spoofing_protection(ip_address, mac_address)

        # Setup Shaping
        self.__enable_shaping(reg_key_query, ip_address_query)

    def get_registered_devices_count(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        return self.db.session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count()

    def get_maximum_allowed_devices(self):
        return config.MAX_MAC_ADDRESSES_PER_REG_KEY

    def __set_reg_key_eula_accepted(self, reg_key_query, accepted):
        reg_key_query.eula_accepted = True

    def __create_ip_entry(self, ip_address):
        self.db.session.add(IpAddress(address_v4=ip_address, address_v6=None))

    def __get_mac_pair_for_ip(self, ip_address):
        return lease_parser.get_mac_from_ip(ip_address)

    def __get_static_lease_mac(self, ip_address):
        return dnsmasq_manager.get_static_lease_mac(ip_address)

    def __create_mac_entry(self, mac_address, user_agent):
        if mac_address is None:
            raise RegistrationError(125)

        mac_address_query = self.db.session.query(MacAddress).filter_by(address=mac_address).first()
        if mac_address_query is None:
            if len(user_agent) > 500:
                user_agent = user_agent[:500]

            self.db.session.add(MacAddress(address=mac_address, user_agent=user_agent, first_known_since=datetime.now()))
        else:
            raise RegistrationError(130)

    def __create_address_pair(self, reg_key_query, mac_address, ip_address):
        mac_address_query = self.db.session.query(MacAddress).filter_by(address=mac_address).first()
        ip_address_query = self.db.session.query(IpAddress).filter_by(address_v4=ip_address).first()

        if mac_address_query is None or ip_address_query is None:
            raise RegistrationError(135)

        self.db.session.add(AddressPair(reg_key=reg_key_query.id, mac_address=mac_address_query.id, ip_address=ip_address_query.id))
        return ip_address_query

    def __add_static_lease(self, mac_address, ip_address):
        dnsmasq_manager.add_static_lease(mac_address, ip_address)
        self.dnsmasq_srv.reload()

    def __unlock_registered_device_firewall(self, ip_address):
        iptables_rules_manager.unlock_registered_device(ip_address)

    def __enable_device_accounting(self, reg_key_query, ip_address):
        if self.db.session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count() <= 1:
            iptables_accounting_manager.add_accounter_chain(reg_key_query.id)

        iptables_accounting_manager.add_ip_to_box(reg_key_query.id, ip_address)

    def __enable_spoofing_protection(self, ip_address, mac_address):
        arp_manager.add_static_arp_entry(ip_address, mac_address)

    def __enable_shaping(self, reg_key_query, ip_address_query):
        if reg_key_query.id in self.accounting_srv.shaped_reg_keys:
            shaping_manager.enable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    #
    # Deregistration
    #

    def deregister_device(self, ip_address):
        ip_address_query = self.get_ip_address_query_by_ip(ip_address)
        address_pair_query = self.get_address_pair_query_by_ip(ip_address_query)
        mac_address_query = self.get_mac_address_query_by_id(address_pair_query.mac_address)
        reg_key_query = self.get_reg_key_query_by_id(address_pair_query.reg_key)

        mac_address = mac_address_query.address

        # Disable Shaping
        self.__disable_shaping(reg_key_query, ip_address_query)

        # Delete AddressPair
        self.delete_query(address_pair_query)
        self.database_commit()

        # Delete IP Address
        self.delete_query(ip_address_query)
        self.database_commit()

        # Delete MAC Address
        self.delete_query(mac_address_query)
        self.database_commit()

        # Disable Accounting
        self.__disable_device_accounting(reg_key_query, ip_address)

        # Spoofing Protection
        self.__disable_spoofing_protection(ip_address)

        # Delete Static Lease
        self.__remove_static_lease(mac_address, ip_address)

        # Setup Firewall
        self.__relock_registered_device_firewall(ip_address)

    def __disable_shaping(self, reg_key_query, ip_address_query):
        if reg_key_query.id in self.accounting_srv.shaped_reg_keys:
            shaping_manager.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    def __disable_device_accounting(self, reg_key_query, ip_address):
        iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address)

        if self.db.session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count() == 0:
            iptables_accounting_manager.remove_accounter_chain(reg_key_query.id)

    def __disable_spoofing_protection(self, ip_address):
        arp_manager.remove_static_arp_entry(ip_address)

    def __remove_static_lease(self, mac_address, ip_address):
        dnsmasq_manager.remove_static_lease(mac_address, ip_address)
        self.dnsmasq_srv.reload()

    def __relock_registered_device_firewall(self, ip_address):
        iptables_rules_manager.relock_registered_device(ip_address)

    #
    # Registration Key Deletion
    #

    def delete_registration_key(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)

        try:
            address_pair_query = self.db.session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all()
            for row in address_pair_query:
                ip_address_query = self.get_ip_address_query_by_id(row.ip_address)
                self.deregister_device(ip_address_query.address_v4)

            traffic_query = self.db.session.query(Traffic).filter_by(reg_key=reg_key_query.id).all()
            for row in traffic_query:
                self.delete_query(row)

            self.delete_query(reg_key_query)
            self.database_commit()

            identity_query = self.db.session.query(Identity).filter_by(id=reg_key_query.identity).first()

            self.delete_query(identity_query)
            self.database_commit()
            return True
        except Exception as ex:
            print(ex)
            raise DeregistrationError(300)

    #
    # User Status
    #

    def access_check(self, ip_address):
        mac_address = self.__get_mac_pair_for_ip(ip_address)

        ip_address_query = self.get_ip_address_query_by_ip(ip_address)
        mac_address_query = self.get_mac_address_query_by_mac(mac_address)

        if ip_address_query is None and mac_address_query is None:
            return UserStatus(registered=False, deactivated=False, ip_stolen=False)

        if ip_address_query is None and mac_address_query is not None:
            return UserStatus(registered=False, deactivated=False, ip_stolen=True)

        if ip_address_query is not None and mac_address_query is None:
            return UserStatus(registered=False, deactivated=False, ip_stolen=True)

        address_pair_query = self.get_address_pair_query_by_mac_ip(mac_address_query, ip_address_query)
        if address_pair_query is None:
            return UserStatus(registered=False, deactivated=False, ip_stolen=False)
        else:
            reg_key_query = self.get_reg_key_query_by_id(address_pair_query.reg_key)
            if reg_key_query.active is False:
                return UserStatus(registered=False, deactivated=True, ip_stolen=False)
            else:
                return UserStatus(registered=True, deactivated=False, ip_stolen=False)

    #
    # Dashboard
    #

    def get_reg_key_credit_by_ip(self, ip_address):
        ip_address_query = self.get_ip_address_query_by_ip(ip_address)
        address_pair_query = self.get_address_pair_query_by_ip(ip_address_query)
        reg_key_query = self.get_reg_key_query_by_id(address_pair_query.reg_key)
        volume_left, credit = self.accounting_srv.get_credit(reg_key_query, gib=True)
        if volume_left < 0:
            volume_left = 0
        return volume_left, credit

    def set_device_user_agent(self, ip_address, user_agent):
        ip_address_query = self.get_ip_address_query_by_ip(ip_address)
        address_pair_query = self.get_address_pair_query_by_ip(ip_address_query)
        mac_address_query = self.get_mac_address_query_by_id(address_pair_query.mac_address)

        if len(user_agent) > 500:
            user_agent = user_agent[:500]

        if mac_address_query.user_agent != user_agent:
            mac_address_query.user_agent = user_agent

        self.database_commit()

    #
    # Supervisor Login
    #

    def get_supervisor_dashboard_stats(self):
        today = datetime.today().date()
        passed_days = today - timedelta(days=10)

        values_downlink = []
        values_uplink = []
        labels = []

        for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
            traffic_query = self.db.session.query(Traffic).filter_by(timestamp=date).all()
            downlink = 0
            uplink = 0
            if traffic_query is not None:
                for row in traffic_query:
                    downlink += self.__to_gib(row.ingress)
                    uplink += self.__to_gib(row.egress)

            values_downlink.append(downlink)
            values_uplink.append(uplink)
            labels.append(date.strftime("%d.%m."))

        active_users = self.db.session.query(RegistrationKey).filter_by(active=True).count()
        ip_adresses = self.db.session.query(IpAddress).count()
        ratio = "N/A"
        if ip_adresses != 0:
            ratio = round(active_users / ip_adresses, 1)

        traffic_rows = self.db.session.query(Traffic).filter_by(timestamp=today).all()

        average_credit = 0
        count = 0
        shaped_users = 0
        for row in traffic_rows:
            count += 1
            average_credit += (row.credit - (row.ingress + row.egress)) / 1073741824
            if row.ingress + row.egress >= row.credit or row.credit <= 0:
                shaped_users += 1

        if count != 0:
            average_credit = round(average_credit, 3)
        else:
            average_credit = 0

        return values_downlink, values_uplink, labels, active_users, ratio, average_credit, shaped_users

    def get_reg_codes_search_results(self, search_term):
        search_results = []
        reg_key_query = []

        for query in self.db.session.query(RegistrationKey).all():
            if search_term in query.key:
                reg_key_query.append(query)
            else:
                identity = self.db.session.query(Identity).filter_by(id=query.identity).first()

                if search_term in identity.first_name.lower() or search_term in identity.last_name.lower() or search_term in identity.mail.lower():
                    reg_key_query.append(query)

        reg_key_query.reverse()

        for row in reg_key_query:
            identity = self.db.session.query(Identity).filter_by(id=row.identity).first()
            credit = self.accounting_srv.get_credit(row, gib=True)[0]
            if credit < 0:
                credit = 0
            search_results.append(KeyRow(row.key, identity.last_name, identity.first_name, credit, row.active))

        return search_results

    def construct_reg_code_list(self):
        rows = []
        for row in self.db.session.query(RegistrationKey).all():
            identity = self.db.session.query(Identity).filter_by(id=row.identity).first()
            credit = self.accounting_srv.get_credit(row, gib=True)[0]
            if credit < 0:
                credit = 0
            rows.append(KeyRow(row.key, identity.last_name, identity.first_name, credit, row.active))
        rows.reverse()
        return rows

    def add_registration_code(self, first_name, surname, mail):
        self.db.session.add(Identity(first_name=first_name, last_name=surname, mail=mail))
        identity = self.db.session.query(Identity).filter_by(first_name=first_name, last_name=surname, mail=mail).first()

        reg_key = generate_registration_key.generate()

        self.db.session.add(RegistrationKey(key=reg_key, identity=identity.id))
        reg_key_query = self.db.session.query(RegistrationKey).filter_by(key=reg_key).first()

        self.db.session.add(Traffic(reg_key=reg_key_query.id, timestamp=datetime.today().date(), credit=config.DAILY_TOPUP_VOLUME, ingress=0, egress=0, ingress_shaped=0, egress_shaped=0))
        self.db.session.commit()

        return reg_key

    def set_reg_key_custom_credit(self, reg_key, value):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        valid = self.accounting_srv.set_custom_credit(reg_key_query, value)

        if not valid:
            return False
        return True

    def set_reg_key_custom_topup(self, reg_key, value):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        valid = self.accounting_srv.set_custom_topup(reg_key_query, value)

        if not valid:
            return False
        return True

    def set_reg_key_disable_custom_topup(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        success = self.accounting_srv.disable_custom_topup(reg_key_query)

        if not success:
            return False
        return True

    def set_reg_key_custom_max_enable(self, reg_key, value):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        valid = self.accounting_srv.set_custom_max_volume(reg_key_query, value)

        if not valid:
            return False
        return True

    def set_reg_key_custom_max_disable(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        success = self.accounting_srv.disable_custom_max_volume(reg_key_query)

        if not success:
            return False
        return True

    def set_reg_key_enable_accounting(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        success = self.accounting_srv.enable_accounting_for_reg_key(reg_key_query)

        if not success:
            return False
        return True

    def set_reg_key_disable_accounting(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        success = self.accounting_srv.disable_accounting_for_reg_key(reg_key_query)

        if not success:
            return False
        return True

    def set_reg_key_activated(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        success = self.accounting_srv.activate_registration_key(reg_key_query)

        if not success:
            return False
        return True

    def set_reg_key_deactivated(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)
        success = self.accounting_srv.deactivate_registration_key(reg_key_query)

        if not success:
            return False
        return True

    def get_reg_code_statistics(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)

        traffic_query = self.db.session.query(Traffic).filter_by(reg_key=reg_key_query.id).first()
        stat_volume_left = self.accounting_srv.get_credit(reg_key_query, gib=True)[0]
        stat_created_on = self.accounting_srv.get_reg_key_creation_timestamp(reg_key_query, "%d.%m.%Y")
        stat_shaped = self.accounting_srv.is_reg_key_shaped(reg_key_query)
        stat_status = self.accounting_srv.is_registration_key_active(reg_key_query)

        if stat_volume_left < 0:
            stat_volume_left = 0

        values_downlink = []
        values_downlink_shaped = []
        values_uplink = []
        values_uplink_shaped = []
        labels = []

        today = datetime.today().date()
        passed_days = today - timedelta(days=10)

        for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
            traffic_query = self.db.session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).all()
            downlink = 0
            downlink_shaped = 0
            uplink = 0
            uplink_shaped = 0

            if traffic_query is not None:
                for row in traffic_query:
                    downlink += self.__to_gib(row.ingress)
                    downlink_shaped += self.__to_gib(row.ingress_shaped)
                    uplink += self.__to_gib(row.egress)
                    uplink_shaped += self.__to_gib(row.egress_shaped)

            values_downlink.append(downlink)
            values_downlink_shaped.append(downlink_shaped)
            values_uplink.append(uplink)
            values_uplink_shaped.append(uplink_shaped)
            labels.append(date.strftime("%d.%m."))

        return stat_volume_left, stat_created_on, stat_shaped, stat_status, labels, values_downlink, values_downlink_shaped, values_uplink, values_uplink_shaped

    def get_reg_code_device_list(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)

        device_list = []
        for row in self.db.session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all():
            ip_address_query = self.db.session.query(IpAddress).filter_by(id=row.ip_address).first()
            mac_address_query = self.db.session.query(MacAddress).filter_by(id=row.mac_address).first()

            device_list.append(DeviceRow(ip_address_query.address_v4, mac_address_query.address, mac_address_query.user_agent, mac_address_query.first_known_since))

        device_list.reverse()
        return device_list

    def get_reg_code_settings_values(self, reg_key):
        reg_key_query = self.get_reg_key_query_by_key(reg_key)

        # Custom Top-Up
        custom_volume_enabled = False
        value_custom_topup = 0
        if reg_key_query.daily_topup_volume is not None:
            custom_volume_enabled = True
            value_custom_topup = self.__to_gib(reg_key_query.daily_topup_volume)

        # Custom Max Value
        custom_max_enabled = False
        value_max_volume = 0
        if reg_key_query.max_volume is not None:
            custom_max_enabled = True
            value_max_volume = self.__to_gib(reg_key_query.max_volume)

        # Disable Accounting
        accounting_enabled = reg_key_query.enable_accounting

        # Deactivate Registration Key
        key_active = reg_key_query.active

        return custom_volume_enabled, value_custom_topup, custom_max_enabled, value_max_volume, accounting_enabled, key_active

    def get_instruction_pdf_values(self):
        max_saved_volume = self.__to_gib(self.accounting_srv.get_max_saved_volume(), decimals=0)
        daily_topup_volume = self.__to_gib(self.accounting_srv.get_daily_topup_volume(), decimals=0)
        shaping_speed = config.SHAPING_SPEED
        traffy_url = config.THIS_SERVER_IP_WAN
        max_devices = config.MAX_MAC_ADDRESSES_PER_REG_KEY

        return max_saved_volume, daily_topup_volume, shaping_speed, traffy_url, max_devices

    #
    # Util / Private
    #

    def __to_gib(self, bytes, decimals=3):
        return round(bytes / 1073741824, decimals)

    def __to_bytes(self, gib):
        return int(gib * 1073741824)

class UserStatus():
    registered = False
    deactivated = False
    ip_stolen = False

    def __init__(self, registered, deactivated, ip_stolen):
        self.registered = registered
        self.deactivated = deactivated
        self.ip_stolen = ip_stolen

class KeyRow():
    reg_key = ""
    last_name = ""
    first_name = ""
    credit = ""
    active = True

    def __init__(self, reg_key, last_name, first_name, credit, active):
        self.reg_key = reg_key
        self.last_name = last_name
        self.first_name = first_name
        self.credit = credit
        self.active = active

class DeviceRow():
    ip_address = ""
    mac_address = ""
    type = ""
    registered_since = ""

    def __init__(self, ip_address, mac_address, user_agent, registered_since):
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.type = self.find_device(user_agent)
        self.registered_since = registered_since.strftime("%d.%m.%Y %H:%M:%S")

    def find_device(self, user_agent):
        device_string = ""
        user_agent = parse(user_agent)

        if user_agent.is_mobile:
            if user_agent.is_touch_capable:
                device_string += "Smartphone / "
                device_string += user_agent.device.brand + " / " + user_agent.device.family + " / "
            else:
                device_string += "Handy / "
                device_string += user_agent.device.brand + " / " + user_agent.device.family + " / "
        elif user_agent.is_tablet:
            device_string += "Tablet / "
        elif user_agent.is_pc:
            device_string += "Desktop / "

        device_string += user_agent.os.family + " " + user_agent.os.version_string

        if device_string == "Other":
            device_string = "Unknown"

        return device_string

