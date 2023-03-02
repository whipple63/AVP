#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        gps.py
# Purpose:     Contains class for gpsd broker client
#              Examples:
#
# Author:      neve
#
# Created:     03/15/2013
#-------------------------------------------------------------------------------

#Built in Modules
from datetime import datetime,timedelta
import logging

import time
#Installed Modules
import pytz.reference
#Custom Modules
from brokers.brokerclient import BrokerClient

class GpsBroker(BrokerClient):
    '''
    Adds methods and attributes specific to the GPS
    Public Methods: None
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'gps'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(GpsBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # Sounder doesn't have anything to load.
        super(GpsBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
