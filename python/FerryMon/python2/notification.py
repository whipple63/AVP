#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        notification
# Purpose:     Monitors the log database for errors and notifies the operator
#
# Author:      whipple
#
# Created:     01/02/2012
#-------------------------------------------------------------------------------

#Built in modules
import datetime
import logging
import socket
import threading
import time
#Installed Modules
import pytz.reference
#Custom Modules
import avp_db
from send_email import send_email

class Notification(threading.Thread):
    '''
    Runs a thread that watches the log database for warning or critical messages
    and emails the ones found to alert the operator
    '''
    SLEEP_TIME = 1.0 # Time to sleep in seconds between schedule checks

    def __init__(self, config):
        '''
        Requires a config dictionary as returned by configObj

        Uses config file keys:
        DB_CHECK_INTERVAL: How often in seconds to check the database
        LOG_TABLE: The name of the log table to check
        '''
        self.running = False    # set up threading
        super(Notification,self).__init__()
        self.name = self.__class__.__name__
        self.lastCheckTime = None
        db_check_int = int(config['db'].get('DB_CHECK_INTERVAL',30 * 60))   # seconds then convert to timedelta below
        self.DB_CHECK_INTERVAL = datetime.timedelta(seconds=db_check_int + 1)
        self.NOTIFY_EMAIL = config['supervisor'].get('NOTIFY_EMAIL',None)  # Who to email
        self.notify_subject = "AVP Warnings and Critical Notifications"
        self.logger = logging.getLogger(self.__class__.__name__)
        LOG_TABLE = config['db'].get('LOG_TABLE','{0}_log'.format(socket.gethostname()))
        self.db = avp_db.AvpDB(config,LOG_TABLE,polling=False)
        self.logger.info('Monitoring log database for notifications')

    def start(self):
        '''
        Start Monitoring the database
        '''
        self.running = True
        super(Notification,self).start() #threading.Thread.start(self)

    def shutdown(self):
        '''
        Stop monitoring the database
        '''
        print("notifications have been shut down")
        self.db.close()
        self.running = False
        time.sleep(1)
        self.logger.debug("Shutting down {0:24} {1:2} threads left.".format(self.name,threading.active_count()))

    def notify_now(self):
        '''
        Force a database check immediately
        '''
        t = self.lastCheckTime - self.DB_CHECK_INTERVAL
        self.lastCheckTime = t
        while (self.lastCheckTime == t):
            time.sleep(1)

    def run(self):
        # only monitor forward in time
        self.lastCheckTime = datetime.datetime.now(pytz.reference.LocalTimezone())
        columns = '*'   # we want to see all columns
        while self.running:
            time.sleep(self.SLEEP_TIME)
            time_now = datetime.datetime.now(pytz.reference.LocalTimezone())
#            import pdb; pdb.set_trace()     # start the debugger
#            print "time_now:           ",time_now
#            print "last check:         ",self.lastCheckTime
#            print "ck time + interval: ",self.lastCheckTime+self.DB_CHECK_INTERVAL
#            print " "
            if time_now > self.lastCheckTime + self.DB_CHECK_INTERVAL:
#                print "Checking database."
                # specify that the time is past the last check time
                where_condition = {'time':self.lastCheckTime,'level':1}
                db_notifications = self.db.select(columns,
                                                  where_condition=where_condition,
                                                  where_oper = '>',
                                                  fetch_type='all',
                                                  debug_mode=False)
#                print "notifications: ",notifications
                if db_notifications:
                    # format notifications more nicely
                    notifications = ' '
                    for log_entry in db_notifications:
                        for field in log_entry:
                            notifications += str(field) + '   '
                        notifications += '\n '
                    self.notify(notifications)
                self.lastCheckTime = datetime.datetime.now(pytz.reference.LocalTimezone())
        self.shutdown()

    def notify(self, notifications):    
        '''
        Used in run thread to send email notifications
        '''
        self.logger.info('Sending notifications to operator')
        m = send_email()    # instantiate an email sender
        for mail_recipient in self.NOTIFY_EMAIL:
            try:
                m.mail(mail_recipient,
                       self.notify_subject,
                       notifications)
            except Exception as e:
                self.logger.error('Error sending notifications: '+str(e))
 
if __name__ == "__main__":
    import avp_util
    import signal
    cloptions,config = avp_util.get_config() # parse command Line options
    n = Notification(config)
    n.start()
    # catch some signals and perform an orderly shutdown
    signal.signal(signal.SIGTERM, n.shutdown)
    signal.signal(signal.SIGHUP,  n.shutdown)
    signal.signal(signal.SIGINT,  n.shutdown)
    signal.signal(signal.SIGQUIT, n.shutdown)
    signal.signal(signal.SIGILL,  n.shutdown)
    signal.signal(signal.SIGABRT, n.shutdown)
    signal.signal(signal.SIGFPE,  n.shutdown)
    signal.signal(signal.SIGSEGV, n.shutdown)
    time.sleep(5)
    while n.running is True:
        time.sleep(5)
