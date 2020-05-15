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
        mail_server.sendmail(self.sender_address, recipients, message)

