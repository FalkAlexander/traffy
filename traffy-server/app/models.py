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

from datetime import datetime
from sqlalchemy.sql import text
from sqlalchemy.ext.declarative import declarative_base
import sqlalchemy as db


Base = declarative_base()

class RegistrationKey(Base):
    __tablename__ = "registration_key"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    created_on = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean(True), nullable=False)
    eula_accepted = db.Column(db.Boolean(False), nullable=False)
    identity = db.Column(db.BigInteger, db.ForeignKey("identity.id"))
    enable_accounting = db.Column(db.Boolean(True), nullable=False)
    daily_topup_volume = db.Column(db.BigInteger, nullable=True)
    max_volume = db.Column(db.BigInteger, nullable=True)
    block_traffic = db.Column(db.Boolean(False), nullable=False)
    ingress_speed = db.Column(db.BigInteger, nullable=True)
    egress_speed = db.Column(db.BigInteger, nullable=True)
    activation_date = db.Column(db.DateTime, nullable=True)
    deletion_date = db.Column(db.DateTime, nullable=True)
    deactivation_reason = db.Column(db.String(250), nullable=True)
    
    def __init__(self, key, identity):
        self.key = key
        self.created_on = datetime.now()
        self.active = True
        self.eula_accepted = False
        self.identity = identity
        self.enable_accounting = True
        self.daily_topup_volume = None
        self.max_volume = None
        self.block_traffic = False
        self.ingress_speed = None
        self.egress_speed = None
    
    def __repr__(self):
        return "<RegistrationKey %r>" % self.key

class MacAddress(Base):
    __tablename__ = "mac_address"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    address = db.Column(db.String(25), unique=True, nullable=False)
    user_agent = db.Column(db.String(500), unique=False, nullable=True)
    vendor = db.Column(db.String(500), unique=False, nullable=True)
    first_known_since = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, address, user_agent, vendor, first_known_since):
        self.address = address
        self.user_agent = user_agent
        self.vendor = vendor
        self.first_known_since = first_known_since
    
    def __repr__(self):
        return "<MacAddress %r>" % self.address

class IpAddress(Base):
    __tablename__ = "ip_address"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    address_v4 = db.Column(db.String(15), unique=True, nullable=False)
    address_v6 = db.Column(db.String(100), unique=True, nullable=True)
    
    def __init__(self, address_v4, address_v6):
        self.address_v4 = address_v4
        self.address_v6 = address_v6
    
    def __repr__(self):
        return "<IpAddress %r>" % self.address_v4

class Identity(Base):
    __tablename__ = "identity"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(500), unique=False, nullable=False)
    last_name = db.Column(db.String(500), unique=False, nullable=False)
    mail = db.Column(db.String(500), unique=False, nullable=False)
    room = db.Column(db.String(20), unique=False, nullable=False)
    new_room = db.Column(db.String(20), unique=False, nullable=True)
    move_date = db.Column(db.DateTime, nullable=True)
    
    def __init__(self, first_name, last_name, mail, room):
        self.first_name = first_name
        self.last_name = last_name
        self.mail = mail
        self.room = room
    
    def __repr__(self):
        return "<Identity %r>" % self.first_name

class Traffic(Base):
    __tablename__ = "traffic"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    reg_key = db.Column(db.BigInteger, db.ForeignKey("registration_key.id"))
    timestamp = db.Column(db.DateTime, nullable=False)
    credit = db.Column(db.BigInteger, nullable=False)
    ingress = db.Column(db.BigInteger, nullable=False)
    egress = db.Column(db.BigInteger, nullable=False)
    ingress_shaped = db.Column(db.BigInteger, nullable=False)
    egress_shaped = db.Column(db.BigInteger, nullable=False)
    ingress_unlimited_range = db.Column(db.BigInteger, nullable=False)
    egress_unlimited_range = db.Column(db.BigInteger, nullable=False)
    ingress_excepted = db.Column(db.BigInteger, nullable=False)
    egress_excepted = db.Column(db.BigInteger, nullable=False)
    
    def __init__(self, reg_key, timestamp, credit, ingress, egress, ingress_shaped, egress_shaped, ingress_unlimited_range, egress_unlimited_range, ingress_excepted, egress_excepted):
        self.reg_key = reg_key
        self.timestamp = timestamp
        self.credit = credit
        self.ingress = ingress
        self.egress = egress
        self.ingress_shaped = ingress_shaped
        self.egress_shaped = egress_shaped
        self.ingress_unlimited_range = ingress_unlimited_range
        self.egress_unlimited_range = egress_unlimited_range
        self.ingress_excepted = ingress_excepted
        self.egress_excepted = egress_excepted
    
    def __repr__(self):
        return "<Traffic %r>" % self.reg_key

class Voucher(Base):
    __tablename__ = "voucher"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=True)
    all_users = db.Column(db.Boolean(False), nullable=False)
    
    def __init__(self, code, valid_until, multiple_users):
        self.code = code
        self.valid_until = valid_until
        self.multiple_users = multiple_users
    
    def __repr__(self):
        return "<Voucher %r>" % self.code

class VoucherUser(Base):
    __tablename__ = "voucher_user"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    code = db.Column(db.BigInteger, db.ForeignKey("voucher.id"))
    reg_key = db.Column(db.BigInteger, db.ForeignKey("registration_key.id"))
    date = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, code, reg_key, date):
        self.code = code
        self.reg_key = reg_key
        self.date = date
    
    def __repr__(self):
        return "<VoucherUser %r>" % self.code

class AddressPair(Base):
    __tablename__ = "address_pair"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    reg_key = db.Column(db.BigInteger, db.ForeignKey("registration_key.id"))
    mac_address = db.Column(db.BigInteger, db.ForeignKey("mac_address.id"))
    ip_address = db.Column(db.BigInteger, db.ForeignKey("ip_address.id"))
    
    def __init__(self, reg_key, mac_address, ip_address):
        self.reg_key = reg_key
        self.mac_address = mac_address
        self.ip_address = ip_address
    
    def __repr__(self):
        return "<AddressPairs %r>" % self.reg_key

def create_all(engine):
    Base.metadata.create_all(engine)

