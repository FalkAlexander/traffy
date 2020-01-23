from app.exceptions.user_exceptions import RegistrationError, DatabaseError, DeregistrationError
from ..models import RegistrationKey, IpAddress, MacAddress, AddressPair, Traffic, Identity
from ..util import arp_manager, generate_registration_key, dnsmasq_manager, lease_parser, iptables_rules_manager, iptables_accounting_manager, shaping_manager
from datetime import datetime, timedelta
from dateutil import rrule
from user_agents import parse
import time
import config
import threading


class ServerAPI:
    db = NotImplemented
    accounting_srv = NotImplemented
    dnsmasq_srv = NotImplemented
    dev_mode_test = NotImplemented

    server_version = "0.1"
    api_version = "1.0"

    def __init__(self, server):
        self.db = server.db
        self.accounting_srv = server.accounting_srv
        self.dnsmasq_srv = server.dnsmasq_srv
        self.dev_mode_test = server.dev_mode_test

    def get_server_version(self):
        return self.server_version

    def get_api_version(self):
        return self.api_version

    #
    # Config
    #

    def reg_key_exists(self, reg_key):
        session = self.db.create_session()
        exists = True
        if self.get_reg_key_query_by_key(session, reg_key) is None:
            exists = False

        session.close()
        return exists


    #
    # Database Generic
    #

    def database_commit(self, session):
        session.commit()

    def delete_query(self, session, query):
        session.delete(query)

    #
    # Queries
    #

    def get_reg_key_query_by_key(self, session, reg_key):
        return session.query(RegistrationKey).filter_by(key=reg_key).first()

    def get_reg_key_query_by_id(self, session, reg_key_id):
        return session.query(RegistrationKey).filter_by(id=reg_key_id).first()

    def get_ip_address_query_by_ip(self, session, ip_address):
        return session.query(IpAddress).filter_by(address_v4=ip_address).first()

    def get_ip_address_query_by_id(self, session, ip_address_id):
        return session.query(IpAddress).filter_by(id=ip_address_id).first()

    def get_mac_address_query_by_mac(self, session, mac_address):
        return session.query(MacAddress).filter_by(address=mac_address).first()

    def get_mac_address_query_by_id(self, session, mac_address_id):
        return session.query(MacAddress).filter_by(id=mac_address_id).first()

    def get_address_pair_query_by_ip(self, session, ip_address_query):
        return session.query(AddressPair).filter_by(ip_address=ip_address_query.id).first()

    def get_address_pair_query_by_mac_ip(self, session, mac_address_query, ip_address_query):
        return session.query(AddressPair).filter_by(mac_address=mac_address_query.id, ip_address=ip_address_query.id).first()

    #
    # Registration
    #

    def register_device(self, reg_key, ip_address, user_agent):
        session = self.db.create_session()

        try:
            reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

            # Rahmennetzordnung
            self.__set_reg_key_eula_accepted(reg_key_query, True)

            # Create IP Entry
            self.__create_ip_entry(session, ip_address)

            # Create MAC Entry
            mac_address = self.__get_mac_pair_for_ip(ip_address)
            self.__create_mac_entry(session, mac_address, user_agent)

            # Create AddressPair
            ip_address_query = self.__create_address_pair(session, reg_key_query, mac_address, ip_address)

            # Write DB
            self.database_commit(session)

            # Create Static Lease
            self.__add_static_lease(mac_address, ip_address)

            # Setup Firewall
            self.__unlock_registered_device_firewall(ip_address)

            # Setup Accounting
            self.__enable_device_accounting(session, reg_key_query, ip_address)
        except:
            session.rollback()
        finally:
            session.close()

        # Spoofing Protection
        self.__enable_spoofing_protection(ip_address, mac_address)

        # Setup Shaping
        self.__enable_shaping(reg_key_query, ip_address_query)

    def get_registered_devices_count(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        devices_count = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count()
        session.close()
        return devices_count

    def get_maximum_allowed_devices(self):
        return config.MAX_MAC_ADDRESSES_PER_REG_KEY

    def __set_reg_key_eula_accepted(self, reg_key_query, accepted):
        reg_key_query.eula_accepted = True

    def __create_ip_entry(self, session, ip_address):
        session.add(IpAddress(address_v4=ip_address, address_v6=None))

    def __get_mac_pair_for_ip(self, ip_address):
        return lease_parser.get_mac_from_ip(ip_address)

    def __get_static_lease_mac(self, ip_address):
        return dnsmasq_manager.get_static_lease_mac(ip_address)

    def __create_mac_entry(self, session, mac_address, user_agent):
        if mac_address is None:
            raise RegistrationError(125)

        mac_address_query = session.query(MacAddress).filter_by(address=mac_address).first()
        if mac_address_query is None:
            if len(user_agent) > 500:
                user_agent = user_agent[:500]

            session.add(MacAddress(address=mac_address, user_agent=user_agent, first_known_since=datetime.now()))
        else:
            raise RegistrationError(130)

    def __create_address_pair(self, session, reg_key_query, mac_address, ip_address):
        mac_address_query = session.query(MacAddress).filter_by(address=mac_address).first()
        ip_address_query = session.query(IpAddress).filter_by(address_v4=ip_address).first()

        if mac_address_query is None or ip_address_query is None:
            raise RegistrationError(135)

        session.add(AddressPair(reg_key=reg_key_query.id, mac_address=mac_address_query.id, ip_address=ip_address_query.id))
        return ip_address_query

    def __add_static_lease(self, mac_address, ip_address):
        dnsmasq_manager.add_static_lease(mac_address, ip_address)
        self.dnsmasq_srv.reload()

    def __unlock_registered_device_firewall(self, ip_address):
        iptables_rules_manager.unlock_registered_device(ip_address)

    def __enable_device_accounting(self, session, reg_key_query, ip_address):
        if session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count() <= 1:
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

    def deregister_device(self, ip_address, session=None):
        close_session = False
        if session is None:
            session = self.db.create_session()
            close_session = True

        try:
            ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
            address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
            mac_address_query = self.get_mac_address_query_by_id(session, address_pair_query.mac_address)
            reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)

            mac_address = mac_address_query.address

            # Disable Shaping
            self.__disable_shaping(reg_key_query, ip_address_query)

            # Delete AddressPair
            self.delete_query(session, address_pair_query)
            self.database_commit(session)

            # Delete IP Address
            self.delete_query(session, ip_address_query)
            self.database_commit(session)

            # Delete MAC Address
            self.delete_query(session, mac_address_query)
            self.database_commit(session)

            # Disable Accounting
            self.__disable_device_accounting(session, reg_key_query, ip_address)
        except:
            session.rollback()
        finally:
            if close_session is True:
                session.close()

        # Spoofing Protection
        self.__disable_spoofing_protection(ip_address)

        # Delete Static Lease
        self.__remove_static_lease(mac_address, ip_address)

        # Setup Firewall
        self.__relock_registered_device_firewall(ip_address)

    def __disable_shaping(self, reg_key_query, ip_address_query):
        if reg_key_query.id in self.accounting_srv.shaped_reg_keys:
            shaping_manager.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    def __disable_device_accounting(self, session, reg_key_query, ip_address):
        iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address)

        if session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count() == 0:
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
        session = self.db.create_session()

        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        try:
            address_pair_query = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all()
            for row in address_pair_query:
                ip_address_query = self.get_ip_address_query_by_id(session, row.ip_address)
                self.deregister_device(ip_address_query.address_v4, session=session)

            traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id).all()
            for row in traffic_query:
                self.delete_query(session, row)
            self.database_commit(session)

            self.delete_query(session, reg_key_query)
            self.database_commit(session)

            identity_query = session.query(Identity).filter_by(id=reg_key_query.identity).first()

            self.delete_query(session, identity_query)
            self.database_commit(session)
            return True
        except Exception as ex:
            session.rollback()
            raise DeregistrationError(300)
        finally:
            session.close()

    #
    # User Status
    #

    def access_check(self, ip_address):
        session = self.db.create_session()

        mac_address = self.__get_mac_pair_for_ip(ip_address)

        ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
        mac_address_query = self.get_mac_address_query_by_mac(session, mac_address)

        if ip_address_query is None and mac_address_query is None:
            session.close()
            return UserStatus(registered=False, deactivated=False, ip_stolen=False)

        if ip_address_query is None and mac_address_query is not None:
            session.close()
            return UserStatus(registered=False, deactivated=False, ip_stolen=True)

        if ip_address_query is not None and mac_address_query is None:
            session.close()
            return UserStatus(registered=False, deactivated=False, ip_stolen=True)

        address_pair_query = self.get_address_pair_query_by_mac_ip(session, mac_address_query, ip_address_query)
        if address_pair_query is None:
            session.close()
            return UserStatus(registered=False, deactivated=False, ip_stolen=False)
        else:
            reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)
            if reg_key_query.active is False:
                session.close()
                return UserStatus(registered=False, deactivated=True, ip_stolen=False)
            else:
                session.close()
                return UserStatus(registered=True, deactivated=False, ip_stolen=False)

    #
    # Dashboard
    #

    def get_reg_key_credit_by_ip(self, ip_address):
        session = self.db.create_session()

        ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
        address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
        reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)
        volume_left, credit = self.accounting_srv.get_credit(session, reg_key_query, gib=True)

        session.close()

        if volume_left < 0:
            volume_left = 0
        return volume_left, credit

    def set_device_user_agent(self, ip_address, user_agent):
        session = self.db.create_session()

        ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
        address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
        mac_address_query = self.get_mac_address_query_by_id(session, address_pair_query.mac_address)

        if len(user_agent) > 500:
            user_agent = user_agent[:500]

        if mac_address_query.user_agent != user_agent:
            mac_address_query.user_agent = user_agent

        self.database_commit(session)
        session.close()

    #
    # Supervisor Login
    #

    def get_supervisor_dashboard_stats(self):
        session = self.db.create_session()

        today = datetime.today().date()
        passed_days = today - timedelta(days=10)

        values_downlink = []
        values_uplink = []
        labels = []

        for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
            traffic_query = session.query(Traffic).filter_by(timestamp=date).all()
            downlink = 0
            uplink = 0
            if traffic_query is not None:
                for row in traffic_query:
                    downlink += self.__to_gib(row.ingress)
                    uplink += self.__to_gib(row.egress)

            values_downlink.append(downlink)
            values_uplink.append(uplink)
            labels.append(date.strftime("%d.%m."))

        active_users = session.query(RegistrationKey).filter_by(active=True).count()
        ip_adresses = session.query(IpAddress).count()
        ratio = "N/A"
        if ip_adresses != 0:
            ratio = round(active_users / ip_adresses, 1)

        traffic_rows = session.query(Traffic).filter_by(timestamp=today).all()

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

        session.close()
        return values_downlink, values_uplink, labels, active_users, ratio, average_credit, shaped_users

    def get_reg_codes_search_results(self, search_term):
        session = self.db.create_session()

        search_results = []
        reg_key_query = []

        for query in session.query(RegistrationKey).all():
            if search_term in query.key:
                reg_key_query.append(query)
            else:
                identity = session.query(Identity).filter_by(id=query.identity).first()

                if search_term in identity.first_name.lower() or search_term in identity.last_name.lower() or search_term in identity.mail.lower():
                    reg_key_query.append(query)

        reg_key_query.reverse()

        for row in reg_key_query:
            identity = session.query(Identity).filter_by(id=row.identity).first()
            credit = self.accounting_srv.get_credit(session, row, gib=True)[0]
            if credit < 0:
                credit = 0
            search_results.append(KeyRow(row.key, identity.last_name, identity.first_name, credit, row.active))

        session.close()
        return search_results

    def construct_reg_code_list(self):
        session = self.db.create_session()

        rows = []
        for row in session.query(RegistrationKey).all():
            identity = session.query(Identity).filter_by(id=row.identity).first()
            credit = self.accounting_srv.get_credit(session, row, gib=True)[0]
            if credit < 0:
                credit = 0
            rows.append(KeyRow(row.key, identity.last_name, identity.first_name, credit, row.active))
        rows.reverse()
        session.close()
        return rows

    def add_registration_code(self, first_name, surname, mail):
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

        return reg_key

    def set_reg_key_custom_credit(self, reg_key, value):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        valid = self.accounting_srv.set_custom_credit(session, reg_key_query, value)
        session.close()

        if not valid:
            return False
        return True

    def set_reg_key_custom_topup(self, reg_key, value):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        valid = self.accounting_srv.set_custom_topup(session, reg_key_query, value)
        session.close()

        if not valid:
            return False
        return True

    def set_reg_key_disable_custom_topup(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        success = self.accounting_srv.disable_custom_topup(session, reg_key_query)
        session.close()

        if not success:
            return False
        return True

    def set_reg_key_custom_max_enable(self, reg_key, value):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        valid = self.accounting_srv.set_custom_max_volume(session, reg_key_query, value)
        session.close()

        if not valid:
            return False
        return True

    def set_reg_key_custom_max_disable(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        success = self.accounting_srv.disable_custom_max_volume(session, reg_key_query)
        session.close()

        if not success:
            return False
        return True

    def set_reg_key_enable_accounting(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        success = self.accounting_srv.enable_accounting_for_reg_key(session, reg_key_query)
        session.close()

        if not success:
            return False
        return True

    def set_reg_key_disable_accounting(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        success = self.accounting_srv.disable_accounting_for_reg_key(session, reg_key_query)
        session.close()

        if not success:
            return False
        return True

    def set_reg_key_activated(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        success = self.accounting_srv.activate_registration_key(session, reg_key_query)
        session.close()

        if not success:
            return False
        return True

    def set_reg_key_deactivated(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        success = self.accounting_srv.deactivate_registration_key(session, reg_key_query)
        session.close()

        if not success:
            return False
        return True

    def get_reg_code_statistics(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id).first()
        stat_volume_left = self.accounting_srv.get_credit(session, reg_key_query, gib=True)[0]
        stat_created_on = self.accounting_srv.get_reg_key_creation_timestamp(reg_key_query, "%d.%m.%Y")
        stat_shaped = self.accounting_srv.is_reg_key_shaped(session, reg_key_query)
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
            traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).all()
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

        session.close()

        return stat_volume_left, stat_created_on, stat_shaped, stat_status, labels, values_downlink, values_downlink_shaped, values_uplink, values_uplink_shaped

    def get_reg_code_device_list(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        device_list = []
        for row in session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all():
            ip_address_query = session.query(IpAddress).filter_by(id=row.ip_address).first()
            mac_address_query = session.query(MacAddress).filter_by(id=row.mac_address).first()

            device_list.append(DeviceRow(ip_address_query.address_v4, mac_address_query.address, mac_address_query.user_agent, mac_address_query.first_known_since))

        device_list.reverse()
        session.close()
        return device_list

    def get_reg_code_settings_values(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

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

        session.close()
        return custom_volume_enabled, value_custom_topup, custom_max_enabled, value_max_volume, accounting_enabled, key_active

    def get_instruction_pdf_values(self):
        max_saved_volume = self.__to_gib(self.accounting_srv.get_max_saved_volume(), decimals=0)
        daily_topup_volume = self.__to_gib(self.accounting_srv.get_daily_topup_volume(), decimals=0)
        shaping_speed = config.SHAPING_SPEED
        traffy_url = config.THIS_SERVER_IP_WAN
        max_devices = config.MAX_MAC_ADDRESSES_PER_REG_KEY

        return max_saved_volume, daily_topup_volume, shaping_speed, traffy_url, max_devices

    #
    # Tests
    #

    def create_reg_key_test(self):
        self.dev_mode_test.add_reg_key()

    def register_device_test(self, reg_key, user_agent):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        self.dev_mode_test.register_device(self, reg_key_query, user_agent)
        session.close()

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

