import config
import smtplib


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

    def send_shaped_notification(self, reg_key_query):
        mail_subject = ""
        mail_text = "Traffic shaping activated for user: "

        message = """\
        From: %s
        To: %s
        Subject: %s

        %s
        """ % (sender_address, ", ".join(self.shaped_recipients), mail_subject, mail_text)

        self.send_mail(self.shaped_recipients, message)

    def send_mail(self, recipients, message):
        mail_server.sendmail(self.sender_address, recipients, message)

