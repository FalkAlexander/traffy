from .. import db
from ..models import Notification
from datetime import datetime
from sqlalchemy import and_


def get_display_notifications():
    today = datetime.today().date()
    notifications = Notification.query.filter(and_(Notification.display_from <= today, Notification.display_until >= today)).all()

    if notifications is None:
        notifications = []
    
    notifications.reverse()

    return notifications
