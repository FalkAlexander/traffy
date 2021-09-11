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

from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import MetaData
import sqlalchemy as db
import config


class DatabaseConnection:
    database_uri = NotImplemented
    engine = NotImplemented
    session_factory = NotImplemented
    session_scoped = NotImplemented
    connection = NotImplemented

    def __init__(self, database_uri):
        self.database_uri = database_uri
        self.init_database()

    def init_database(self):
        self.engine = db.create_engine(self.database_uri, pool_size=10, max_overflow=10)
        self.session_factory = sessionmaker(bind=self.engine)
        self.connection = self.engine.connect()
        self.session_scoped = scoped_session(self.session_factory)
        self.metadata = MetaData()

    def create_session(self):
        return self.session_scoped()


class DatabaseManagerTraffy(DatabaseConnection):
    def __init__(self):
        super(DatabaseManagerTraffy, self).__init__(config.TRAFFY_MASTER_DATABASE_URI)


class DatabaseManagerERP(DatabaseConnection):
    def __init__(self):
        super(DatabaseManagerERP, self).__init__(config.ERP_MASTER_DATABASE_URI)
