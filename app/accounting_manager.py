from app.models import RegistrationKey, IpAddress, AddressPair, Traffic
from app.util import iptables_accounting_manager, iptables_rules_manager, shaping_manager, helpers
from datetime import datetime, timedelta
from dateutil import rrule
import threading, time
import config
import logging


class AccountingService():
    db = NotImplemented
    app = NotImplemented
    run = True
    shaped_reg_keys = []

    def __init__(self, db):
        self.db = db

    #
    # Accounting Thread Management
    #

    def start(self, interval):
        thread = threading.Thread(target=self.query_active_boxes, args=[interval, self.app])
        thread.daemon = True
        thread.start()

    def stop(self):
        self.run = False

    def query_active_boxes(self, interval, app):
        while self.run:
            with app.app_context():
                logging.debug("Begin collecting accounting data")
                reg_key_query = RegistrationKey.query.all()
                for reg_key in reg_key_query:
                    if reg_key.active is False or reg_key.enable_accounting is False:
                        continue

                    if AddressPair.query.filter_by(reg_key=reg_key.id).count() != 0:
                        self.update_interval_used_traffic(reg_key,
                                                          iptables_accounting_manager.get_box_ingress_bytes(reg_key.id),
                                                          iptables_accounting_manager.get_box_egress_bytes(reg_key.id))
                    else:
                        self.update_interval_used_traffic(reg_key, 0, 0, inactive=True)
                logging.debug("Finished collecting accounting data")

            time.sleep(interval)

    #
    # Calculate User Credit and Ingress / Egress
    #

    def update_interval_used_traffic(self, reg_key_query, ingress_used, egress_used, inactive=False):
        # Every X Seconds Check
        date = datetime.today().date()
        traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id, timestamp=date).first()

        if traffic_query is not None:
            credit = traffic_query.credit

            if traffic_query.ingress + traffic_query.egress >= credit or credit <= 0:
                traffic_query.ingress_shaped = traffic_query.ingress_shaped + ingress_used
                traffic_query.egress_shaped = traffic_query.egress_shaped + egress_used

                self.db.session.commit()

                if not inactive:
                    self.traffic_limit_exceeded(reg_key_query)
            else:
                traffic_query.ingress = traffic_query.ingress + ingress_used
                traffic_query.egress = traffic_query.egress + egress_used

                self.db.session.commit()
                if not inactive:
                    self.traffic_limit_obeyed(reg_key_query)

            if not inactive:
                iptables_accounting_manager.reset_box_counter(reg_key_query.id)
            return

        # New Day Check
        date = date - timedelta(days = 1)
        traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id, timestamp=date).first()

        topup_volume = self.get_daily_topup_volume()
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
                max_volume = self.get_max_saved_volume()
                if reg_key_query.max_volume is not None:
                    max_volume = reg_key_query.max_volume

                if credit > max_volume:
                    credit = max_volume

            row = Traffic(reg_key=reg_key_query.id,
                          timestamp=date,
                          credit=credit,
                          ingress=ingress_used,
                          egress=egress_used,
                          ingress_shaped=0,
                          egress_shaped=0)
            self.db.session.add(row)
            self.db.session.commit()

            if not inactive:
                iptables_accounting_manager.reset_box_counter(reg_key_query.id)
            return

        # First Ever Check
        date = datetime.today().date()
        if Traffic.query.filter_by(reg_key=reg_key_query.id).count() == 0:
            row = Traffic(reg_key=reg_key_query.id,
                                  timestamp=date,
                                  credit=topup_volume,
                                  ingress=ingress_used,
                                  egress=egress_used,
                                  ingress_shaped=0,
                                  egress_shaped=0)

            self.db.session.add(row)
            self.db.session.commit()

            if not inactive:
                iptables_accounting_manager.reset_box_counter(reg_key_query.id)
            return
        else:
            # Missing Traffic Entries
            day_range = int(self.get_max_saved_volume(gib=True) / self.get_daily_topup_volume(gib=True))
            volume_start_day = date - timedelta(days=day_range)
            collected_credit = 0
            days_iterative = []
            for day in rrule.rrule(rrule.DAILY, dtstart=volume_start_day, until=date):
                days_iterative.append(day)

            days_iterative.reverse()

            for day in days_iterative:
                traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id, timestamp=day).first()
                if traffic_query is not None:
                    collected_credit = traffic_query.credit + self.get_daily_topup_volume()
                    break

            row = Traffic(reg_key=reg_key_query.id,
                          timestamp=date,
                          credit=collected_credit,
                          ingress=ingress_used,
                          egress=egress_used,
                          ingress_shaped=0,
                          egress_shaped=0)

            self.db.session.add(row)
            self.db.session.commit()

            if not inactive:
                iptables_accounting_manager.reset_box_counter(reg_key_query.id)
            return

    #
    # In Interval Traffic Actions
    #

    def traffic_limit_exceeded(self, reg_key_query):
        if reg_key_query.id in self.shaped_reg_keys:
            return

        self.shaped_reg_keys.append(reg_key_query.id)
        self.__enable_traffic_shaping_for_reg_key(reg_key_query)

    def traffic_limit_obeyed(self, reg_key_query):
        if reg_key_query.id not in self.shaped_reg_keys:
            return

        self.__disable_traffic_shaping_for_reg_key(reg_key_query)
        self.shaped_reg_keys.remove(reg_key_query.id)

    #
    # Out of Interval Traffic Actions
    #

    def add_extra_credit(self, reg_key_query, amount_gib):
        traffic_query = self.__verify_todays_traffic_query(reg_key_query)

        try:
            amount_gib = helpers.string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            credit = traffic_query.credit + self.__to_bytes(amount_gib) + self.get_ingress_egress_amount(traffic_query)

            if credit < 0:
                credit = 0

            traffic_query.credit = credit
            self.db.session.commit()
            return self.__to_gib(traffic_query.credit)
        except:
            return False

    def set_custom_credit(self, reg_key_query, amount_gib):
        traffic_query = self.__verify_todays_traffic_query(reg_key_query)

        try:
            amount_gib = helpers.string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            traffic_query.credit = self.__to_bytes(amount_gib) + self.get_ingress_egress_amount(traffic_query)
            self.db.session.commit()
            return self.__to_gib(traffic_query.credit)
        except:
            return False

    def set_custom_topup(self, reg_key_query, amount_gib):
        try:
            amount_gib = helpers.string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            reg_key_query.daily_topup_volume = self.__to_bytes(amount_gib)
            self.db.session.commit()
            return self.__to_gib(reg_key_query.daily_topup_volume)
        except:
            return False

    def set_custom_max_volume(self, reg_key_query, amount_gib):
        try:
            amount_gib = helpers.string_to_float(amount_gib)
            if not amount_gib > 0 or amount_gib > 999:
                return False

            reg_key_query.max_volume = self.__to_bytes(amount_gib)
            self.db.session.commit()
            return self.__to_gib(reg_key_query.max_volume)
        except:
            return False

    def disable_custom_topup(self, reg_key_query):
        try:
            reg_key_query.daily_topup_volume = None
            self.db.session.commit()
            return True
        except:
            return False

    def disable_custom_max_volume(self, reg_key_query):
        try:
            reg_key_query.max_volume = None
            self.db.session.commit()
            return True
        except:
            return False

    def enable_accounting_for_reg_key(self, reg_key_query):
        try:
            reg_key_query.enable_accounting = True
            self.db.session.commit()
            return True
        except:
            return False

    def disable_accounting_for_reg_key(self, reg_key_query):
        try:
            reg_key_query.enable_accounting = False
            self.traffic_limit_obeyed(reg_key_query)
            self.db.session.commit()
            return True
        except:
            return False

    def activate_registration_key(self, reg_key_query):
        try:
            reg_key_query.active = True
            self.db.session.commit()

            address_pair_query = AddressPair.query.filter_by(reg_key=reg_key_query.id).all()
            for row in address_pair_query:
                ip_address_query = IpAddress.query.filter_by(id=row.ip_address).first()

                # Setup Firewall
                iptables_rules_manager.unlock_registered_device(ip_address_query.address_v4)

                # Setup Accounting
                if AddressPair.query.filter_by(reg_key=reg_key_query.id).count() <= 1:
                    iptables_accounting_manager.add_accounter_chain(reg_key_query.id)
                    iptables_accounting_manager.add_ip_to_box(reg_key_query.id, ip_address_query.address_v4)
                else:
                    iptables_accounting_manager.add_ip_to_box(reg_key_query.id, ip_address_query.address_v4)

                # Setup Shaping
                if reg_key_query.id in self.shaped_reg_keys:
                    shaping_manager.enable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

            return True
        except:
            return False

    def deactivate_registration_key(self, reg_key_query):
        try:
            reg_key_query.active = False
            self.db.session.commit()

            address_pair_query = AddressPair.query.filter_by(reg_key=reg_key_query.id).all()
            for row in address_pair_query:
                ip_address_query = IpAddress.query.filter_by(id=row.ip_address).first()

                # Disable Shaping
                if reg_key_query.id in self.shaped_reg_keys:
                    shaping_manager.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

                # Disable Accounting
                if AddressPair.query.filter_by(reg_key=reg_key_query.id).count() == 0:
                    iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address_query.address_v4)
                    iptables_accounting_manager.remove_accounter_chain(reg_key_query.id)
                else:
                    iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address_query.address_v4)

                # Setup Firewall
                iptables_rules_manager.relock_registered_device(ip_address_query.address_v4)

            return True
        except:
            return False

    def is_registration_key_active(self, reg_key_query):
        try:
            return reg_key_query.active
        except:
            return False

    def get_count_shaped_reg_keys(self, traffic_query):
        try:
            return traffic_query.id in self.shaped_reg_keys
        except:
            return 0

    def get_reg_key_creation_timestamp(self, reg_key_query, format):
        try:
            return reg_key_query.created_on.strftime(format)
        except:
            return _l("Error")

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

    def get_credit(self, reg_key_query, gib=False, decimals=3):
        traffic_query = self.__verify_todays_traffic_query(reg_key_query)

        try:
            credit = traffic_query.credit
        except:
            credit = 0

        volume_left = credit - self.get_ingress_egress_amount(traffic_query)

        daily_topup_volume = self.get_daily_topup_volume()
        max_saved_volume = self.get_max_saved_volume()

        if traffic_query is None:
            if gib is True:
                return self.__to_gib(daily_topup_volume, decimals), self.__to_gib(daily_topup_volume, decimals)
            else:
                return daily_topup_volume, daily_topup_volume
        else:
            if gib is True:
                return self.__to_gib(volume_left, decimals), self.__to_gib(credit, decimals)
            else:
                return volume_left, credit

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

    #
    # Private Functions
    #

    def __enable_traffic_shaping_for_reg_key(self, reg_key_query):
        address_pair_query = AddressPair.query.filter_by(reg_key=reg_key_query.id).distinct()
        for query in address_pair_query:
            ip_address_query = IpAddress.query.filter_by(id=query.ip_address).first()
            shaping_manager.enable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    def __disable_traffic_shaping_for_reg_key(self, reg_key_query):
        address_pair_query = AddressPair.query.filter_by(reg_key=reg_key_query.id).distinct()
        for query in address_pair_query:
            ip_address_query = IpAddress.query.filter_by(id=query.ip_address).first()
            shaping_manager.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    def __verify_todays_traffic_query(self, reg_key_query):
        date = datetime.today().date()
        traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id, timestamp=date).first()

        if traffic_query is None:
            date = date - timedelta(days = 1)
            traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id, timestamp=date).first()
            if traffic_query is None:
                return None

        return traffic_query

    def __to_gib(self, bytes, decimals=3):
        return round(bytes / 1073741824, decimals)

    def __to_bytes(self, gib):
        return int(gib * 1073741824)

