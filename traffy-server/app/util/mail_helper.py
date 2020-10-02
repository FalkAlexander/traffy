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

import config
import smtplib
from email.mime.text import MIMEText


class MailHelper():
    mail_server = NotImplemented
    sender_address = "noreply-traffy@hszg.de"

    shaped_recipients = []
    login_recipients = []
    failure_recipients = []

    def __init__(self):
        self.mail_server = smtplib.SMTP(host=config.SMTP_SERVER, port=config.SMTP_PORT)

    def quit_client(self):
        self.mail_server.quit()

    def update_recipients(self, shaped_recipients, login_recipients, failure_recipients):
        pass

    def send_shaped_notification(self, first_name, last_name, room):
        mail_subject = "Tenant " + last_name + ", " + first_name + " has exceeded the data limit"
        mail_text = "The user : "

        msg = MIMEText('This is test mail')

        msg['Subject'] = 'Test mail'
        msg['From'] = 'admin@example.com'
        msg['To'] = 'info@example.com'

        self.__send_mail(self.shaped_recipients, message)

    def __send_mail(self, recipients, message):
        self.mail_server.sendmail(self.sender_address, recipients, message)

