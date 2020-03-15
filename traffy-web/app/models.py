from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db


class Role(db.Model):             
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role = db.Column(db.String(30), unique=True, nullable=False)
    
    def __init__(self, role):
        self.role = role
    
    def __repr__(self):
        return "<Role %r>" % self.role

class SupervisorAccount(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), unique=False, nullable=False)
    first_name = db.Column(db.String(100), unique=False, nullable=False)
    last_name = db.Column(db.String(100), unique=False, nullable=False)
    mail = db.Column(db.String(100), unique=False, nullable=False)
    role = db.Column(db.Integer, db.ForeignKey("role.id"))
    notify_shaping = db.Column(db.Boolean, unique=False, nullable=False)
    notify_login_attempts = db.Column(db.Boolean, unique=False, nullable=False)
    notify_critical_events = db.Column(db.Boolean, unique=False, nullable=False)

    def __init__(self, username, password, first_name, last_name, mail, role, notify_shaping, notify_login_attempts, notify_critical_events):
        self.username = username
        self.password = generate_password_hash(password, method="sha256")
        self.first_name = first_name
        self.last_name = last_name
        self.mail = mail
        self.role = role
        self.notify_shaping = notify_shaping
        self.notify_login_attempts = notify_login_attempts
        self.notify_critical_events = notify_critical_events

    def set_password(self, password):
        self.password = generate_password_hash(password, method="sha256")

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def is_admin(self):
        role_query = Role.query.filter_by(id=self.role).first()
        if role_query.role == "Admin":
            return True
        else:
            return False

    def is_helpdesk(self):
        role_query = Role.query.filter_by(id=self.role).first()
        if role_query.role == "Helpdesk":
            return True
        else:
            return False

    def is_clerk(self):
        role_query = Role.query.filter_by(id=self.role).first()
        if role_query.role == "Clerk":
            return True
        else:
            return False

    def get_first_name(self):
        return self.first_name

    def get_last_name(self):
        return self.last_name

    def get_role(self):
        if self.is_admin():
            return "Admin"
        elif is_helpdesk():
            return "Helpdesk"
        elif is_clerk():
            return "Sachbearbeiter*in"

    def __repr__(self):
        return "<SupervisorAccount %r>" % self.username

