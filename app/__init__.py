from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_login import LoginManager
from config import config
from app.util.dnsmasq_manager import DnsmasqService
from app.util.mail_helper import MailHelper
import os


db = SQLAlchemy()
dnsmasq_srv = DnsmasqService()
babel = Babel()
login_manager = LoginManager()
mail_helper = MailHelper()


def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)
    babel.init_app(app)
    login_manager.init_app(app)

    # User Interface
    from .user import user as user_blueprint
    app.register_blueprint(user_blueprint)

    # Admin Interface
    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint)
    
    create_configs()

    return app

def create_configs():
    import config 
    configs = [config.DNSMASQ_CONFIG_FILE, config.DNSMASQ_HOSTS_FILE, config.DNSMASQ_LEASE_FILE]
    
    for cfile in configs:
        if not os.path.exists(os.path.dirname(cfile)):
            try:
                os.makedirs(os.path.dirname(cfile))
            except e:
                raise

        if not os.path.exists(cfile):
            try:
                open(cfile, "a").close()
            except e:
                raise

from app.accounting_manager import AccountingService
accounting_srv = AccountingService(db)

