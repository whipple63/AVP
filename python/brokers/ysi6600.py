#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        ysi6600.py
# Purpose:     Contains class for YSI 6600 sonde 
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


class SondeBroker(BrokerClient):
    '''
    Adds methods and variables specific to the YSI sonde

    Public Methods: wipe, calibrate_pressure, start_sampling, start_logging,
                    stop_logging, stop_sampling,  is_logging,
                    in_water
    Instance Variables: broker_name, WIPE_TIMEOUT, INSTRUMENT_OFFSET,
                        BOTTOM_OFFSET, inwater_cond,
                        INWATER_DEPTH, location ,
                        SONDE_STARTUP_TIME, PRESSURE_ERROR
    '''
    BROKER_NAME = 'sonde'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False) # Not .pop()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(SondeBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
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
        self.SAMPLE_TIMEOUT     = 40
        self.WIPE_TIMEOUT       = 120
        self.INSTRUMENT_OFFSET  = 0.254
        self.BOTTOM_OFFSET      = 0.200
        self.inwater_cond       = 3.0
        self.INWATER_DEPTH      = 0.010
        self.SONDE_STARTUP_TIME = 5.0
        self.PRESSURE_ERROR     = 0.004
        super(SondeBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def wipe(self,**kwargs):
        ''' Wipe is a method specific to the sonde broker.
        '''
        if not self._is_initialized(method_name='wipe'): return {}
        if self.sampling.value != False: 
            self.logger.error("Can not wipe while in sampling mode ({0}).".format(self.sampling.value))
            return 0
        self._json_id += 1
        wipe_result =  self.socket_handler.send_rpc('wipe',
                                                    self._json_id,
                                                    timeout=self.WIPE_TIMEOUT,
                                                    params=None,
                                                    **kwargs)
        return self._result_checker(wipe_result)
    def _cal_press(self,timeout=None,**kwargs):
        ''' calibrate_pressure is a method specific to the sonde broker.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='_cal_press'): return {}
        if debug_mode: print "Calibrating pressure"
        self._json_id += 1
        calibrate_pressure_result =  self.socket_handler.send_rpc('calibratePressure',
                                                                  self._json_id,
                                                                  timeout=timeout,
                                                                  params=None,
                                                                  debug_mode=debug_mode)
        return self._result_checker(calibrate_pressure_result)
    def calibrate_pressure(self,check_instruments=True,**kwargs):
        '''
        Wraps the _cal_press method around some additional error checking functionality.
        Leaves sampling mode the same as when it starts.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='calibrate_pressure'): return {}
        result = {}
        #if not self.depth_m.subscribed:
        #    self.add_subscriptions(['depth_m'],**kwargs)
        #if not self.spcond_mScm.subscribed:
        #    self.add_subscriptions(['spcond_mScm'],**kwargs)
        result['in_water'] = self.in_water(instrument='spcond_mScm',debug_mode=debug_mode)
        if result['in_water'][0]:
            if check_instruments:
                result['error'] = "Error calibrating pressure: Conductivity {0} indicates sonde may be in water.({1})".format(self.spcond_mScm.value,result['in_water'])
                self.logger.warning(result['error'])
                return result
            else:
                self.logger.warning("Calibrating pressure despite conductivity {0} indicating sonde may be in water.({1})".format(self.spcond_mScm.value,result['in_water']))
        # Calibrate
        old_depth = self.depth_m.value
        sampling_status = self.sampling.value # Record original sampling state, so we can return in same state.
        if self.sampling.value != False:
            result['stop_sampling'] = self.stop_sampling(timeout=None,debug_mode=debug_mode)  # Stop sampling mode
        result['_cal_press'] = self._cal_press(timeout=None,debug_mode=debug_mode)        # Calibrate
        if result['_cal_press'].get('error',False):
            self.logger.warning("Error calibrating pressure: {0}".format(result['_cal_press']['error']))
        wake_time = datetime.now(pytz.reference.LocalTimezone()) + timedelta(seconds=self.SONDE_STARTUP_TIME)
        self.logger.info("Waiting {0} sec for calibration procedure and settling.".format(self.SONDE_STARTUP_TIME))
        while datetime.now(pytz.reference.LocalTimezone()) < wake_time:
            print ".",
            time.sleep(1)
        print
        result['SondeBroker.start_sampling'] = self.start_sampling(debug_mode=debug_mode) # Restart sampling
        wake_time = datetime.now(pytz.reference.LocalTimezone()) + timedelta(seconds=5)
        self.logger.info("Waiting {0} sec for new depth value ".format((wake_time - datetime.now(pytz.reference.LocalTimezone())).seconds),)
        while datetime.now(pytz.reference.LocalTimezone()) < wake_time:
            print "{0:6} {1}".format(self.depth_m.value,self.depth_m.units)
            time.sleep(1)
        print
        self.get_value(['depth_m'],verbose=False,timeout=None,debug_mode=debug_mode) #refresh value
        # See if calibration was successful
        if abs(self.depth_m.value) > self.PRESSURE_ERROR:
            result['error'] = {'message':'Pressure {0} indicates bad calibration may have occured.'.format(self.depth_m.value),'code':0}
            self.logger.error("In {0}.calibrate_pressure: {1}".format(self.BROKER_NAME, result['error'].get('message')))
        else:
            self.logger.info("Pressure calibrated from {0} to {1}".format(old_depth,self.depth_m.value))
            result['result'] = 'ok'
        if not sampling_status:
            result['stop_sampling'] = self.stop_sampling(timeout=timeout,debug_mode=debug_mode)  # return to the state in which we started.
        return result
    def start_sampling(self,**kwargs): # was start_collection
        '''
        Put sonde in sampling (run) mode
        Status can be checked with self.sampling.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='start_sampling'): return {}
        if debug_mode: print "Starting sampling"
        self._json_id += 1
        start_sampling_result =  self.socket_handler.send_rpc('start_sampling',
                                                                self._json_id,
                                                                timeout=self.SAMPLE_TIMEOUT,
                                                                params=None,
                                                                debug_mode=debug_mode)
        return self._result_checker(start_sampling_result)
    def stop_sampling(self,timeout=None,**kwargs): # was stop_collection
        '''
        Take sonde out of sampling (run) mode
        Status can be checked with self.sampling.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='stop_sampling'): return {}
        if self.is_logging(timeout=timeout,debug_mode=debug_mode):
            self.stop_logging(timeout=timeout,debug_mode=debug_mode)
        if debug_mode: print "Stopping sampling"
        self._json_id += 1
        stop_sampling_result =  self.socket_handler.send_rpc('stop_sampling',
                                                               self._json_id,
                                                               params=None,
                                                               timeout=timeout,
                                                               debug_mode=debug_mode)
        return self._result_checker(stop_sampling_result)
    def start_logging(self,cast_number,timeout=None,**kwargs):
        '''
        Put sonde in logging to database mode. Requires cast_number
        Status can be checked with self.logging.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='start_logging'): return {}
        if self.sampling.value != True:
            self.start_sampling(debug_mode=debug_mode)
        self._json_id += 1
        start_logging_result =  self.socket_handler.send_rpc('start_logging',
                                                             self._json_id,
                                                             timeout=timeout,
                                                             params = {"cast_number":cast_number},
                                                             debug_mode=debug_mode)
        return self._result_checker(start_logging_result)
    def stop_logging(self,timeout=None,**kwargs):
        '''
        Stop sonde logging to database
        Status can be checked with self.logging.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='stop_logging'): return {}
        self._json_id += 1
        stop_logging_result =  self.socket_handler.send_rpc('stop_logging',
                                                            self._json_id,
                                                            timeout=timeout,
                                                            params=None,
                                                            debug_mode=debug_mode)
        return self._result_checker(stop_logging_result)
    def is_logging(self,timeout=None,**kwargs):
        if not self._is_initialized(method_name='is_logging'): return {}
        debug_mode = kwargs.pop('debug_mode',False)
        if not self.sampling.subscribed:
            self.add_subscriptions(['logging'],
                                   on_change=True,
                                   verbose=False,
                                   timeout=timeout,
                                   min_interval=None,
                                   max_interval=None,
                                   debug_mode=debug_mode)
            try:
                self.get_value(['logging'],verbose=False,debug_mode=debug_mode)
            except Exception,e:
                self.logger.error("Error: Unable to get logging status: {0}".format(e))
                return 0
        return self.logging.value
    def in_water(self,instrument='all',**kwargs):
        '''
        Uses specified instument ('depth_m'|'spcond_mScm'|'any'|'all') to determine if sensor is in water.
        Returns a list with two elements.
        The first list element is a True if it is in the water, False if it isn't, or None if unknown
        The second is the comparison used.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='in_water'): return [None,'sonde object not initialized']
        depth_in_water = spcond_in_water = None
        in_water = None
        message = ''
        valid_instrumets = ['any','all','spcond_mScm','depth_m']
        if instrument not in valid_instrumets:
            message = '{0} is not a valid instruemt for sonde.in_water'.format(instrument)
            self.logger.error(message)
            return [None,message]
        if self.sampling.value is not True:
            if debug_mode: print "Starting sonde sampling:"
            self.start_sampling(debug_mode=debug_mode)
            time.sleep(self.SONDE_STARTUP_TIME)
        if self.spcond_mScm.subscribed is False:
            self.get_value(['spcond_mScm'])
        if self.depth_m.subscribed is False:
            self.get_value(['depth_m'])
        if debug_mode: print "comparing current conductivity {0} to max allowed {1}".format(self.spcond_mScm.value,self.inwater_cond)
        if self.spcond_mScm.value is None:
            message += "spcond_msCm unknown. "
        elif self.spcond_mScm.value >= self.inwater_cond: 
            message += "{0}: {1} >= {2}. ".format('spcond_mScm',self.spcond_mScm.value,self.inwater_cond)
            spcond_in_water = True
        else:
            message +=  '{0}: {1} < {2}. '.format('spcond_mScm',self.spcond_mScm.value,self.inwater_cond)
            spcond_in_water = False
        if debug_mode: print "comparing current depth_m {0} to max allowed {1}".format(self.depth_m.value,self.INWATER_DEPTH)
        if self.depth_m.value is None:
            message += 'depth_m unknown. '
        elif self.depth_m.value >= self.INWATER_DEPTH: 
            message += "{0}: {1} >= {2}. ".format('depth_m',self.depth_m.value,self.INWATER_DEPTH)
            depth_in_water = True
        else:
            message += "{0}: {1} < {2}. ".format('depth_m',self.depth_m.value,self.INWATER_DEPTH)
            depth_in_water = False
        if debug_mode: print "in_water depth:{0} cond:{1} req:{2}".format(depth_in_water,spcond_in_water,instrument)
        if instrument   == 'all':         in_water = depth_in_water and spcond_in_water
        elif instrument == 'any':         in_water = depth_in_water or spcond_in_water
        elif instrument == 'depth_m':     in_water = depth_in_water 
        elif instrument == 'spcond_mScm': in_water = spcond_in_water
        return [in_water,message]
