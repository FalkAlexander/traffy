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

from app import create_app, db
from app.models import Role, SupervisorAccount
from datetime import datetime
import logging


def __setup_logging():
    logging.basicConfig(format="[%(asctime)s] [%(process)d] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S %z", level=logging.INFO)

def __create_initial_db_entries():
    admin_role = Role.query.filter_by(role="Admin").first()
    if admin_role is None:
        db.session.add(Role(role="Admin"))

    helpdesk_role = Role.query.filter_by(role="Helpdesk").first()
    if helpdesk_role is None:
        db.session.add(Role(role="Helpdesk"))

    clerk_role = Role.query.filter_by(role="Clerk").first()
    if clerk_role is None:
        db.session.add(Role(role="Clerk"))

    admin_role = Role.query.filter_by(role="Admin").first()
    if SupervisorAccount.query.count() == 0:
        db.session.add(SupervisorAccount(username="admin",
                                         password="admin",
                                         first_name="Max",
                                         last_name="Mustermann",
                                         mail="admin.goerlitz@wh.studentenwerk-dresden.de",
                                         role=admin_role.id,
                                         notify_shaping=True,
                                         notify_login_attempts=True,
                                         notify_critical_events=True))

    db.session.commit()

def shutdown():
    logging.info("Client powered off")

def startup():
    with app.app_context():
        db.create_all()
        __create_initial_db_entries()

    logging.info("Traffy web client ready after " + str((datetime.now() - before_startup).total_seconds()) + "s")

before_startup = datetime.now()
__setup_logging()
app = create_app()

