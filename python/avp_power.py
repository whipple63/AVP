#!/usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        avp_power
# Purpose:     provides interface for power monitoring.
#
# Author:      neve
#
# Created:     01/02/2012
#-------------------

#Built in Modules
from collections import deque
from datetime import datetime,timedelta
import logging
import os
#Installed Modules
#Custom Modules

class AVP_Power(object):
    def __init__(self,aio,config,last_load_ah=0,last_charge_ah=0):
        self._logger = logging.getLogger()
        self.aio = aio
        self._config = config
        self.charge_current   = CurrentMonitor(amp_hours=last_charge_ah,monitor_type='charge')
        self.load_current     = CurrentMonitor(amp_hours=last_load_ah,monitor_type='load')
        self.voltage          = VoltageMonitor(self._config)
        aio_callbacks = {self.aio.voltage_ADC.data_name:self.voltage_callback,
                         self.aio.load_current_ADC.data_name:self.load_current_callback,
                         self.aio.charge_current_ADC.data_name:self.charge_current_callback}

        self._logger.info("Adding aio callbacks: {0}".format(list(aio_callbacks.keys())))
        self.aio.add_callback(aio_callbacks)
        self._logger.info("Adding aio subscriptions")
        self.aio.add_subscriptions(['voltage_ADC', 'load_current_ADC', 'charge_current_ADC'],
                                   on_change = False,
                                   min_interval=1000,
                                   max_interval=1000)
        # These callback routines are called in their own thread when new values appear in the subscription
    def voltage_callback(self, sample_dt, callback_obj):
        if self.aio.initialized is True:
            try:
                VOLTAGE_MULTIPLIER = self.aio.VOLTAGE_MULTIPLIER
                self.voltage.accumVoltage(sample_dt, callback_obj, VOLTAGE_MULTIPLIER)
            except KeyError as e:
                self._logger.critical('Error in power finding configuration key '+str(e))
    def load_current_callback(self, sample_dt, callback_obj):
        if self.aio.initialized is True:
            try:
                CURRENT_OFFSET = self.aio.LOAD_CURRENT_OFFSET
                CURRENT_MULTIPLIER = self.aio.LOAD_CURRENT_MULTIPLIER
                self.load_current.accumCurrent(sample_dt, callback_obj, CURRENT_OFFSET,CURRENT_MULTIPLIER)
            except KeyError as e:
                self._logger.critical('Error in power finding configuration key '+str(e))
    def charge_current_callback(self, sample_dt, callback_obj):
        if self.aio.initialized is True:
            try:
                CURRENT_OFFSET = self.aio.CHARGE_CURRENT_OFFSET
                CURRENT_MULTIPLIER = self.aio.CHARGE_CURRENT_MULTIPLIER
                self.charge_current.accumCurrent(sample_dt, callback_obj, CURRENT_OFFSET, CURRENT_MULTIPLIER)
            except KeyError as e:
                self._logger.critical('Error in power finding configuration key '+str(e))
                
class CurrentMonitor(object):
    def __init__(self,amp_hours=0,monitor_type=''):
        '''
        amp_hours   - Is non 0 if resuming with a value from the database
        monitor_type        - label used for logging
        '''
        try:
            self.amp_hours = float(amp_hours)  # amp-hours drawn since monitoring has begun
        except TypeError as e:
            self.amp_hours = 0
        self.monitor_type = monitor_type
        self._logger = logging.getLogger()
        self._last_dt = None    # most recent datetime
        self._last_date = datetime.now().day  # Day of most recent value used for daily reset
        self.value = 0  # most recent current value
        self._valHistory  = deque([])  # list from which the averages are taken
        self._timeHistory = deque([])  # list of associated times
        self.one_min_ave = 0 # keep a one minute average
        self._tot_time = timedelta(0)  # total time over which current has been monitored
        self.maximum = -99 # Not zero since we can get negative currents on charge.
    def reset(self):
        self.__init__()
    def accumCurrent(self, sample_dt, callback_obj, offset, mult):
        # convert the time to seconds since 1970 and add the fractional part
        if sample_dt.day != self._last_date: #Reset every day at midnight.
            self._logger.info('Daily {0} amp hour values reset at {1} ah'.format(self.monitor_type,self.amp_hours))
            self.reset()
        if self._last_dt != None:
            timeStep = sample_dt - self._last_dt
            if timeStep > timedelta(seconds=60*10):
                print(("invalid timestamp {0} received".format(sample_dt)))
                return
            ampStep = self.value * (timeStep.seconds / 3600.0)
            self._tot_time += timeStep
            self.amp_hours += ampStep
        self._last_dt = sample_dt
        self.value = (float(callback_obj.value) - offset) * mult    # Offset is 0.1 * 5V supply voltage
        if self.value > self.maximum:
            self.maximum = self.value
        self._valHistory.append(self.value)
        self._timeHistory.append(self._last_dt)
        if self._timeHistory[-1] - self._timeHistory[0] > timedelta(seconds=60):  # keep only 60 seconds
            self._valHistory.popleft()
            self._timeHistory.popleft()
        self.one_min_ave = sum( self._valHistory ) / len(self._valHistory)
        
class VoltageMonitor(object):
    def __init__(self,config):
        self._logger = logging.getLogger()
        self.value = 0  # most recent voltage
        self._voltHistory = deque([])  # list from which the averages are taken
        self._timeHistory = deque([])  # list of associated times
        self.one_min_ave = 0       # keep a one minute average
        self.one_min_min = 999 
    def reset(self):
        self.__init__()
    def accumVoltage(self, sample_dt, callback_obj, mult):
        self.value = float(callback_obj.value) * mult  # convert from divider voltage to real voltage as measured
        self._voltHistory.append( self.value )
        self._timeHistory.append( sample_dt )
        if self._timeHistory[-1] - self._timeHistory[0] > timedelta(seconds=60):  # keep only 60 seconds
            self._voltHistory.popleft()
            self._timeHistory.popleft()
        self.one_min_ave = sum(self._voltHistory) / len(self._voltHistory)
        self.one_min_min = min(self._voltHistory)