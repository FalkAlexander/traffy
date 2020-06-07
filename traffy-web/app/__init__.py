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

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_login import LoginManager
from app.socket_manager import SocketManager
from datetime import datetime
import os
import config


db = SQLAlchemy()
babel = Babel()
login_manager = LoginManager()
server = SocketManager().server
client_version = "0.1"

def create_app():
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.url_map.strict_slashes = False
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URI

    db.init_app(app)
    babel.init_app(app)
    login_manager.init_app(app)

    @app.context_processor
    def inject():
        return dict(admins=config.ADMINS, facility_management=config.FACILITY_MANAGEMENT)
    
    @app.template_filter("strftime")
    def __jinja2_filter_datetime(date, fmt=None):
        format="%d.%m.%Y %H:%M:%S"
        date = datetime.fromtimestamp(date)
        return date.strftime(format) 

    # User Interface
    from .user import user as user_blueprint
    app.register_blueprint(user_blueprint)

    # Admin Interface
    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint)

    return app
