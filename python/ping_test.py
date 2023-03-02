#!/usr/bin/python

#Built in Modules
import logging, logging.handlers
import socket
import subprocess
import time
import sys
#Installed Modules
from configobj import ConfigObj

#Custom Modules
import avp_db
sys.path.append('/usr/local/bin')

class Pinger(object):
    def __init__(self,config): # PING_TARGET='www.google.com',PING_TIMEOUT=500,MAX_TRIES=5,SLEEP_TIME=90):
        # set up logging with a root level logger
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info('Initializing ping_test.py')
        self.PING_TARGET = config.get('ping_test',{}).get('PING_TARGET','google.com')
        self.MAX_TRIES = int(config.get('ping_test',{}).get('MAX_TRIES',5))
        self.SLEEP_TIME = int(config.get('ping_test',{}).get('SLEEP_TIME',90))
        self.PING_TIMEOUT = int(config.get('ping_test',{}).get('PING_TIMEOUT',500))
        self.RESET_COMMAND = config.get('ping_test',{}).get('RESET_COMMAND','/home/avp/bin/cyclemodem.sh')
        self.failed_pings = 0

    def ping_failed(self,msg='unknown'):
        self.failed_pings += 1
        self.logger.warning("Ping {0} to {1} failed for {2} msec: {3}".format(self.failed_pings,self.PING_TARGET,self.PING_TIMEOUT,msg))
        
    def ping_succeeded(self):
        self.logger.debug('Ping to {0} succeeded.'.format(self.PING_TARGET))
        self.failed_pings = 0
        
    def reset_modem(self):
        self.logger.critical('Ping of {1} failed {1} times.  Resetting modem.'.format(self.MAX_TRIES,self.PING_TARGET))
        result = subprocess.call(self.RESET_COMMAND, shell=True)
        self.failed_pings = 0
        return result

    def start(self):
        self.logger.info('Starting ping_test.py')
        while True:     #forever
            time.sleep(self.SLEEP_TIME)
            try:
                result = self.do_ping(self.PING_TARGET)
                if result is 0:
                    print("{0} is alive".format(self.PING_TARGET))
                    self.ping_succeeded()
                else:
                    print("{0} is unreachable".format(self.PING_TARGET))
                    self.ping_failed(result)
            except socket.error as e:
                self.ping_failed(e)
            except Exception as e:
                self.ping_failed(e)
            if self.failed_pings >= self.MAX_TRIES:   # Try resetting modem
                self.reset_modem()
                time.sleep(self.SLEEP_TIME) # Extra sleeping to allow modem to recover
      
    def do_ping(self,ip,count=1,interval=1.0):
        ''' Returns 0 on success '''
        ret = subprocess.call("ping -c {0} -i {1} {2}".format(count,interval,ip),
                shell=True,
                stdout=open('/dev/null', 'w'),
                stderr=subprocess.STDOUT)
        return ret

if __name__ == '__main__':
    
    logger = logging.getLogger('ping_test.py')
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    try:
        config = ConfigObj(sys.argv[1])  # Read the config file
    except Exception as e:
        print("Bad usage: {0} {1}".format(sys.argv,e))
    dbh = avp_db.DB_LogHandler(config)
    dbh.setLevel(logging.INFO)
    logger.setLevel(logging.INFO)  # uncomment to suppress debug messages
    logger.addHandler(dbh)

    p = Pinger(config)
    p.start()
    
