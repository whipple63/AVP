#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        isco6712.py
# Purpose:     Contains class for ISCO 6712 water sampler
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

class IscoBroker(BrokerClient):
    '''
    Adds methods and attributes specific to the ISCO
    Public Methods: take_sample, sampler_on, get_sample_status, get_isco_status
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'isco'
    _ISCO_STATUS = {1:'WAITING TO SAMPLE',
                    4:'POWER FAILED',
                    5:'PUMP JAMMED',
                    6:'DISTRIBUTOR JAMMED',
                    9:'SAMPLER OFF',
                    12:'SAMPLE IN PROGRESS',
                    20:'INVALID COMMAND',
                    21:'CHECKSUM MISMATCH',
                    22:'INVALID BOTTLE',
                    23:'VOLUME OUT OF RANGE'}
    _SAMPLE_STATUS = {0:'SAMPLE OK',
                    1 :'NO LIQUID FOUND',
                    2 :'LIQUID LOST',
                    3 :'USER STOPPED',
                    4 :'POWER FAILED',
                    5 :'PUMP JAMMED',
                    6 :'DISTRIBUTOR JAMMED',
                    8 :'PUMP LATCH OPEN',
                    9 :'SAMPLER SHUT OFF',
                    11:'NO DISTRIBUTOR',
                    12:'SAMPLE IN PROGRESS'}
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.BROKER_NAME)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(IscoBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Supe
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
        self.BOTTLE_SIZE = 1000
        self.NUM_BOTTLES = 24
        self.SAMPLE_TIMEOUT = 24
        super(IscoBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def take_sample(self,bottle, volume, cast_number, sample_depth,timeout=None,**kwargs):
        # take a sample into a specific bottle using a specific volume
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='take_sample'): return {}
        self._json_id += 1
        params = {"bottle_num":bottle, "sample_volume":volume, "cast_number":cast_number, "sample_depth":sample_depth}
        result =  self.socket_handler.send_rpc('take_sample',
                                               self._json_id,
                                               timeout=timeout,
                                               params=params,
                                               debug_mode=debug_mode)
        return self._result_checker(result)
    def sampler_on(self,timeout=None,**kwargs):
        # If the sampler is turned off via the panel, this will turn it on.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='sampler_on'): return {}
        self._json_id += 1
        result =  self.socket_handler.send_rpc('sampler_on',
                                               self._json_id,
                                               timeout=timeout,
                                               params=None,
                                               debug_mode=debug_mode)
        return self._result_checker(result)
    def get_sample_status(self,status_num=None,**kwargs):
        # Translate a number into a meaningfule string.
        if not self._is_initialized(method_name='get_sample_status'): return {}
        if status_num == None:
            status_num = self.sample_status.value
        result = self._SAMPLE_STATUS.get(status_num,"{0} is an unknown sample status.".format(status_num))
        return result
    def get_isco_status(self,status_num=None,**kwargs):
        # Translate a number into a meaningfule string.
        if not self._is_initialized(method_name='get_isco_status'): return {}
        if status_num == None:
            status_num = self.sample_status.value
        result = self._ISCO_STATUS.get(status_num,"{0} is an unknown ISCO status.".format(status_num))
        return result
