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

from app.exceptions.user_exceptions import RegistrationError, DatabaseError, DeregistrationError
from enum import Enum
from ..models import IdentityUpdate, RegistrationKey, IpAddress, MacAddress, AddressPair, Traffic, Identity, Dormitory
from ..util import tc_manager, nftables_manager
from datetime import datetime, timedelta
from dateutil import rrule
from user_agents import parse
from sqlalchemy.sql import func
from sqlalchemy import and_
import json
import time
import codecs
import config
import threading
import urllib.request as urllib2
import uuid


class ServerAPI:
    db = NotImplemented
    accounting_srv = NotImplemented

    def __init__(self, server):
        self.db = server.db
        self.accounting_srv = server.accounting_srv

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

    def set_data_policy_accepted(self, reg_key):
        session = self.db.create_session()

        try:
            reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
            if reg_key_query.data_policy_accepted is not True:
                reg_key_query.data_policy_accepted = True
                self.database_commit(session)
        except:
            session.rollback()
        finally:
            session.close()
    
    def set_eula_accepted(self, reg_key):
        session = self.db.create_session()

        try:
            reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
            if reg_key_query.eula_accepted is not True:
                reg_key_query.eula_accepted = True
                self.database_commit(session)
        except:
            session.rollback()
        finally:
            session.close()

    def register_device(self, reg_key, ip_address, user_agent):
        session = self.db.create_session()

        try:
            reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

            # Create IP Entry
            self.__create_ip_entry(session, ip_address)

            # Create MAC Entry
            mac_address = self.__get_mac_from_ip(ip_address)
            self.__create_mac_entry(session, mac_address, user_agent)

            # Create AddressPair
            ip_address_query = self.__create_address_pair(session, reg_key_query, mac_address, ip_address)

            # Write DB
            self.database_commit(session)

            # Setup Firewall
            self.__unlock_registered_device_firewall(mac_address, ip_address)

            # Setup Accounting
            self.__enable_device_accounting(session, reg_key_query, ip_address)

            # Setup Shaping
            self.__enable_shaping(reg_key_query, ip_address_query)
        except:
            session.rollback()
        finally:
            session.close()

    def get_registered_devices_count(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        devices_count = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count()
        session.close()
        return devices_count

    def get_maximum_allowed_devices(self):
        return config.MAX_MAC_ADDRESSES_PER_REG_KEY
    
    def get_max_saved_volume(self):
        return self.accounting_srv.get_max_saved_volume()

    def get_in_unlimited_time_range(self):
        in_unlimited_time_range = False
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        for range in config.TIME_RANGES_UNLIMITED_DATA:
            start = range[0]
            end = range[1]
            if current_time > start and current_time < end:
                in_unlimited_time_range = True
                break
        return in_unlimited_time_range

    def get_reg_code_room(self, reg_key):
        session = self.db.create_session()
        reg_key = session.query(RegistrationKey).filter_by(key=reg_key).first()
        identity = session.query(Identity).filter_by(id=reg_key.identity).first()
        session.close()
        return identity.room

    def __create_ip_entry(self, session, ip_address):
        session.add(IpAddress(address_v4=ip_address, address_v6=None))

    def __create_mac_entry(self, session, mac_address, user_agent):
        if mac_address is None:
            raise RegistrationError(125)

        mac_address_query = session.query(MacAddress).filter_by(address=mac_address).first()
        if mac_address_query is None:
            if len(user_agent) > 500:
                user_agent = user_agent[:500]
            
            vendor = self.__get_mac_address_vendor(mac_address)
            if len(vendor) > 500:
                vendor = vendor[:500]

            session.add(MacAddress(address=mac_address, user_agent=user_agent, vendor=vendor, first_known_since=datetime.now()))
        else:
            raise RegistrationError(130)

    def __create_address_pair(self, session, reg_key_query, mac_address, ip_address):
        mac_address_query = session.query(MacAddress).filter_by(address=mac_address).first()
        ip_address_query = session.query(IpAddress).filter_by(address_v4=ip_address).first()

        if mac_address_query is None or ip_address_query is None:
            raise RegistrationError(135)

        session.add(AddressPair(reg_key=reg_key_query.id, mac_address=mac_address_query.id, ip_address=ip_address_query.id))
        return ip_address_query

    def __unlock_registered_device_firewall(self, mac_address, ip_address):
        nftables_manager.add_allocation_to_registered_set(mac_address, ip_address)

    def __enable_device_accounting(self, session, reg_key_query, ip_address):
        if session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count() <= 1:
            nftables_manager.add_reg_key_set(str(reg_key_query.id))
            nftables_manager.add_accounting_matching_rules(str(reg_key_query.id))
        
        nftables_manager.add_ip_to_reg_key_set(ip_address, str(reg_key_query.id))

    def __enable_shaping(self, reg_key_query, ip_address_query):
        if reg_key_query.id in self.accounting_srv.shaped_reg_keys:
            tc_manager.enable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

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

        # Setup Firewall
        self.__relock_registered_device_firewall(mac_address, ip_address)

    def deregister_all_devices(self, reg_key, session=None):
        close_session = False
        if session is None:
            session = self.db.create_session()
            close_session = True

        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        try:
            address_pair_query = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all()
            for row in address_pair_query:
                ip_address_query = self.get_ip_address_query_by_id(session, row.ip_address)
                self.deregister_device(ip_address_query.address_v4, session=session)
        except:
            session.rollback()
        finally:
            if close_session is True:
                session.close()

    def __disable_shaping(self, reg_key_query, ip_address_query):
        if reg_key_query.id in self.accounting_srv.shaped_reg_keys:
            tc_manager.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    def __disable_device_accounting(self, session, reg_key_query, ip_address):
        nftables_manager.delete_ip_from_reg_key_set(ip_address, str(reg_key_query.id))

        if session.query(AddressPair).filter_by(reg_key=reg_key_query.id).count() == 0:
            nftables_manager.delete_accounting_matching_rules(str(reg_key_query.id))
            nftables_manager.delete_reg_key_set(str(reg_key_query.id))

    def __relock_registered_device_firewall(self, mac_address, ip_address):
        nftables_manager.delete_allocation_from_registered_set(mac_address, ip_address)

    #
    # Registration Key Deletion
    #

    def delete_registration_key(self, reg_key, date):
        success = NotImplemented
        session = self.db.create_session()

        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        try:
            deletion_date = None
            if date != "":
                deletion_date = datetime.strptime(date, "%Y-%m-%d")
            
            if deletion_date is not None:
                reg_key_query.deletion_date = deletion_date
                self.database_commit(session)
            else:
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
            success = True
        except:
            session.rollback()
            raise DeregistrationError(300)
            success = False
        finally:
            session.close()
        
        return success
    
    def cancel_delete_registration_key(self, reg_key):
        success = NotImplemented
        session = self.db.create_session()

        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        try:
            reg_key_query.deletion_date = None
            self.database_commit(session)
            success = True
        except:
            session.rollback()
            success = False
        finally:
            session.close()
        
        return success

    #
    # User Status
    #

    def access_check(self, ip_address):
        session = self.db.create_session()

        mac_address = self.__get_mac_from_ip(ip_address)

        # Check if request came from inside the network
        if self.__is_ip_in_range(ip_address) is False:
            session.close()
            return AccessMode(outside_lan=True)

        # The corresponding MAC to the IP address could not be found, assuming that there is no lease
        if mac_address is None:
            session.close()
            return AccessMode(no_lease=True)

        try:
            ip_address_query = session.query(IpAddress).filter_by(address_v4=ip_address).first()
            mac_address_query = session.query(MacAddress).filter_by(address=mac_address).first()
        except:
            session.rollback()
            return AccessMode(error=True)

        # Both MAC and IP are known to the system...
        if ip_address_query is not None and mac_address_query is not None:
            try:
                address_pair_query = session.query(AddressPair).filter_by(mac_address=mac_address_query.id, ip_address=ip_address_query.id).first()
            except:
                session.rollback()
                return AccessMode(error=True)
            
            # Is there a device with both the exact same MAC and IP?
            if address_pair_query is not None:
                reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)

                if reg_key_query.active is False:
                    session.close()
                    return AccessMode(deactivated=True)
    
                session.close()
                return AccessMode(registered=True)
            else:
                session.close()
                return AccessMode(device_registered_with_different_port=True)
        
        # Only the MAC is known to the system...
        if mac_address_query is not None and ip_address_query is None:
            session.close()
            return AccessMode(device_registered_with_different_port=True)

        session.close()
        return AccessMode(unregistered=True)

    #
    # Dashboard
    #

    def get_reg_key_credit_by_ip(self, ip_address):
        session = self.db.create_session()

        ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
        address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
        reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)
        volume_left, max_volume = self.accounting_srv.get_credit(session, reg_key_query, gib=True)

        session.close()

        if volume_left < 0:
            volume_left = 0
        return volume_left, max_volume

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

    def get_advanced_dashboard_stats(self, ip_address):
        session = self.db.create_session()

        ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
        address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
        reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)

        today = datetime.today().date()
        passed_days = today - timedelta(days=6)

        values_downlink = []
        values_downlink_unlimited_range = []
        values_downlink_shaped = []
        values_downlink_excepted = []
        values_uplink = []
        values_uplink_unlimited_range = []
        values_uplink_shaped = []
        values_uplink_excepted = []
        labels = []

        try:
            for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
                traffic_query = session.query(func.sum(Traffic.ingress), func.sum(Traffic.ingress_unlimited_range), func.sum(Traffic.ingress_shaped), func.sum(Traffic.ingress_excepted), func.sum(Traffic.egress), func.sum(Traffic.egress_unlimited_range), func.sum(Traffic.egress_shaped), func.sum(Traffic.egress_excepted)).filter_by(timestamp=date, reg_key=reg_key_query.id).all()
                ingress, ingress_unlimited_range, ingress_shaped, ingress_excepted, egress, egress_unlimited_range, egress_shaped, egress_excepted = traffic_query[0]

                if ingress is not None:
                    ingress = round(float(ingress), 3)
                if ingress_unlimited_range is not None:
                    ingress_unlimited_range = round(float(ingress_unlimited_range), 3)
                if ingress_shaped is not None:
                    ingress_shaped = round(float(ingress_shaped), 3)
                if ingress_excepted is not None:
                    ingress_excepted = round(float(ingress_excepted), 3)
                if egress is not None:
                    egress = round(float(egress), 3)
                if egress_unlimited_range is not None:
                    egress_unlimited_range = round(float(egress_unlimited_range), 3)
                if egress_shaped is not None:
                    egress_shaped = round(float(egress_shaped), 3)
                if egress_excepted is not None:
                    egress_excepted = round(float(egress_excepted), 3)


                values_downlink.append(self.__to_gib(ingress))
                values_downlink_unlimited_range.append(self.__to_gib(ingress_unlimited_range))
                values_downlink_shaped.append(self.__to_gib(ingress_shaped))
                values_downlink_excepted.append(self.__to_gib(ingress_excepted))
                values_uplink.append(self.__to_gib(egress))
                values_uplink_unlimited_range.append(self.__to_gib(egress_unlimited_range))
                values_uplink_shaped.append(self.__to_gib(egress_shaped))
                values_uplink_excepted.append(self.__to_gib(egress_excepted))
                labels.append(date.strftime("%d.%m."))
        except:
            session.rollback()
        finally:
            session.close()

        return values_downlink, values_downlink_unlimited_range, values_downlink_shaped, values_downlink_excepted, values_uplink, values_uplink_unlimited_range, values_uplink_shaped, values_uplink_excepted, labels


    #
    # Supervisor Login
    #

    def get_supervisor_dashboard_stats(self):
        session = self.db.create_session()

        today = datetime.today().date()
        passed_days = today - timedelta(days=10)

        values_downlink = []
        values_downlink_unlimited_range = []
        values_downlink_shaped = []
        values_downlink_excepted = []
        values_uplink = []
        values_uplink_unlimited_range = []
        values_uplink_shaped = []
        values_uplink_excepted = []
        labels = []

        try:
            for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
                traffic_query = session.query(func.sum(Traffic.ingress), func.sum(Traffic.ingress_unlimited_range), func.sum(Traffic.ingress_shaped), func.sum(Traffic.ingress_excepted), func.sum(Traffic.egress), func.sum(Traffic.egress_unlimited_range), func.sum(Traffic.egress_shaped), func.sum(Traffic.egress_excepted)).filter_by(timestamp=date).all()
                ingress, ingress_unlimited_range, ingress_shaped, ingress_excepted, egress, egress_unlimited_range, egress_shaped, egress_excepted = traffic_query[0]

                if ingress is not None:
                    ingress = round(float(ingress), 3)
                if ingress_unlimited_range is not None:
                    ingress_unlimited_range = round(float(ingress_unlimited_range), 3)
                if ingress_shaped is not None:
                    ingress_shaped = round(float(ingress_shaped), 3)
                if ingress_excepted is not None:
                    ingress_excepted = round(float(ingress_excepted), 3)
                if egress is not None:
                    egress = round(float(egress), 3)
                if egress_unlimited_range is not None:
                    egress_unlimited_range = round(float(egress_unlimited_range), 3)
                if egress_shaped is not None:
                    egress_shaped = round(float(egress_shaped), 3)
                if egress_excepted is not None:
                    egress_excepted = round(float(egress_excepted), 3)


                values_downlink.append(self.__to_gib(ingress))
                values_downlink_unlimited_range.append(self.__to_gib(ingress_unlimited_range))
                values_downlink_shaped.append(self.__to_gib(ingress_shaped))
                values_downlink_excepted.append(self.__to_gib(ingress_excepted))
                values_uplink.append(self.__to_gib(egress))
                values_uplink_unlimited_range.append(self.__to_gib(egress_unlimited_range))
                values_uplink_shaped.append(self.__to_gib(egress_shaped))
                values_uplink_excepted.append(self.__to_gib(egress_excepted))
                labels.append(date.strftime("%d.%m."))

            active_users = session.query(RegistrationKey).filter_by(active=True).count()
            registered_users = session.query(AddressPair).count()

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
                average_credit = round(average_credit / count, 3)
            else:
                average_credit = 0
        except:
            session.rollback()
        finally:
            session.close()

        return values_downlink, values_downlink_unlimited_range, values_downlink_shaped, values_downlink_excepted, values_uplink, values_uplink_unlimited_range, values_uplink_shaped, values_uplink_excepted, labels, active_users, registered_users, average_credit, shaped_users

    def get_reg_codes_search_results(self, search_term):
        session = self.db.create_session()

        search_results = []
        reg_key_query = []

        for query in session.query(RegistrationKey).all():
            if search_term in query.key:
                reg_key_query.append(query)
            else:
                identity = session.query(Identity).filter_by(id=query.identity).first()

                if search_term in identity.first_name.lower() or search_term in identity.last_name.lower() or search_term in identity.room.lower() or search_term in identity.mail.lower():
                    reg_key_query.append(query)
                else:
                    added = False
                    address_pair_query = session.query(AddressPair).filter_by(reg_key=query.id).first()

                    if address_pair_query is None:
                        continue

                    for ip_address_query in session.query(IpAddress).filter_by(id=address_pair_query.ip_address).all():
                        if search_term in ip_address_query.address_v4:
                            reg_key_query.append(query)
                            added = True
                            break
                        elif ip_address_query.address_v6 is not None:
                            if search_term in ip_address_query.address_v6:
                                reg_key_query.append(query)
                                break
                    
                    if added is False:
                        for mac_address_query in session.query(MacAddress).filter_by(id=address_pair_query.mac_address).all():
                            if search_term in mac_address_query.address:
                                reg_key_query.append(query)
                                break

        reg_key_query.reverse()

        for row in reg_key_query:
            identity = session.query(Identity).filter_by(id=row.identity).first()
            dormitory_query = session.query(Dormitory).filter_by(id=identity.dormitory_id).first()
            if dormitory_query:
                dormitory_name = dormitory_query.name
            else:
                dormitory_name = str(identity.dormitory_id)
            credit = self.accounting_srv.get_credit(session, row, gib=True)[0]
            if credit < 0:
                credit = 0
            
            key_row = KeyRow(row.key, identity.last_name, identity.first_name, dormitory_name, identity.room, credit, row.active)
            
            if identity.new_dormitory_id is not None or identity.new_room is not None:
                key_row.set_flag_move(True)
            
            if row.deletion_date is not None:
                key_row.set_flag_deletion(True)
            
            if self.accounting_srv.is_reg_key_shaped(session, row) is True:
                key_row.set_flag_shaped(True)
            
            if row.enable_accounting is False:
                key_row.set_flag_accounting_disabled(True)
            
            if row.daily_topup_volume is not None:
                key_row.set_flag_custom_settings(True)

            search_results.append(key_row)

        session.close()
        return search_results

    def get_reg_code_count(self):
        session = self.db.create_session()

        count = session.query(RegistrationKey).count()
        session.close()
        return count

    def get_dormitories(self):
        session = self.db.create_session()

        dormitories = []
        for dormitory in session.query(Dormitory).all():
            dormitories.append(dormitory.name)
        
        session.close()
        return dormitories

    def construct_reg_code_list(self, limit, offset):
        session = self.db.create_session()

        rows = []
        for row in session.query(RegistrationKey).order_by(RegistrationKey.id.desc()).offset(offset).limit(limit):
            identity = session.query(Identity).filter_by(id=row.identity).first()
            dormitory_query = session.query(Dormitory).filter_by(id=identity.dormitory_id).first()
            if dormitory_query:
                dormitory_name = dormitory_query.name
            else:
                dormitory_name = str(identity.dormitory_id)
            credit = self.accounting_srv.get_credit(session, row, gib=True)[0]
            if credit < 0:
                credit = 0

            key_row = KeyRow(row.key, identity.last_name, identity.first_name, dormitory_name, identity.room, credit, row.active)
            
            if identity.new_dormitory_id is not None or identity.new_room is not None:
                key_row.set_flag_move(True)
            
            if row.deletion_date is not None:
                key_row.set_flag_deletion(True)
            
            if self.accounting_srv.is_reg_key_shaped(session, row) is True:
                key_row.set_flag_shaped(True)
            
            if row.enable_accounting is False:
                key_row.set_flag_accounting_disabled(True)
            
            if row.daily_topup_volume is not None:
                key_row.set_flag_custom_settings(True)

            rows.append(key_row)

        session.close()
        return rows

    def add_registration_code(self, person_id, first_name, surname, mail, dormitory_id, room):
        try:
            session = self.db.create_session()

            identity = Identity(customer_id=person_id, first_name=first_name, last_name=surname, mail=mail, dormitory_id=dormitory_id, room=room, ib_needed=None, ib_expiry_date=None)
            session.add(identity)
            session.commit()

            reg_key = self.__generate_reg_key()

            session.add(RegistrationKey(key=reg_key, identity=identity.id))
            reg_key_query = session.query(RegistrationKey).filter_by(key=reg_key).first()

            session.add(Traffic(reg_key=reg_key_query.id, timestamp=datetime.today().date(), credit=config.INITIAL_VOLUME, ingress=0, egress=0, ingress_shaped=0, egress_shaped=0, ingress_unlimited_range=0, egress_unlimited_range=0, ingress_excepted=0, egress_excepted=0))
            session.commit()
        except:
            session.rollback()
        finally:
            session.close()
        
        self.accounting_srv.restart()

        return reg_key
    
    def edit_reg_key_identity(self, reg_key, person_id, first_name, surname, mail, dormitory_id, room, move_date):
        try:
            session = self.db.create_session()

            reg_key_query = session.query(RegistrationKey).filter_by(key=reg_key).first()
            identity_query = session.query(Identity).filter_by(id=reg_key_query.identity).first()

            identity_query.customer_id = int(person_id)
            identity_query.first_name = first_name
            identity_query.last_name = surname
            identity_query.mail = mail

            if move_date != "" and move_date is not None:
                if "." in move_date:
                    move_date = datetime.strptime(move_date, "%d.%m.%Y %H:%M:%S")
                else:
                    move_date = datetime.strptime(move_date, "%Y-%m-%d")
                identity_query.move_date = move_date
                identity_query.new_dormitory_id = dormitory_id
                identity_query.new_room = room
            else:
                identity_query.move_date = None
                identity_query.dormitory_id = dormitory_id
                identity_query.new_dormitory_id = None
                identity_query.room = room
                identity_query.new_room = None

            session.commit()
            success = True
        except:
            session.rollback()
            success = False
        finally:
            session.close()

        return success

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

    def set_reg_key_deactivated(self, reg_key, reason):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        success = self.accounting_srv.deactivate_registration_key(session, reg_key_query, reason)
        session.close()

        if not success:
            return False
        return True
    
    def is_reg_key_deactivated(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        session.close()

        if reg_key_query.active is True:
            return False
        else:
            return True

    def get_dormitory_id_from_name(self, dormitory_name):
        try:
            session = self.db.create_session()

            dormitory_query = session.query(Dormitory).filter_by(name=dormitory_name).first()
            dormitory_id = dormitory_query.id

            session.close()
            return dormitory_id
        except:
            return None
    
    def get_dormitory_name_from_id(self, dormitory_id):
        try:
            session = self.db.create_session()

            dormitory_query = session.query(Dormitory).filter_by(id=dormitory_id).first()
            dormitory_name = dormitory_query.name

            session.close()
            return dormitory_name
        except:
            return None
    
    def get_reg_key_deactivation_reason(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        reason = reg_key_query.deactivation_reason
        if reason == "":
            reason = None
        session.close()

        return reason

    def get_reg_key_deactivation_reason_by_ip(self, ip_address):
        session = self.db.create_session()
        reason = None

        try:
            ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
            address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
            reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)
            reason = reg_key_query.deactivation_reason
            if reason == "":
                reason = None
        except:
            session.rollback()
        finally:
            session.close()

        return reason

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
        values_downlink_unlimited_range = []
        values_downlink_shaped = []
        values_downlink_excepted = []
        values_uplink = []
        values_uplink_unlimited_range = []
        values_uplink_shaped = []
        values_uplink_excepted = []
        labels = []

        today = datetime.today().date()
        passed_days = today - timedelta(days=10)

        for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
            traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).all()
            downlink = 0
            downlink_unlimited_range = 0
            downlink_shaped = 0
            downlink_excepted = 0
            uplink = 0
            uplink_unlimited_range = 0
            uplink_shaped = 0
            uplink_excepted = 0

            if traffic_query is not None:
                for row in traffic_query:
                    downlink += self.__to_gib(row.ingress)
                    downlink_unlimited_range += self.__to_gib(row.ingress_unlimited_range)
                    downlink_shaped += self.__to_gib(row.ingress_shaped)
                    downlink_excepted += self.__to_gib(row.ingress_excepted)
                    uplink += self.__to_gib(row.egress)
                    uplink_unlimited_range += self.__to_gib(row.egress_unlimited_range)
                    uplink_shaped += self.__to_gib(row.egress_shaped)
                    uplink_excepted += self.__to_gib(row.egress_excepted)

            values_downlink.append(downlink)
            values_downlink_unlimited_range.append(downlink_unlimited_range)
            values_downlink_shaped.append(downlink_shaped)
            values_downlink_excepted.append(downlink_excepted)
            values_uplink.append(uplink)
            values_uplink_unlimited_range.append(uplink_unlimited_range)
            values_uplink_shaped.append(uplink_shaped)
            values_uplink_excepted.append(uplink_excepted)
            labels.append(date.strftime("%d.%m."))

        session.close()

        return stat_volume_left, stat_created_on, stat_shaped, stat_status, labels, values_downlink, values_downlink_unlimited_range, values_downlink_shaped, values_downlink_excepted, values_uplink, values_uplink_unlimited_range, values_uplink_shaped, values_uplink_excepted

    def get_reg_code_identity_data(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)
        identity = session.query(Identity).filter_by(id=reg_key_query.identity).first()

        if identity.move_date is None:
            identity_data = IdentityRow(identity.id, identity.customer_id, identity.last_name, identity.first_name, identity.mail, identity.dormitory_id, identity.new_dormitory_id, identity.room, identity.new_room, identity.move_date, identity.ib_needed, identity.ib_expiry_date)
        else:
            identity_data = IdentityRow(identity.id, identity.customer_id, identity.last_name, identity.first_name, identity.mail, identity.dormitory_id, identity.new_dormitory_id, identity.room, identity.new_room, identity.move_date.strftime("%d.%m.%Y %H:%M:%S"), identity.ib_needed, identity.ib_expiry_date)

        session.close()
        return identity_data
    
    def get_reg_code_identity_data_by_ip(self, ip_address):
        session = self.db.create_session()

        try:
            ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
            address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
            reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)
        except:
            session.rollback()
        finally:
            session.close()

        return self.get_reg_code_identity_data(reg_key_query.key)

    def get_reg_code_device_list(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        device_list = []
        for row in session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all():
            ip_address_query = session.query(IpAddress).filter_by(id=row.ip_address).first()
            mac_address_query = session.query(MacAddress).filter_by(id=row.mac_address).first()

            device_list.append(DeviceRow(ip_address_query.address_v4, mac_address_query.address, mac_address_query.user_agent, mac_address_query.vendor, mac_address_query.first_known_since))

        device_list.reverse()
        session.close()
        return device_list
    
    def get_reg_code_device_list_by_ip(self, ip_address):
        session = self.db.create_session()

        try:
            ip_address_query = self.get_ip_address_query_by_ip(session, ip_address)
            address_pair_query = self.get_address_pair_query_by_ip(session, ip_address_query)
            reg_key_query = self.get_reg_key_query_by_id(session, address_pair_query.reg_key)
        except:
            session.rollback()
        finally:
            session.close()

        return self.get_reg_code_device_list(reg_key_query.key)

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

        # Deletion Date
        deletion_date = reg_key_query.deletion_date
        if deletion_date is not None:
            deletion_date = deletion_date.strftime("%d.%m.%Y %H:%M:%S")

        session.close()
        return custom_volume_enabled, value_custom_topup, custom_max_enabled, value_max_volume, accounting_enabled, key_active, deletion_date

    def get_instruction_pdf_values(self):
        max_saved_volume = self.__to_gib(self.accounting_srv.get_max_saved_volume(), decimals=0)
        initial_volume = self.__to_gib(self.accounting_srv.get_initial_volume(), decimals=0)
        daily_topup_volume = self.__to_gib(self.accounting_srv.get_daily_topup_volume(), decimals=0)
        shaping_speed = config.SHAPING_SPEED
        traffy_ip = config.WAN_IP_ADDRESS
        traffy_domain = config.DOMAIN
        max_devices = config.MAX_MAC_ADDRESSES_PER_REG_KEY

        return max_saved_volume, initial_volume, daily_topup_volume, shaping_speed, traffy_ip, traffy_domain, max_devices

    def get_reg_code_identity(self, reg_key):
        session = self.db.create_session()
        reg_key_query = self.get_reg_key_query_by_key(session, reg_key)

        identity_query = session.query(Identity).filter_by(id=reg_key_query.identity).first()
        first_name = identity_query.first_name
        last_name = identity_query.last_name
        room = identity_query.room

        session.close()
        return first_name, last_name, room

    def is_erp_integration_enabled(self):
        return config.ENABLE_ERP_INTEGRATION

    def is_master_updates_available(self):
        session = self.db.create_session()
        identity_update_query = session.query(IdentityUpdate).all()

        if len(identity_update_query) > 0:
            return True
        else:
            return False

        session.close()

    def get_erp_integration_status(self):
        session = self.db.create_session()
        session.close()

    def get_identity_master_data_updates_createable(self):
        session = self.db.create_session()
        identity_update_query = session.query(IdentityUpdate).filter(and_(IdentityUpdate.new_customer_id != None,
                                                                     IdentityUpdate.old_customer_id == None,
                                                                     IdentityUpdate.identity_id == None)).all()

        identity_rows = []
        for identity in identity_update_query:
            if identity.ib_expiry_date is not None:
                ib_expiry_date = identity.ib_expiry_date.strftime("%Y-%m-%d")
            else:
                ib_expiry_date = ""

            remote_dormitory_id = session.query(Dormitory).filter_by(internal_id=identity.dormitory_id).first()

            if remote_dormitory_id is not None:
                remote_dormitory_name = remote_dormitory_id.name
            else:
                remote_dormitory_name = "N/A"

            identity_rows.append(IdentityRowUpdate(
                remote_id=None,
                remote_person_id=identity.new_customer_id,
                remote_last_name=identity.last_name,
                remote_first_name=identity.first_name,
                remote_mail=identity.mail,
                remote_dormitory=remote_dormitory_name,
                remote_room=identity.room,
                remote_ib_needed=identity.ib_needed,
                remote_ib_expiry_date=ib_expiry_date
            ))

        session.close()

        return identity_rows

    def get_identity_master_data_updates_updateable(self):
        session = self.db.create_session()
        identity_update_query = session.query(IdentityUpdate).filter(and_(IdentityUpdate.new_customer_id != None,
                                                                     IdentityUpdate.old_customer_id != None,
                                                                     IdentityUpdate.identity_id != None)).all()
        identity_rows = []
        for identity in identity_update_query:
            local_identity_query = session.query(Identity).filter_by(customer_id=identity.old_customer_id).first()
            if local_identity_query is None:
                continue

            if local_identity_query.ib_expiry_date is not None:
                local_ib_expiry_date = local_identity_query.ib_expiry_date.strftime("%Y-%m-%d")
            else:
                local_ib_expiry_date = ""

            if identity.ib_expiry_date is not None:
                remote_ib_expiry_date = identity.ib_expiry_date.strftime("%Y-%m-%d")
            else:
                remote_ib_expiry_date = ""

            local_dormitory_id = session.query(Dormitory).filter_by(id=local_identity_query.dormitory_id).first()
            remote_dormitory_id = session.query(Dormitory).filter_by(internal_id=identity.dormitory_id).first()

            if local_dormitory_id is not None:
                local_dormitory_name = local_dormitory_id.name
            else:
                local_dormitory_name = "N/A"

            if remote_dormitory_id is not None:
                remote_dormitory_name = remote_dormitory_id.name
            else:
                remote_dormitory_name = "N/A"

            identity_rows.append(IdentityRowUpdate(
                local_id=None,
                local_person_id=local_identity_query.customer_id,
                local_last_name=local_identity_query.last_name,
                local_first_name=local_identity_query.first_name,
                local_mail=local_identity_query.mail,
                local_dormitory=local_dormitory_name,
                local_room=local_identity_query.room,
                local_ib_needed=local_identity_query.ib_needed,
                local_ib_expiry_date=local_ib_expiry_date,
                remote_id=None,
                remote_person_id=identity.new_customer_id,
                remote_last_name=identity.last_name,
                remote_first_name=identity.first_name,
                remote_mail=identity.mail,
                remote_dormitory=remote_dormitory_name,
                remote_room=identity.room,
                remote_ib_needed=identity.ib_needed,
                remote_ib_expiry_date=remote_ib_expiry_date,
                do_difference_check=True
            ))

        session.close()

        return identity_rows

    def get_identity_master_data_updates_deletables(self):
        session = self.db.create_session()
        identity_update_query = session.query(IdentityUpdate).filter_by(new_customer_id=None).all()

        identity_rows = []
        for identity in identity_update_query:
            local_identity_query = session.query(Identity).filter_by(id=identity.identity_id).first()
            if local_identity_query is None:
                continue

            local_dormitory_id = session.query(Dormitory).filter_by(id=local_identity_query.dormitory_id).first()

            if local_dormitory_id is not None:
                local_dormitory_name = local_dormitory_id.name
            else:
                local_dormitory_name = "N/A"

            identity_rows.append(IdentityRowUpdate(
                local_id=local_identity_query.id,
                local_person_id=local_identity_query.customer_id,
                local_last_name=local_identity_query.last_name,
                local_first_name=local_identity_query.first_name,
                local_mail=local_identity_query.mail,
                local_dormitory=local_dormitory_name,
                local_room=local_identity_query.room,
                local_ib_needed=local_identity_query.ib_needed,
                local_ib_expiry_date=local_identity_query.ib_expiry_date
            ))

        session.close()

        return identity_rows

    #
    # Util / Private
    #

    def __to_gib(self, bytes, decimals=3):
        try:
            return round(bytes / 1073741824, decimals)
        except:
            return 0

    def __to_bytes(self, gib):
        return int(gib * 1073741824)
    
    def __is_ip_in_range(self, ip_address):
        in_range = False

        for subnet in config.IP_RANGES:
            min_ip = subnet[1].split('.')
            max_ip = subnet[3].split('.')
            ip = ip_address.split('.')

            for i in range(2, 3):
                if int(ip[i]) < int(min_ip[i]) or int(ip[i]) > int(max_ip[i]):
                    in_range = False
                    break
                else:
                    in_range = True

            if in_range is True:
                break
        
        return in_range
    
    def __get_mac_address_vendor(self, mac_address):
        api_url = "https://macvendors.co/api/"
        request = urllib2.Request(api_url + mac_address, headers={"User-Agent": "API Browser"})

        try:
            response = urllib2.urlopen(request, timeout=3)
            reader = codecs.getreader("utf-8")
            obj = json.load(reader(response))

            return(obj["result"]["company"])
        except:
            return("N/A")
    
    def __migration_init_vendor_column(self):
        session = self.db.create_session()
        for row in session.query(AddressPair).all():
            mac_address_query = session.query(MacAddress).filter_by(id=row.mac_address).first()
            if mac_address_query.vendor is None:
                try:
                    mac_address_query.vendor = self.__get_mac_address_vendor(mac_address_query.address)
                    session.commit()
                except:
                    session.rollback()
        session.close()
    
    def __generate_reg_key(self):
        return str(uuid.uuid4())

    def __get_mac_from_ip(self, ip_address):
        results = []
        with open(config.DNSMASQ_LEASE_FILE) as leases:
            for line in leases:
                elements = line.split()
                if len(elements) == 5:
                    if elements[2] == ip_address:
                        results.append(elements[1])
        if results:
            return results[-1]
        else:
            return None


class AccessMode():
    def __init__(self, unregistered=None, registered=None, outside_lan=None, no_lease=None, device_registered_with_different_port=None, deactivated=None, error=None):
        self.unregistered = unregistered
        self.registered = registered
        self.outside_lan = outside_lan
        self.no_lease = no_lease
        self.device_registered_with_different_port = device_registered_with_different_port
        self.deactivated = deactivated
        self.error = error


class KeyRow():
    reg_key = ""
    last_name = ""
    first_name = ""
    dormitory = ""
    room = ""
    credit = ""
    active = True
    flags = {}

    def __init__(self, reg_key, last_name, first_name, dormitory, room, credit, active):
        self.reg_key = reg_key
        self.last_name = last_name
        self.first_name = first_name
        self.dormitory = dormitory
        self.room = room
        self.credit = credit
        self.active = active
        self.flags = {
            "deletion": False,
            "shaped": False,
            "custom_settings": False,
            "accounting_disabled": False,
            "move": False
        }
    
    def set_flag_deletion(self, boolean):
        self.flags["deletion"] = boolean
    
    def set_flag_shaped(self, boolean):
        self.flags["shaped"] = boolean

    def set_flag_custom_settings(self, boolean):
        self.flags["custom_settings"] = boolean
    
    def set_flag_accounting_disabled(self, boolean):
        self.flags["accounting_disabled"] = boolean
    
    def set_flag_move(self, boolean):
        self.flags["move"] = boolean

class IdentityRow():
    id = ""
    person_id = ""
    last_name = ""
    first_name = ""
    mail = ""
    dormitory_id = ""
    new_dormitory_id = ""
    room = ""
    new_room = ""
    scheduled_move = ""
    ib_needed = ""
    ib_expiry_date = ""

    def __init__(self, id, person_id, last_name, first_name, mail, dormitory_id, new_dormitory_id, room, new_room, scheduled_move, ib_needed, ib_expiry_date):
        self.id = id
        self.person_id = str(person_id)
        self.last_name = last_name
        self.first_name = first_name
        self.mail = mail
        self.dormitory_id = dormitory_id
        self.new_dormitory_id = new_dormitory_id
        self.room = room
        self.new_room = new_room
        self.scheduled_move = scheduled_move
        self.ib_needed = ib_needed
        self.ib_expiry_date = ib_expiry_date

class IdentityRowUpdate():
    local_id = ""
    local_person_id = ""
    local_last_name = ""
    local_first_name = ""
    local_mail = ""
    local_dormitory = ""
    local_room = ""
    local_ib_needed = ""
    local_ib_expiry_date = ""

    remote_id = ""
    remote_person_id = ""
    remote_last_name = ""
    remote_first_name = ""
    remote_mail = ""
    remote_dormitory = ""
    remote_room = ""
    remote_ib_needed = ""
    remote_ib_expiry_date = ""

    different_id = False
    different_person_id = False
    different_last_name = False
    different_first_name = False
    different_mail = False
    different_dormitory = False
    different_room = False
    different_ib_needed = False
    different_ib_expiry_date = False

    def __init__(self,
                 local_id=None,
                 local_person_id=None,
                 local_last_name=None,
                 local_first_name=None,
                 local_mail=None,
                 local_dormitory=None,
                 local_room=None,
                 local_ib_needed=None,
                 local_ib_expiry_date=None,
                 remote_id=None,
                 remote_person_id=None,
                 remote_last_name=None,
                 remote_first_name=None,
                 remote_mail=None,
                 remote_dormitory=None,
                 remote_room=None,
                 remote_ib_needed=None,
                 remote_ib_expiry_date=None,
                 do_difference_check=False):
        self.local_id = local_id
        self.local_person_id = local_person_id
        self.local_last_name = local_last_name
        self.local_first_name = local_first_name
        self.local_mail = local_mail
        self.local_dormitory = local_dormitory
        self.local_room = local_room
        self.local_ib_needed = local_ib_needed
        self.local_ib_expiry_date = local_ib_expiry_date

        self.remote_id = remote_id
        self.remote_person_id = remote_person_id
        self.remote_last_name = remote_last_name
        self.remote_first_name = remote_first_name
        self.remote_mail = remote_mail
        self.remote_dormitory = remote_dormitory
        self.remote_room = remote_room
        self.remote_ib_needed = remote_ib_needed
        self.remote_ib_expiry_date = remote_ib_expiry_date

        if do_difference_check is True:
            self.__difference_check()

    def __difference_check(self):
        if self.local_id != self.remote_id:
            self.different_id = True
        if self.local_person_id != self.remote_person_id:
            self.different_person_id = True
        if self.local_last_name != self.remote_last_name:
            self.different_last_name = True
        if self.local_first_name != self.remote_first_name:
            self.different_first_name = True
        if self.local_mail != self.remote_mail:
            self.different_mail = True
        if self.local_dormitory != self.remote_dormitory:
            self.different_dormitory = True
        if self.local_room != self.remote_room:
            self.different_room = True
        if self.local_ib_needed != self.remote_ib_needed:
            self.different_ib_needed = True
        if self.local_ib_expiry_date != self.remote_ib_expiry_date:
            self.different_ib_expiry_date = True


class DeviceRow():
    ip_address = ""
    mac_address = ""
    type = ""
    vendor = ""
    registered_since = ""

    def __init__(self, ip_address, mac_address, user_agent, vendor, registered_since):
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.type = self.find_device(user_agent)
        self.vendor = vendor
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
