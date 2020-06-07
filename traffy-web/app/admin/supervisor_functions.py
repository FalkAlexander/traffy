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
        db.session.rollback()
        return False

def set_account_password(account_query, password):
    if not __password_check(password):
        return False

    try:
        account_query.set_password(password)
        db.session.commit()
        return True
    except:
        db.session.rollback()
        return False

def set_account_mail(account_query, mail):
    if not __mail_check(mail):
        return False

    try:
        account_query.mail = mail
        db.session.commit()
        return True
    except:
        db.session.rollback()
        return False

def delete_account(account_query):
    try:
        db.session.delete(account_query)
        db.session.commit()
        return True
    except:
        db.session.rollback()
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
        db.session.rollback()
        return False

#
# Private
#

def __password_check(password):
    if len(password) < 10:
        return False

    upper = 0
    lower = 0
    digit = 0
    special = 0
    for i in range(len(password)): 
        if password[i].isupper(): 
            upper += 1
        elif password[i].islower(): 
            lower += 1
        elif password[i].isdigit(): 
            digit += 1
        else: 
            special += 1

    if upper < 1 or lower < 1 or digit < 0 or special < 0:
        return False
    else:
        return True

def __mail_check(mail):
    if not re.match(r"^[a-zA-Z0-9_.+-]+@(?:(?:[a-zA-Z0-9-]+\.)?[a-zA-Z]+\.)?(hszg|studentenwerk-dresden)\.de$", mail):
        return False

    return True

