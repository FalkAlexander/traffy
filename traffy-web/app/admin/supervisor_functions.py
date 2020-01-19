from .. import db
from ..models import SupervisorAccount, Role
import re

def set_account_notifications(account_query, notify_shaping, notify_login_attempts, notify_critical_events):
    if notify_shaping == "on":
        notify_shaping = True
    else:
        notify_shaping = False

    if notify_login_attempts == "on":
        notify_login_attempts = True
    else:
        notify_login_attempts = False

    if notify_critical_events == "on":
        notify_critical_events = True
    else:
        notify_critical_events = False

    try:
        account_query.notify_shaping = notify_shaping
        account_query.notify_login_attempts = notify_login_attempts
        account_query.notify_critical_events = notify_critical_events
        db.session.commit()
        return True
    except:
        return False

def set_account_password(account_query, password):
    if not __password_check(password):
        return False

    try:
        account_query.set_password(password)
        db.session.commit()
        return True
    except:
        return False

def set_account_mail(account_query, mail):
    if not __mail_check(mail):
        return False

    try:
        account_query.mail = mail
        db.session.commit()
        return True
    except:
        return False

def delete_account(account_query):
    try:
        db.session.delete(account_query)
        db.session.commit()
        return True
    except:
        return False

def create_account(username, first_name, last_name, mail, password, role):
    role = Role.query.filter_by(role=role).first()
    if role is None:
        return False

    if not __password_check(password):
        return False

    if not __mail_check(mail):
        return False

    try:
        db.session.add(SupervisorAccount(username=username,
                                         password=password,
                                         first_name=first_name,
                                         last_name=last_name,
                                         mail=mail,
                                         role=role.id,
                                         notify_shaping=True,
                                         notify_login_attempts=True,
                                         notify_critical_events=True))
        db.session.commit()
        return True
    except:
        return False

#
# Private
#

def __password_check(password):
    if len(password) < 20:
        return False

    if sum(1 for char in password if char.isupper()) < 5:
        return False

    if sum(1 for char in password if char.islower()) < 5:
        return False

    if sum(1 for char in password if char.isdigit()) < 5:
        return False

    req = 0
    for char in password:
        if char.isupper():
            req += 1
        elif char.islower():
            req += 1
        elif char.isdigit():
            req += 1
        elif char.isalpha():
            continue
        else:
            req += 1

    if req < 15:
        return False

    return True

def __mail_check(mail):
    if not re.match(r"^[a-zA-Z0-9_.+-]+@(?:(?:[a-zA-Z0-9-]+\.)?[a-zA-Z]+\.)?(hszg|studentenwerk-dresden)\.de$", mail):
        return False

    return True

