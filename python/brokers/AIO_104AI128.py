#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        AIO_104AI128.py
# Purpose:     Contains class for Access I/O Model 104-AI12-8 AI/DIO board
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


class AIOBroker(BrokerClient):
    '''
    Adds methods and attributes specific to the IO board
    Public methods: 
    Instance Variables: broker_name, VOLTAGE_MULTIPLIER
    This broker supports attrubite aliases. In the config['aio']['aliases']
    '''
    BROKER_NAME = 'aio'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(AIOBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
        #This allows us to alias parameters with their functions.
        self.param_aliases = self.config[self.BROKER_NAME].get('aliases',{})
        for key,value in self.param_aliases.items():
            this_data_item = getattr(self,value)
            setattr(self,key,this_data_item)
            self.data_points[key] = getattr(self,key)
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
        self.VOLTAGE_MULTIPLIER = 3.089
        self.LOAD_CURRENT_OFFSET = 0.515
        self.CHARGE_CURRENT_OFFSET = 0.4077
        self.LOAD_CURRENT_MULTIPLIER = 7.519
        self.CHARGE_CURRENT_MULTIPLIER = 9.259
        super(AIOBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
