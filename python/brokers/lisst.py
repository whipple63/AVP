#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        lisst.py
# Purpose:     Contains class for Sequoia LISST
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


class LisstBroker(BrokerClient):
    '''
    Adds methods and attributes specific to the LISST
    Public Methods: get_file, delete_file, start_collection, stop_collection
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'lisst'
    MAX_FLUSH_TIME = 60 # Will not flush for longer than this. Limited by broker as well.
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(LisstBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
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
        self.SAMPLE_LATENCY      = 0
        self.FLUSH_TIME          = 5
        self.ZERO_TIME           = 10
        self.ZERO_FLUSH_DELAY    = 3
        self.FILE_TIMEOUT        = 20 #Longer timeout for file transfer.
        self.WATER_LEVEL_MIN     = 0.0
        self.WATER_LEVEL_WARN    = 10.0
        super(LisstBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def get_file(self,lisst_file=None,**kwargs):
        # Process file from lisst data recorder.  Empty lisst_file retrieves most recent.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='get_file'): return {}
        self._json_id += 1
        self.logger.debug('Downloading LISST file')
        if lisst_file is None:
            params = None
        else:
            params = {'lisst_file':lisst_file}
        result = self.socket_handler.send_rpc('get_file',
                                              self._json_id,
                                              timeout=self.FILE_TIMEOUT,
                                              params=params,
                                              debug_mode=debug_mode)
        return self._result_checker(result)
    def delete_file(self,lisst_file,timeout=None,**kwargs):
        # delete file from lisst data recorder.  File name must be given.
        if not self._is_initialized(method_name='delete_file'): return {}
        self._json_id += 1
        result =  self.socket_handler.send_rpc('delete_file',
                                               self._json_id,
                                               timeout=timeout,
                                               params={'lisst_file':lisst_file},
                                               **kwargs)
        return self._result_checker(result)
    def start_collection(self,cast_number,pump_delay=0,timeout=None,**kwargs):
        # start LISST data collection.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='start_collection'): return {}
        self._json_id += 1
        result =  self.socket_handler.send_rpc('start_collection',
                                               self._json_id,
                                               timeout=timeout,
                                               params={"cast_number":cast_number,"pump_delay":pump_delay},
                                              debug_mode=debug_mode)
        return self._result_checker(result)
    def stop_collection(self,timeout=None,**kwargs):
        # stop data collection.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='stop_collection'): return {}
        self._json_id += 1
        result = self.socket_handler.send_rpc('stop_collection',
                                              self._json_id,
                                              timeout=timeout,
                                              params=None,
                                              debug_mode=debug_mode)
        return self._result_checker(result)
    def is_pumping(self,**kwargs):
        result =  self.get_value(['seawater_pump'],**kwargs)
        return avp_util.t_or_f(result.get('seawater_pump',False))
    def start_pump(self,timeout=None,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        result = self.set({'seawater_pump':True},timeout=timeout,debug_mode=debug_mode)
        return result
    def stop_pump(self,timeout=None,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        result = self.set({'seawater_pump':False},timeout=timeout,debug_mode=debug_mode)
        return result
    def is_flushing(self,**kwargs):
        result = self.get_value(['clean_water_flush'],**kwargs)
        return avp_util.t_or_f(result.get('clean_water_flush',False))
    def flush(self,blocking=False,flush_time=None,**kwargs):
        '''
        Opens and closes flush valve for a set amount of time.
        Arguments:
        FLUSH_TIME - Seconds between opening and closing flush valve.
        blocking - If True, wait for fluch to complete before returning
        '''
        if flush_time is None:
            flush_time = self.FLUSH_TIME
        debug_mode = kwargs.pop('debug_mode',False)
        if blocking:
            result = self._do_flush(flush_time=flush_time,debug_mode=debug_mode)
        else:
            name = "{0}.flush".format(self.BROKER_NAME)
            flush_thread = threading.Thread(target=self._do_flush,
                                            name=name,
                                            kwargs = {'FLUSH_TIME':flush_time,'thread':True,'debug_mode':debug_mode})
            if debug_mode: print "Spawning {0} as {1} with FLUSH_TIME={2}".format(self._do_flush,name,flush_time)
            flush_thread.start()
            result  = {'result':'ok','message':'Flush routine started as a thread','thread':flush_thread}
        return result
    def _do_flush(self,flush_time=None,thread=False,**kwargs):
        '''
        Open flush valve,
        wait flush_time
        close flush valve.
        return dictionary of results
        '''
        if flush_time is None:
            flush_time = self.FLUSH_TIME
        if flush_time > self.MAX_FLUSH_TIME:
            return {'error':'{0} is > MAX_FLUSH_TIME of {1}'.format(flush_time,self.MAX_FLUSH_TIME)}
        result = {}
        self.logger.info("Flushing LISST for {0} seconds".format(flush_time))
        result['flush_on'] = self.__flush_on()
        time.sleep(int(flush_time))
        result['flush_off'] = self._flush_off()
        self.logger.info("LISST flush done.")
        if thread:
            self.logger.info("Flush thread result {0}".format(result))
        else:
            return result
    def __flush_on(self):
        '''
        '''
        return self.set({'clean_water_flush':True})
    def _flush_off(self):
        '''
        '''
        result =  self.set({'clean_water_flush':False})
        # We need to be very sure this is turned off
        if result.get('error',{}).get('code',False) == -31929: # A token error?
            self.get_token(program_name=__name__,
                            calling_obj=self.__class__.__name__,
                            override=True)
            result = self.set({'clean_water_flush':False}) # Try again
        return result
    def zero_sample(self,cast_number,**kwargs):
        '''
        Blocking
        Turns on Starts flush procedure as a thread,
        waits
        Starts sampling
        waits
        stops sampling
        Joins with flush thread
        returns
        '''
        result = {}
        debug_mode = kwargs.pop('debug_mode',False)
        self.logger.debug('LISST zero sample procedure for cast {0}'.format(cast_number))
        result['flush'] = self.flush(blocking=True,flush_time=self.FLUSH_TIME,debug_mode=debug_mode)
        time.sleep(self.ZERO_FLUSH_DELAY) # Give the flush time to start.
        result['start_collection'] = self.start_collection(cast_number=cast_number,pump_delay=0,debug_mode=debug_mode)
        time.sleep(self.ZERO_TIME)
        result['stop_collection'] = self.stop_collection(debug_mode=debug_mode)
        return result
