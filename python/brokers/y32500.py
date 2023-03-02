#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        y32500.py
# Purpose:     Contains class for RM Young Y32500 wind speed/direction instrument.
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

class WindBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the RM Young 32500 wind instrument
    Public Methods: start_collection, stop_collection
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'wind'
    MPS_TO_KNOTS = 1.94384
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(WindBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # These are default values which are overwritten by [[constants]] in config when load_config
        # is called below
        self.COMPASS_TARGET = 0 
        self.COMPASS_MARGIN = 90
        super(Y32500Broker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def start_collection(self,timeout=None,**kwargs):
        # Just testing
        if not self._is_initialized(method_name='start_collection'): return {}
        self._json_id += 1
        start_collection_result =  self.socket_handler.send_rpc('startCollection',
                                                                self._json_id,
                                                                timeout=timeout,
                                                                params=None,
                                                                **kwargs)
        return self._result_checker(start_collection_result)
    def stop_collection(self,timeout=None,**kwargs):
        # Just testing...
        if not self._is_initialized(method_name='stop_collection'): return {}
        self._json_id += 1
        stop_collection_result =  self.socket_handler.send_rpc('stopCollection',
                                                               self._json_id,
                                                               timeout=timeout,
                                                               params=None,
                                                               **kwargs)
        return self._result_checker(stop_collection_result)
