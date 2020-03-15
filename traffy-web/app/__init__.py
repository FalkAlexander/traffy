from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_babel import Babel
from flask_login import LoginManager
from app.socket_manager import SocketManager
import os
import config


db = SQLAlchemy()
babel = Babel()
login_manager = LoginManager()
server = SocketManager().server
client_version = "0.1"

def create_app():
    app = Flask(__name__)
    app.secret_key = "BnUlPYIj2ZzeTL1wv4IxzCsRtqcPJLpxvOv"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_DATABASE_URI"] = config.DATABASE_URI

    db.init_app(app)
    babel.init_app(app)
    login_manager.init_app(app)

    @app.context_processor
    def inject():
        return dict(admins=config.ADMINS, facility_management=config.FACILITY_MANAGEMENT)

    # User Interface
    from .user import user as user_blueprint
    app.register_blueprint(user_blueprint)

    # Admin Interface
    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint)

    return app

