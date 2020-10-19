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

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.schema import CreateSchema
from sqlalchemy import MetaData
import os
import sqlalchemy as db
import config
import threading


class DatabaseManager():
    engine = NotImplemented
    session_factory = NotImplemented
    session_scoped = NotImplemented
    connection = NotImplemented

    def __init__(self):
        self.init_database()

    def init_database(self):
        self.engine = db.create_engine(config.DATABASE_URI, pool_size=200, max_overflow=50)
        self.session_factory = sessionmaker(bind=self.engine)
        self.connection = self.engine.connect()
        self.session_scoped = scoped_session(self.session_factory)
        self.metadata = MetaData()
        self.__create_initial_tables()

    def create_session(self):
        return self.session_scoped()

    #
    # Private
    #

    def __create_initial_tables(self):
        from app import models
        models.create_all(self.engine)

