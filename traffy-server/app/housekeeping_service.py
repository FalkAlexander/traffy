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

from app.models import RegistrationKey, IpAddress, AddressPair, Traffic, Identity
from app.util import shaping_manager
from datetime import datetime, timedelta
from dateutil import rrule
import threading, time
import config
import logging


class HousekeepingService():
    db = NotImplemented
    interval = NotImplemented
    housekeeping_thread = NotImplemented
    server_api = NotImplemented

    def __init__(self, db):
        self.db = db

    #
    # Housekeeping Thread Management
    #

    def start(self, interval, server_api):
        self.interval = interval
        self.server_api = server_api

        self.housekeeping_thread = HousekeepingThread(self, interval, server_api)
        self.housekeeping_thread.daemon = True
        self.housekeeping_thread.start()

    def stop(self):
        self.housekeeping_thread.stop()

    def restart(self):
        self.stop()
        self.start(self.interval, self.server_api)


class HousekeepingThread(threading.Thread):
    running = True
    db = NotImplemented
    interval = NotImplemented
    housekeeping_srv = NotImplemented
    server_api = NotImplemented

    def __init__(self, housekeeping_srv, interval, server_api):
        super(HousekeepingThread, self).__init__()
        self.housekeeping_srv = housekeeping_srv
        self.interval = interval
        self.db = housekeeping_srv.db
        self.server_api = server_api

    def run(self):
        self.do_housekeeping()

    def stop(self):
        self.running = False

    def do_housekeeping(self):
        while self.running:
            try:
                session = self.db.create_session()
                self.__remove_orphaned_devices(session)
                session.close()

                session = self.db.create_session()
                self.__remove_orphaned_reg_keys(session)
                session.close()
            except:
                session.rollback()
                logging.error("Exception thrown in Housekeeping Service")
            finally:
                session.close()

            time.sleep(self.interval)
    
    def __remove_orphaned_devices(self, session):
        moving_users = session.query(Identity).filter(Identity.move_date != None).all()
        for row in moving_users:
            if row.move_date <= datetime.now():
                reg_key_query = session.query(RegistrationKey).filter(RegistrationKey.identity == row.id).first()
                address_pair_query = session.query(AddressPair).filter(AddressPair.reg_key == reg_key_query.id).all()
                for device in address_pair_query:
                    ip_address = session.query(IpAddress).filter_by(id=device.ip_address).first()
                    self.server_api.deregister_device(ip_address.address_v4)

                identity_query = session.query(Identity).filter(Identity.id == reg_key_query.identity).first()
                identity_query.room = identity_query.new_room
                identity_query.new_room = None
                identity_query.new_dormitory_id = None
                identity_query.move_date = None
                session.commit()

                logging.info("Moved user into a new room")

    def __remove_orphaned_reg_keys(self, session):
        deletion_keys = session.query(RegistrationKey).filter(RegistrationKey.deletion_date != None).all()
        for row in deletion_keys:
            if row.deletion_date <= datetime.now():
                self.server_api.delete_registration_key(row.key, "")

