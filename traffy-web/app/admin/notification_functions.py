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
from ..models import Notification
from datetime import datetime

def create_notification(title, body, valid_from, valid_until):
    success = False

    valid_from = datetime.strptime(valid_from, "%Y-%m-%d")
    valid_until = datetime.strptime(valid_until, "%Y-%m-%d")

    try:
        notification = Notification(title=title, body=body, display_from=valid_from, display_until=valid_until)
        db.session.add(notification)
        db.session.commit()

        success = True
    except:
        db.session.rollback()
        success = False
    finally:
        db.session.close()

    return success

def get_notification_data(notification_id):
    notification = Notification.query.filter_by(id=notification_id).first()

    if notification is None:
        return None
    else:
        return notification.title, notification.body, notification.display_from.strftime("%Y-%m-%d"), notification.display_until.strftime("%Y-%m-%d")

def edit_notification(notification_id, title, body, valid_from, valid_until):
    success = False

    valid_from = datetime.strptime(valid_from, "%Y-%m-%d")
    valid_until = datetime.strptime(valid_until, "%Y-%m-%d")

    try:
        notification = Notification.query.filter_by(id=notification_id).first()
        if notification is not None:
            notification.title = title
            notification.body = body
            notification.display_from = valid_from
            notification.display_until = valid_until

            db.session.commit()
            success = True
        else:
            success = False
    except:
        db.session.rollback()
        success = False
    finally:
        db.session.close()

    return success

def delete_notification(notification_id):
    success = False

    try:
        notification = Notification.query.filter_by(id=notification_id).first()
        if notification is not None:
            db.session.delete(notification)
            db.session.commit()
            success = True
        else:
            success = False
    except:
        db.session.rollback()
        success = False
    finally:
        db.session.close()

    return success
