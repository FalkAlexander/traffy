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

from app.models import RegistrationKey, IpAddress, MacAddress, AddressPair, Traffic, Identity
from datetime import datetime, timedelta
from dateutil import rrule
import threading, time
import config
import logging


class AccountingService():
    db = NotImplemented
    commander = NotImplemented
    accounting_thread = NotImplemented
    shaped_reg_keys = []

    def __init__(self, db, commander):
        self.db = db
        self.commander = commander

    #
    # Accounting Threads Management
    #

    def start(self):
        self.accounting_thread = AccountingThread(self)
        self.accounting_thread.daemon = True
        self.accounting_thread.start()

    def stop(self):
        self.accounting_thread.stop()

    def restart(self):
        self.stop()
        self.start()

    #
    # Out of Interval Traffic Actions
    #

    def add_extra_credit(self, session, reg_key_query, amount_gib):
        traffic_query = self.__verify_todays_traffic_query(session, reg_key_query)

        try:
            amount_gib = self.__string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            credit = traffic_query.credit + self.__to_bytes(amount_gib) + self.get_ingress_egress_amount(traffic_query)

            if credit < 0:
                credit = 0

            traffic_query.credit = credit
            session.commit()
            return self.__to_gib(traffic_query.credit)
        except:
            session.rollback()
            return False

    def set_custom_credit(self, session, reg_key_query, amount_gib):
        traffic_query = self.__verify_todays_traffic_query(session, reg_key_query)

        try:
            amount_gib = self.__string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            traffic_query.credit = self.__to_bytes(amount_gib) + self.get_ingress_egress_amount(traffic_query)
            session.commit()
            return self.__to_gib(traffic_query.credit)
        except:
            session.rollback()
            return False

    def set_custom_topup(self, session, reg_key_query, amount_gib):
        try:
            amount_gib = self.__string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            reg_key_query.daily_topup_volume = self.__to_bytes(amount_gib)
            session.commit()
            return self.__to_gib(reg_key_query.daily_topup_volume)
        except:
            session.rollback()
            return False

    def set_custom_max_volume(self, session, reg_key_query, amount_gib):
        try:
            amount_gib = self._string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            reg_key_query.max_volume = self.__to_bytes(amount_gib)
            session.commit()
            return self.__to_gib(reg_key_query.max_volume)
        except:
            session.rollback()
            return False

    def disable_custom_topup(self, session, reg_key_query):
        try:
            reg_key_query.daily_topup_volume = None
            session.commit()
            return True
        except:
            session.rollback()
            return False

    def disable_custom_max_volume(self, session, reg_key_query):
        try:
            reg_key_query.max_volume = None
            session.commit()
            return True
        except:
            session.rollback()
            return False

    def enable_accounting_for_reg_key(self, session, reg_key_query):
        try:
            reg_key_query.enable_accounting = True
            session.commit()
            return True
        except:
            session.rollback()
            return False

    def disable_accounting_for_reg_key(self, session, reg_key_query):
        try:
            reg_key_query.enable_accounting = False
            session.commit()
            return True
        except:
            session.rollback()
            return False

    def activate_registration_key(self, session, reg_key_query):
        try:
            reg_key_query.active = True
            reg_key_query.deactivation_reason = None
            session.commit()

            address_pair_query = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all()

            if len(address_pair_query) > 0:
                self.commander.add_reg_key_set(str(reg_key_query.id))

            for row in address_pair_query:
                ip_address_query = session.query(IpAddress).filter_by(id=row.ip_address).first()
                mac_address_query = session.query(MacAddress).filter_by(id=row.mac_address).first()

                # Setup Firewall
                self.commander.add_allocation_to_registered_set(mac_address_query.address, ip_address_query.address_v4)

                # Setup Accounting
                self.commander.add_ip_to_reg_key_set(ip_address_query.address_v4, str(reg_key_query.id))

                # Setup Shaping
                if self.is_reg_key_shaped(session, reg_key_query):
                    self.commander.enable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

            if len(address_pair_query) > 0:
                self.commander.add_accounting_matching_rules(str(reg_key_query.id))

            return True
        except:
            session.rollback()
            return False

    def deactivate_registration_key(self, session, reg_key_query, reason):
        try:
            address_pair_query = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).all()

            if len(address_pair_query) > 0:
                # Disable Accounting
                self.commander.delete_accounting_matching_rules(str(reg_key_query.id))
                self.commander.delete_reg_key_set(str(reg_key_query.id))

            for row in address_pair_query:
                ip_address_query = session.query(IpAddress).filter_by(id=row.ip_address).first()
                mac_address_query = session.query(MacAddress).filter_by(id=row.mac_address).first()

                # Disable Shaping
                if self.is_reg_key_shaped(session, reg_key_query):
                    self.commander.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

                # Setup Firewall
                self.commander.delete_allocation_from_registered_set(mac_address_query.address, ip_address_query.address_v4)

            if reason is not None:
                if len(reason) <= 250:
                    reg_key_query.deactivation_reason = reason
                elif len(reason) > 250:
                    reg_key_query.deactivation_reason = reason[:250]
            else:
                reg_key_query.deactivation_reason = None

            reg_key_query.active = False
            session.commit()

            return True
        except:
            session.rollback()
            return False

    def is_registration_key_active(self, reg_key_query):
        try:
            return reg_key_query.active
        except:
            return False

    def is_reg_key_shaped(self, session, reg_key_query):
        try:
            date = datetime.today().date()
            traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).first()
            if traffic_query.ingress + traffic_query.egress >= traffic_query.credit or traffic_query.credit <= 0:
                return True
            else:
                return False
        except:
            return 0

    def get_reg_key_creation_timestamp(self, reg_key_query, format):
        try:
            return reg_key_query.created_on.strftime(format)
        except:
            return "N/A"

    #
    # Traffic Value Getters
    #

    def get_ingress_egress_amount(self, traffic_query, gib=False):
        try:
            ingress_egress = traffic_query.ingress + traffic_query.egress
        except:
            ingress_egress = 0

        if gib is True:
            return round(ingress_egress * 1073741824, 2)
        else:
            return ingress_egress

    def get_credit(self, session, reg_key_query, gib=False, decimals=3):
        traffic_query = self.__verify_todays_traffic_query(session, reg_key_query)

        try:
            credit = traffic_query.credit
        except:
            credit = 0

        volume_left = credit - self.get_ingress_egress_amount(traffic_query)

        initial_volume = self.get_initial_volume()
        max_saved_volume = self.get_max_saved_volume()

        if volume_left > max_saved_volume:
            max_saved_volume = credit

        if traffic_query is None:
            if gib is True:
                return self.__to_gib(initial_volume, decimals), self.__to_gib(max_saved_volume, decimals)
            else:
                return initial_volume, max_saved_volume
        else:
            if gib is True:
                return self.__to_gib(volume_left, decimals), self.__to_gib(max_saved_volume, decimals)
            else:
                return volume_left, max_saved_volume

    def get_daily_topup_volume(self, gib=False):
        if gib is True:
            return self.__to_gib(config.DAILY_TOPUP_VOLUME, decimals=1)
        else:
            return config.DAILY_TOPUP_VOLUME

    def get_max_saved_volume(self, gib=False):
        if gib is True:
            return self.__to_gib(config.MAX_SAVED_VOLUME, decimals=1)
        else:
            return config.MAX_SAVED_VOLUME

    def get_initial_volume(self, gib=False):
        if gib is True:
            return self.__to_gib(config.INITIAL_VOLUME, decimals=1)
        else:
            return config.INITIAL_VOLUME

    #
    # Private Functions
    #

    def __verify_todays_traffic_query(self, session, reg_key_query):
        date = datetime.today().date()
        traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).first()

        if traffic_query is None:
            date = date - timedelta(days = 1)
            traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).first()
            if traffic_query is None:
                return None

        return traffic_query

    def __to_gib(self, bytes, decimals=3):
        return round(bytes / 1073741824, decimals)

    def __to_bytes(self, gib):
        return int(gib * 1073741824)

    def __string_to_float(self, value):
        if value == "":
            raise ValueError("String given was empty")
        try:
            return float(value)
        except:
            raise ValueError("String given can not be transformed")


class AccountingThread(threading.Thread):
    run = True
    db = NotImplemented
    commander = NotImplemented
    accounting_srv = NotImplemented

    def __init__(self, accounting_srv):
        super(AccountingThread, self).__init__()
        self.accounting_srv = accounting_srv
        self.db = accounting_srv.db
        self.commander = accounting_srv.commander

    def run(self):
        self.query_active_boxes()

    def stop(self):
        self.run = False

    def query_active_boxes(self):
        while self.run:
            try:
                time.sleep(config.ACCOUNTING_INTERVAL)

                session = self.db.create_session()
                reg_key_query = session.query(RegistrationKey).all()

                counters = self.commander.get_counter_values()
                self.commander.reset_counter_values()

                for reg_key in reg_key_query:
                    if reg_key.active is False or reg_key.enable_accounting is False:
                        continue

                    if session.query(AddressPair).filter_by(reg_key=reg_key.id).count() != 0:
                        self.update_interval_used_traffic(session,
                                                        reg_key,
                                                        counters.get(str(reg_key.id) + "-ingress"),
                                                        counters.get(str(reg_key.id) + "-egress"),
                                                        counters.get(str(reg_key.id) + "-ingress-exc"),
                                                        counters.get(str(reg_key.id) + "-egress-exc"))
                    else:
                        self.update_interval_used_traffic(session, reg_key, 0, 0, 0, 0, inactive=True)
            except:
                session.rollback()
                logging.debug("Exception thrown in Accounting Service")
            finally:
                session.close()

    #
    # Calculate User Credit and Ingress / Egress
    #

    def update_interval_used_traffic(self, session, reg_key_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used, inactive=False):
        # Every X Seconds Check
        date = datetime.today().date()
        traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).first()

        in_unlimited_time_range = False
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        try:
            for range in config.TIME_RANGES_UNLIMITED_DATA:
                start = range[0]
                end = range[1]
                if current_time > start and current_time < end:
                    in_unlimited_time_range = True
                    break
        except:
            in_unlimited_time_range = False

        if traffic_query is not None:
            credit = traffic_query.credit

            if traffic_query.ingress + traffic_query.egress + ingress_used + egress_used >= credit or credit <= 0:
                if inactive:
                    return

                if reg_key_query.id in self.accounting_srv.shaped_reg_keys:
                    self.__update_traffic_shaped_values(session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used)
                else:
                    if in_unlimited_time_range is True:
                        self.__update_traffic_unlimited_range_values(session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used)
                    else:
                        self.__update_traffic_values(session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used)
                    self.accounting_srv.shaped_reg_keys.append(reg_key_query.id)
                    self.__enable_traffic_shaping_for_reg_key(session, reg_key_query)

                    identity_query = session.query(Identity).filter_by(id=reg_key_query.identity).first()
            else:
                if inactive:
                    return

                if reg_key_query.id not in self.accounting_srv.shaped_reg_keys:
                    if in_unlimited_time_range is True:
                        self.__update_traffic_unlimited_range_values(session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used)
                    else:
                        self.__update_traffic_values(session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used)
                else:
                    self.__disable_traffic_shaping_for_reg_key(session, reg_key_query)
                    self.__update_traffic_shaped_values(session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used)
                    self.accounting_srv.shaped_reg_keys.remove(reg_key_query.id)

            return

        # New Day Check
        date = date - timedelta(days = 1)
        traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=date).first()

        topup_volume = self.accounting_srv.get_daily_topup_volume()
        if reg_key_query.daily_topup_volume is not None:
            topup_volume = reg_key_query.daily_topup_volume

        if traffic_query is not None:
            date = datetime.today().date()

            credit = traffic_query.credit
            ingress = traffic_query.ingress
            egress = traffic_query.egress

            if traffic_query.credit <= 0:
                credit = topup_volume
            else:
                credit = (credit - (ingress + egress)) + topup_volume
                max_volume = self.accounting_srv.get_max_saved_volume()
                if reg_key_query.max_volume is not None:
                    max_volume = reg_key_query.max_volume

                if credit > max_volume:
                    credit = max_volume

            try:
                if in_unlimited_time_range is True:
                    row = Traffic(reg_key=reg_key_query.id,
                              timestamp=date,
                              credit=credit,
                              ingress=0,
                              egress=0,
                              ingress_shaped=0,
                              egress_shaped=0,
                              ingress_unlimited_range=ingress_used,
                              egress_unlimited_range=egress_used,
                              ingress_excepted=ingress_excepted_used,
                              egress_excepted=egress_excepted_used)
                else:
                    row = Traffic(reg_key=reg_key_query.id,
                                timestamp=date,
                                credit=credit,
                                ingress=ingress_used,
                                egress=egress_used,
                                ingress_shaped=0,
                                egress_shaped=0,
                                ingress_unlimited_range=0,
                                egress_unlimited_range=0,
                                ingress_excepted=ingress_excepted_used,
                                egress_excepted=egress_excepted_used)
                session.add(row)
                session.commit()
            except:
                session.rollback()

            return

        # First Ever Check
        date = datetime.today().date()
        if session.query(Traffic).filter_by(reg_key=reg_key_query.id).count() == 0:
            initial_volume = self.accounting_srv.get_initial_volume()
            try:
                if in_unlimited_time_range is True:
                    row = Traffic(reg_key=reg_key_query.id,
                                      timestamp=date,
                                      credit=initial_volume,
                                      ingress=0,
                                      egress=0,
                                      ingress_shaped=0,
                                      egress_shaped=0,
                                      ingress_unlimited_range=ingress_used,
                                      egress_unlimited_range=egress_used,
                                      ingress_excepted=ingress_excepted_used,
                                      egress_excepted=egress_excepted_used)
                else:
                    row = Traffic(reg_key=reg_key_query.id,
                                        timestamp=date,
                                        credit=initial_volume,
                                        ingress=ingress_used,
                                        egress=egress_used,
                                        ingress_shaped=0,
                                        egress_shaped=0,
                                        ingress_unlimited_range=0,
                                        egress_unlimited_range=0,
                                        ingress_excepted=ingress_excepted_used,
                                        egress_excepted=egress_excepted_used)

                session.add(row)
                session.commit()
            except:
                session.rollback()

            return
        else:
            # Missing Traffic Entries
            day_range = int(self.accounting_srv.get_max_saved_volume(gib=True) / self.accounting_srv.get_daily_topup_volume(gib=True))
            volume_start_day = date - timedelta(days=day_range)
            collected_credit = 0
            days_iterative = []
            for day in rrule.rrule(rrule.DAILY, dtstart=volume_start_day, until=date):
                days_iterative.append(day)

            days_iterative.reverse()

            for day in days_iterative:
                traffic_query = session.query(Traffic).filter_by(reg_key=reg_key_query.id, timestamp=day).first()
                if traffic_query is not None:
                    collected_credit = traffic_query.credit + self.accounting_srv.get_daily_topup_volume()
                    break

            try:
                if in_unlimited_time_range is True:
                    row = Traffic(reg_key=reg_key_query.id,
                                timestamp=date,
                                credit=collected_credit,
                                ingress=0,
                                egress=0,
                                ingress_shaped=0,
                                egress_shaped=0,
                                ingress_unlimited_range=ingress_used,
                                egress_unlimited_range=egress_used,
                                ingress_excepted=ingress_excepted_used,
                                egress_excepted=egress_excepted_used)
                else:
                    row = Traffic(reg_key=reg_key_query.id,
                                timestamp=date,
                                credit=collected_credit,
                                ingress=ingress_used,
                                egress=egress_used,
                                ingress_shaped=0,
                                egress_shaped=0,
                                ingress_unlimited_range=0,
                                egress_unlimited_range=0,
                                ingress_excepted=ingress_excepted_used,
                                egress_excepted=egress_excepted_used)

                session.add(row)
                session.commit()
            except:
                session.rollback()

            return

    def __update_traffic_values(self, session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used):
        try:
            traffic_query.ingress = traffic_query.ingress + ingress_used
            traffic_query.egress = traffic_query.egress + egress_used
            traffic_query.ingress_excepted = traffic_query.ingress_excepted + ingress_excepted_used
            traffic_query.egress_excepted = traffic_query.egress_excepted + egress_excepted_used
            session.commit()
        except Exception as ex:
            session.rollback()

    def __update_traffic_shaped_values(self, session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used):
        try:
            traffic_query.ingress_shaped = traffic_query.ingress_shaped + ingress_used
            traffic_query.egress_shaped = traffic_query.egress_shaped + egress_used
            traffic_query.ingress_excepted = traffic_query.ingress_excepted + ingress_excepted_used
            traffic_query.egress_excepted = traffic_query.egress_excepted + egress_excepted_used
            session.commit()
        except:
            session.rollback()
    
    def __update_traffic_unlimited_range_values(self, session, traffic_query, ingress_used, egress_used, ingress_excepted_used, egress_excepted_used):
        try:
            traffic_query.ingress_unlimited_range = traffic_query.ingress_unlimited_range + ingress_used
            traffic_query.egress_unlimited_range = traffic_query.egress_unlimited_range + egress_used
            traffic_query.ingress_excepted = traffic_query.ingress_excepted + ingress_excepted_used
            traffic_query.egress_excepted = traffic_query.egress_excepted + egress_excepted_used
            session.commit()
        except:
            session.rollback()

    def __enable_traffic_shaping_for_reg_key(self, session, reg_key_query):
        address_pair_query = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).distinct()
        for query in address_pair_query:
            ip_address_query = session.query(IpAddress).filter_by(id=query.ip_address).first()
            self.commander.enable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    def __disable_traffic_shaping_for_reg_key(self, session, reg_key_query):
        address_pair_query = session.query(AddressPair).filter_by(reg_key=reg_key_query.id).distinct()
        for query in address_pair_query:
            ip_address_query = session.query(IpAddress).filter_by(id=query.ip_address).first()
            self.commander.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

