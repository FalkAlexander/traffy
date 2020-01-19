from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema
from sqlalchemy import MetaData
import os
import sqlalchemy as db
import config


class DatabaseManager():
    engine = NotImplemented
    session = NotImplemented
    connection = NotImplemented

    def __init__(self):
        self.init_database()

    def init_database(self):
        self.engine = db.create_engine(config.DATABASE_URI)
        self.session = sessionmaker(bind=self.engine)
        self.connection = self.engine.connect()
        self.session = self.session()
        self.metadata = MetaData()
        self.__create_initial_tables()

    #
    # Private
    #

    def __create_initial_tables(self):
        from app import models
        models.create_all(self.engine)

