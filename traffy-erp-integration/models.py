"""
 Copyright (C) 2021 Falk Seidl <hi@falsei.de>

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

from sqlalchemy.ext.declarative import declarative_base
import sqlalchemy as db

Base = declarative_base()


class ERPMaster(Base):
    __tablename__ = "master"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    debitor_id = db.Column(db.Integer)
    first_name = db.Column(db.String(1000))
    last_name = db.Column(db.String(1000))
    mail = db.Column(db.String(1000))
    dormitory_id = db.Column(db.Integer)
    dormitory_name = db.Column(db.String(1000))
    room = db.Column(db.String(1000))
    ib_needed = db.Column(db.String(1))
    ib_expiry_date = db.Column(db.Date)
    contract_expiry_date = db.Column(db.Date)

    def __init__(self, debitor_id, first_name, last_name, mail, dormitory_id, dormitory_name, room, ib_needed, ib_expiry_date, contract_expiry_date):
        self.debitor_id = debitor_id
        self.first_name = first_name
        self.last_name = last_name
        self.mail = mail
        self.dormitory_id = dormitory_id
        self.dormitory_name = dormitory_name
        self.room = room
        self.ib_needed = ib_needed
        self.ib_expiry_date = ib_expiry_date
        self.contract_expiry_date = contract_expiry_date

    def __repr__(self):
        return "<ERPMaster %r>" % self.debitor_id


class ERPHistory(Base):
    __tablename__ = "history"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    insert_date = db.Column(db.DateTime)

    def __init__(self, insert_date):
        self.insert_date = insert_date

    def __repr__(self):
        return "<ERPHistory %r>" % self.id


class TraffyIdentity(Base):
    __tablename__ = "identity"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    customer_id = db.Column(db.BigInteger, unique=False, nullable=False)
    first_name = db.Column(db.String(500), unique=False, nullable=False)
    last_name = db.Column(db.String(500), unique=False, nullable=False)
    mail = db.Column(db.String(500), unique=False, nullable=False)
    dormitory_id = db.Column(db.Integer, unique=False, nullable=False)
    new_dormitory_id = db.Column(db.Integer, unique=False, nullable=True)
    room = db.Column(db.String(20), unique=False, nullable=False)
    new_room = db.Column(db.String(20), unique=False, nullable=True)
    move_date = db.Column(db.DateTime, nullable=True)
    ib_needed = db.Column(db.String(1), unique=False, nullable=True)
    ib_expiry_date = db.Column(db.Date, unique=False, nullable=True)

    def __init__(self, customer_id, first_name, last_name, mail, dormitory_id, room, ib_needed, ib_expiry_date):
        self.customer_id = customer_id
        self.first_name = first_name
        self.last_name = last_name
        self.mail = mail
        self.dormitory_id = dormitory_id
        self.room = room
        self.ib_needed = ib_needed
        self.ib_expiry_date = ib_expiry_date

    def __repr__(self):
        return "<Identity %r>" % self.customer_id


class TraffyDormitory(Base):
    __tablename__ = "dormitory"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    internal_id = db.Column(db.BigInteger, unique=True, nullable=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def __init__(self, internal_id, name):
        self.internal_id = internal_id
        self.name = name

    def __repr__(self):
        return "<Dormitory %r>" % self.internal_id


class IdentityUpdate(Base):
    __tablename__ = "identity_update"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    identity_id = db.Column(db.BigInteger, unique=False, nullable=True)
    new_customer_id = db.Column(db.BigInteger, unique=False, nullable=True)
    old_customer_id = db.Column(db.BigInteger, unique=False, nullable=True)
    first_name = db.Column(db.String(500), unique=False, nullable=True)
    last_name = db.Column(db.String(500), unique=False, nullable=True)
    mail = db.Column(db.String(500), unique=False, nullable=True)
    dormitory_id = db.Column(db.Integer, unique=False, nullable=True)
    room = db.Column(db.String(20), unique=False, nullable=True)
    ib_needed = db.Column(db.Boolean, nullable=True)
    ib_expiry_date = db.Column(db.Date, nullable=True)
    contract_expiry_date = db.Column(db.Date, nullable=True)

    def __init__(self, identity_id, new_customer_id, old_customer_id, first_name, last_name, mail, dormitory_id,
                 room, ib_needed, ib_expiry_date, contract_expiry_date):
        self.identity_id = identity_id
        self.new_customer_id = new_customer_id
        self.old_customer_id = old_customer_id
        self.first_name = first_name
        self.last_name = last_name
        self.mail = mail
        self.dormitory_id = dormitory_id
        self.room = room
        self.ib_needed = ib_needed
        self.ib_expiry_date = ib_expiry_date
        self.contract_expiry_date = contract_expiry_date

    def __repr__(self):
        return "<IdentityUpdate %r>" % self.id
