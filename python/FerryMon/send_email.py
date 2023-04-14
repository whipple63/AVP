#!/usr/bin/python
import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email import Encoders
import os

class send_email():
    '''
    Sends an e-mail using an smtp server,
    can optionally send an attachment
    '''

    def __init__(self):
        self.gmail_user = "AutonomousVerticalProfiler@gmail.com"
        #self.gmail_pwd = "6600sonde"
        self.gmail_pwd = "cztjdjrwpzhmmzno"

    def mail(self, to, subject, text, attach=None):
        msg = MIMEMultipart()
        msg['From'] = self.gmail_user
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(text))
        if attach:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(open(attach, 'rb').read())
            Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"' % os.path.basename(attach))
            msg.attach(part)
        mailServer = smtplib.SMTP("smtp.gmail.com", 587)
        mailServer.ehlo()
        mailServer.starttls()
        mailServer.ehlo()
        mailServer.login(self.gmail_user, self.gmail_pwd)
        mailServer.sendmail(self.gmail_user, to, msg.as_string())
        # Should be mailServer.quit(), but that crashes...
        mailServer.close()


if __name__ == "__main__":
    m = send_email()
    # example with an attachement
#    m.mail("whipple@email.unc.edu",
#           "Hello from python!",
#           "This is an email sent with python with an attachment",
#           "C:\\Documents and Settings\\Tony Whipple\\My Documents\\acw\\HeadShot_Boat.jpg")

    m.mail("whipple@email.unc.edu",
           "Hello from python!",
           "This is an email sent with python")
 
