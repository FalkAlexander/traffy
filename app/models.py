from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from . import db
from sqlalchemy.sql import text


class RegistrationKey(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    created_on = db.Column(db.DateTime, nullable=False)
    active = db.Column(db.Boolean(True), nullable=False)
    eula_accepted = db.Column(db.Boolean(False), nullable=False)
    identity = db.Column(db.Integer, db.ForeignKey("identity.id"))
    enable_accounting = db.Column(db.Boolean(True), nullable=False)
    daily_topup_volume = db.Column(db.BigInteger, nullable=True)
    max_volume = db.Column(db.BigInteger, nullable=True)
    block_traffic = db.Column(db.Boolean(False), nullable=False)
    ingress_speed = db.Column(db.Integer, nullable=True)
    egress_speed = db.Column(db.Integer, nullable=True)
    
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

class MacAddress(db.Model):             
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    address = db.Column(db.String(25), unique=True, nullable=False)
    user_agent = db.Column(db.String(500), unique=False, nullable=True)
    first_known_since = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, address, user_agent, first_known_since):
        self.address = address
        self.user_agent = user_agent
        self.first_known_since = first_known_since
    
    def __repr__(self):
        return "<MacAddress %r>" % self.address

class IpAddress(db.Model):             
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    address_v4 = db.Column(db.String(15), unique=True, nullable=False)
    address_v6 = db.Column(db.String(100), unique=True, nullable=True)
    
    def __init__(self, address_v4, address_v6):
        self.address_v4 = address_v4
        self.address_v6 = address_v6
    
    def __repr__(self):
        return "<IpAddress %r>" % self.address

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

    def __repr__(self):
        return "<SupervisorAccount %r>" % self.username

class Identity(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(50), unique=False, nullable=True)
    last_name = db.Column(db.String(50), unique=False, nullable=True)
    mail = db.Column(db.String(50), unique=False, nullable=True)
    
    def __init__(self, first_name, last_name, mail):
        self.first_name = first_name
        self.last_name = last_name
        self.mail = mail
    
    def __repr__(self):
        return "<Identity %r>" % self.first_name

class Traffic(db.Model):             
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reg_key = db.Column(db.Integer, db.ForeignKey("registration_key.id"))
    timestamp = db.Column(db.DateTime, nullable=False)
    credit = db.Column(db.BigInteger, nullable=False)
    ingress = db.Column(db.BigInteger, nullable=False)
    egress = db.Column(db.BigInteger, nullable=False)
    ingress_shaped = db.Column(db.BigInteger, nullable=False)
    egress_shaped = db.Column(db.BigInteger, nullable=False)
    
    def __init__(self, reg_key, timestamp, credit, ingress, egress, ingress_shaped, egress_shaped):
        self.reg_key = reg_key
        self.timestamp = timestamp
        self.credit = credit
        self.ingress = ingress
        self.egress = egress
        self.ingress_shaped = ingress_shaped
        self.egress_shaped = egress_shaped
    
    def __repr__(self):
        return "<Traffic %r>" % self.reg_key

class Voucher(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    valid_until = db.Column(db.DateTime, nullable=True)
    all_users = db.Column(db.Boolean(False), nullable=False)
    
    def __init__(self, code, valid_until, multiple_users):
        self.code = code
        self.valid_until = valid_until
        self.multiple_users = multiple_users
    
    def __repr__(self):
        return "<Voucher %r>" % self.code

class VoucherUser(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.Integer, db.ForeignKey("voucher.id"))
    reg_key = db.Column(db.Integer, db.ForeignKey("registration_key.id"))
    date = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, code, reg_key, date):
        self.code = code
        self.reg_key = reg_key
        self.date = date
    
    def __repr__(self):
        return "<VoucherUser %r>" % self.code

class AddressPair(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    reg_key = db.Column(db.Integer, db.ForeignKey("registration_key.id"))
    mac_address = db.Column(db.Integer, db.ForeignKey("mac_address.id"))
    ip_address = db.Column(db.Integer, db.ForeignKey("ip_address.id"))
    
    def __init__(self, reg_key, mac_address, ip_address):
        self.reg_key = reg_key
        self.mac_address = mac_address
        self.ip_address = ip_address
    
    def __repr__(self):
        return "<AddressPairs %r>" % self.reg_key

