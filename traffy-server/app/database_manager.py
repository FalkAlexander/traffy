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
        self.engine = db.create_engine(config.DATABASE_URI)
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

