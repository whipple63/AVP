#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        mm3.py
# Purpose:     Contains class for Solutions Cubed Motion Mind 3 motor controller.
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

class MM3Broker(BrokerClient):
    '''
    This MM3Broker class adds methods and attributes specific to the
        Motion Mind 3 motor controller

    Public Methods: _move_to_setup, move_to_position, move_to_relative,
                    move_at_speed, stop, motor_cb, limit_cb, reset, restore,
                    write_store, store_position
    Instance Variables: broker_name, AMPS_LIMIT
    '''
    BROKER_NAME = 'mm3'
    def __init__(self,config,check_defaults=True,**kwargs):
        '''
        Initializes the MotionMind3 controller client's interface.
        '''
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        try: # IPC Database stuff
            self.ipc_db = avp_db.AvpDB(self.config,self.IPC_TABLE,polling=True)
        except Exception,e:
            self.logger.critical('Error in {0}.__init__ initializing IPC database {1}'.format(self.BROKER_NAME,e))
        self.amps_limit = self.temperature = self.position  = self.amps= None
        super(MM3Broker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
        if check_defaults is True:
            self._check_defaults(debug_mode=debug_mode)
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
        self.AMPS_LIMIT    = 3500
        self.DEFAULT_SPEED = 5
        self.MIN_SPEED     = 1
        self.IPC_TABLE = self.config.get('db',{}).get('IPC_TABLE','avp_ipc')
        # This broker uses the IPC_TABLE
        super(MM3Broker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def _check_defaults(self,**kwargs):
        '''
        Reads in a list of defaults from the config file.
        Checks these default values against the current values.
        Updates any which are wrong.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        defaults_to_set = {}
        checked_defaults = {}
        defaults = self.config[self.BROKER_NAME].get('defaults')
        if not defaults: return 0
        for param,value in defaults.items(): # make sure we have all these
            if hasattr(self,param):
                checked_defaults[param] = value
            else:
                self.logger.error("Broker {0} has no parameter {1}. Default not set.".format(self.BROKER_NAME,param))
        current_value_dict = self.get_value(checked_defaults.keys()) # returns a dictionary of values
        if 'error' in current_value_dict:
            self.logger.error("Error {cvec} in {bn}._check_defaults: {cvem} ({cvd})".format(
                                cvec=current_value_dict.get('error').get('code'),bn=self.BROKER_NAME,
                                cvem=current_value_dict.get('error').get('message'),
                                cvd=current_value_dict))
            return 0
        for param,default_value in checked_defaults.items():
            current_value = str(current_value_dict.get(param))
            if default_value != current_value:
                defaults_to_set[param] = default_value
                self.logger.info("{bn}:parameter {p} is {cv} will be set to default of {dv}".format(
                                    p=param,cv=current_value,dv=default_value,bn=self.BROKER_NAME))
        if len(defaults_to_set) > 0:
            self.get_token(override=True,
                           calling_obj="{0}._check_defaults".format(self.BROKER_NAME),
                           debug_mode=debug_mode)
            result = self.set(defaults_to_set)
            self.tokenRelease()
        else:
            self.logger.debug("No {0} default values to set.".format(self.BROKER_NAME))
            result = 1
        return result
    def _move_to_setup(self,speedlimit=None,velocity_limit_enable=1,enable_db=1,PWM_limit=1023,amps_limit=None,disable_pid=0,**kwargs):
        '''
        Sets a number of mm3 registers in anticipation of a move.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        set_dict = {}
        if speedlimit is None:
            speedlimit = self.DEFAULT_SPEED
            if debug_mode: print "No speedlimit given to _move_to_setup. Using default of {0}".format(self.DEFAULT_SPEED)
        if amps_limit is None:
            amps_limit = self.AMPS_LIMIT
        set_dict['velocity_limit'] = speedlimit
        set_dict['velocity_limit_enable'] = velocity_limit_enable # Turn on velocity limits
        set_dict['enable_db'] = enable_db # Turn on deadband enable
        set_dict['PWM_limit'] = PWM_limit # set this to max value
        set_dict['amps_limit'] = amps_limit # set this to default
        set_dict['disable_pid'] = disable_pid # don't disable PID
        result = {}
        result['set'] = self.set(set_dict,write_store=False,timeout=None,debug_mode=debug_mode)
        return result
    def move_to_position(self,location,speedlimit=None,amps_limit=None,enable_db=1,**kwargs):
        '''
        This method encapsulates a few settings which should be set before a move_to_absolute is performed.
        Instance variables:
            result
                _move_to_setup, db.update, set,
        '''        
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='move_to_position'): return {}
        result = {}
        if speedlimit is None:
            speedlimit = self.DEFAULT_SPEED
        if amps_limit is None:
            amps_limit = self.AMPS_LIMIT
        if debug_mode: print "{0} move_to_position: setup".format(str(datetime.now(pytz.reference.LocalTimezone())))
        result['_move_to_setup'] = self._move_to_setup(speedlimit=speedlimit,
                                                       amps_limit=amps_limit,
                                                       velocity_limit_enable=1,
                                                       enable_db=enable_db,
                                                       PWM_limit=1023,
                                                       disable_pid=0,
                                                       debug_mode=debug_mode)
        result['_clear_stop_reason'] = self._clear_stop_reason(debug_mode=debug_mode)
        if result['_clear_stop_reason'].get('error',False):
            self.logger.error("Error in {0}.move_to_position._clear_stop_reason: {1}".format(self.BROKER_NAME,result['_clear_stop_reason']['error']))
        if debug_mode: print "     {0} start move to {1}".format(str(datetime.now(pytz.reference.LocalTimezone())),location)
        try:
            result['set'] = self.set({'move_to_absolute':location},
                                     write_store=False,
                                     timeout=None,
                                     debug_mode=debug_mode)
            result['stop'] = ''
        except Exception,e:
            self.logger.error( "Error with set in {0}.move_to_absolute:{1}".format(self.BROKER_NAME,e) )
            result['stop'] = self.stop(debug_mode=debug_mode)
            result['error'] = e
        if result.get('error',False):
            self.logger.error("Error in {0}.move_to_position.set: {1}".format(self.BROKER_NAME,result['error']))
        if debug_mode: print "     {0} done".format(str(datetime.now(pytz.reference.LocalTimezone())))
        return result
    def move_to_relative(self,distance,speedlimit=None,velocity_limit_enable=1,enable_db=1,PWM_limit=1023,amps_limit=None,disable_pid=0,**kwargs):
        '''
        Abstract's mm3's move_to_rel functionality.
        '''
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='move_to_relative'): return {}
        result = {}
        result['_move_to_setup'] = self._move_to_setup(speedlimit=speedlimit,
                                                       velocity_limit_enable=velocity_limit_enable,
                                                       enable_db=enable_db,
                                                       PWM_limit=PWM_limit,
                                                       amps_limit=amps_limit,
                                                       disable_pid=disable_pid,
                                                       debug_mode=debug_mode)
        result['_clear_stop_reason'] = self._clear_stop_reason(debug_mode=debug_mode)
        if result['_clear_stop_reason'].get('error',False):
            self.logger.error("Error in {0}.move_to_relative._clear_stop_reason: {1}".format(self.BROKER_NAME,result['_clear_stop_reason']['error']))
        if debug_mode: print "     {0} start relative move:{1}".format(str(datetime.now(pytz.reference.LocalTimezone())),distance)
        try:
            result['set'] = self.set({'move_to_rel':distance},write_store=False,timeout=None,debug_mode=debug_mode) # Here is the move
        except Exception,e:
            self.logger.error( "Error with set in {0}.move_to_relative:{1}".format(self.BROKER_NAME,e) )
            self.stop(check_defaults=False,timeout=None,debug_mode=debug_mode)
            result['error'] = e
        if result.get('error',False):
            self.logger.error("Error in {0}.move_to_relative.set: {1}".format(self.BROKER_NAME,result['error']))
        if debug_mode: print "     {0} done".format(str(datetime.now(pytz.reference.LocalTimezone())))
        return result
    def move_at_speed(self,motorspeed,direction=None,amps_limit=None,enable_db=True,**kwargs):
        '''
        Abstract's mm3's move_at functionality.
        '''
        if not self._is_initialized(method_name='move_at_speed'): return {}
        if amps_limit is None:
            amps_limit = self.AMPS_LIMIT
        debug_mode = kwargs.pop('debug_mode',False) 
        result = {}
        try:
            motorspeed = abs(int(motorspeed))
        except Exception,e:
            self.logger.error("Invalid move_at_speed.motorspeed parameter:{0},e".format(motorspeed,e))
            return result
        if direction == 'up':
            motorspeed = motorspeed * -1
        elif direction == 'down':
            pass
        else:
            self.logger.debug("Error in move_at: {0} at {1} is an invalid command".format(direction,motorspeed))
            return result
        if enable_db is True: enable_db = 1
        else: enable_db = 0
        if amps_limit != self.amps_limit.value:
            if debug_mode: print "Setting amps_limit from {0} to {1} mA".format(self.amps_limit.value,amps_limit)
            result['set(amps_limit)'] = self.set({'amps_limit':int(amps_limit)},write_store=False,timeout=None,debug_mode=debug_mode)
        try:
            if debug_mode: print "{0} move_at_speed: setup".format(str(datetime.now(pytz.reference.LocalTimezone())))
            result['_clear_stop_reason'] = self._clear_stop_reason(debug_mode=debug_mode)
            #stop_reason = ''
            #set_values={'value':stop_reason,'time':datetime.now(pytz.reference.LocalTimezone())}
            #where_condition = {'broker':self.BROKER_NAME,'param':'stop_reason'}
            #self.ipc_db.update(set_values,
            #                   where_condition=where_condition,
            #                   where_oper='=',debug_mode=debug_mode)
            #if debug_mode: print "cleared stop_reason in database "
            result['set(velocity_limit_enable)'] = self.set({'velocity_limit_enable':0,
                                'velocity_limit':99,
                                'enable_db':enable_db,
                                'PWM_limit':1023,
                                'disable_pid':0},
                                write_store=False,timeout=None,debug_mode=debug_mode)
            if debug_mode: print "     {0} start move at {1}".format(str(datetime.now(pytz.reference.LocalTimezone())),motorspeed)
            result['set(move_at)'] = self.set({'move_at':motorspeed},write_store=False,timeout=None,debug_mode=debug_mode)
        except Exception,e:
            self.logger.error( "Error with set in {0}.move_at_speed:{1}".format(self.BROKER_NAME,e) )
            self.stop(check_defaults=False,timeout=None,debug_mode=debug_mode)
            result['set(move_at)'] = {'error':e}
        if result['set(move_at)'].get('error',False):
            self.logger.error("Error in move_at_speed: {0}".format(result['set(move_at)']['error']))
        return result
    def _clear_stop_reason(self,**kwargs):
        '''
        Clears stop reason from ipc database
        '''
        result = {}
        debug_mode = kwargs.pop('debug_mode',False) 
        where_condition = {'broker':self.BROKER_NAME,'param':'stop_reason'}
        set_values={'value':'','time':datetime.now(pytz.reference.LocalTimezone())}
        try:
            result['result'] = self.ipc_db.update(set_values,
                                                  where_condition=where_condition,
                                                  where_join='AND',
                                                  where_oper='=',
                                                  debug_mode=debug_mode)
            if debug_mode: print "cleared stop_reason in database "
            self.ipc_db.poll() # Clear any notification this caused.
        except Exception,e:
            self.logger.error( "Error in {0}._clear_stop_reason:{1}".format(self.BROKER_NAME,e) )
            result['stop'] = self.stop(check_defaults=False,debug_mode=debug_mode)
            result['error'] = e
        return result
    def stop(self,check_defaults=False,timeout=None,**kwargs):
        '''
        Stop the motor
        We could put a try here, and the except would kill the power to the mm3 via the aio broker.
        Keyword Arguments:
            check_defaults -- Defaults to False
        '''
        result = {}
        debug_mode = kwargs.pop('debug_mode',False) 
        if self.token_acquired is False: # if we already had the token, do nothing with it
            self.get_token(override=True,
                           calling_obj="{0}.stop".format(self.BROKER_NAME),
                           debug_mode=debug_mode)
            releaseToken = True
        else:
            releaseToken = False
        result['set'] = self.set({'move_at':0,'PWM_limit':0,'disable_pid':1},write_store=False,timeout=timeout,debug_mode=debug_mode) #Stop motor
        if releaseToken == True:
            self.tokenRelease(timeout=timeout,debug_mode=debug_mode)
        if result['set'].get('error',False):
            self.logger.error("In {0}.stop: {1}".format(self.BROKER_NAME,result['set']['error']))
        if check_defaults:
            self._check_defaults(debug_mode=debug_mode)
        return result
    def motor_cb(self,date_stamp,callback_obj,**kwargs):
        ''' This method will get called on any motor fault.
        It will often be used as a callback routine.
        '''
        result = {}
        if callback_obj.value == 1:
            result['stop'] = self.stop() # Stop Motor due to callback
            set_values = {'value':'{0}'.format(callback_obj.data_name),
                          'time':datetime.now(pytz.reference.LocalTimezone())}
            where_condition = {'broker':self.BROKER_NAME,'param':'stop_reason'}
            self.ipc_db.update(set_values,
                               where_condition=where_condition,
                               **kwargs)
            # Determine cause of fault.
            if callback_obj.data_name == 'current_limit':
                result['message'] = 'MM3 Current Limited at {0} mA'.format(self.amps_limit.value)
                self.logger.warning(result['message'])
            elif callback_obj.data_name == 'temp_fault':
                if 'temperature' not in self.subscriptions: # Can't assume we are subscribed to temperature
                    self.get_value(['temperature'])
                result['message'] = 'MM3 Temperature Error {0} {1}'.format(self.temperature.value,self.temperature.units)
                self.logger.critical(result['message'])
            else:
                result['message'] = 'MM3 unknown Error {0} {1}'.format(self.temperature.value,self.temperature.units)
                self.logger.critical(result['message'])
        else:
            # Just the bit resetting
            self.logger.debug("{0} motor callback reset.".format(callback_obj.data_name))
    def limit_cb(self,date_stamp,callback_obj):
        ''' This method will get called on any limit switch trip.
        It will often be used as a callback routine.
        '''
        if callback_obj.value == 1:
            if 'position' not in self.subscriptions: # Can't assume we are subscribed to temperature
                self.get_value(['position'])
            # Determine cause of fault.
            if callback_obj.data_name == 'neg_limit_switch':
                self.logger.info('Upper limit photo-switch tripped. Position = %s' % self.position.value)
            elif callback_obj.data_name == 'pos_limit_switch':
                self.logger.info('Cable tension switch tripped. Position = %s' % self.position.value)
            else:
                self.logger.error('Unknown limit callback: {0}'.format(callback_obj.data_name))
        else:
            # Just the bit resetting
            self.logger.debug("{0} limit callback reset.".format(callback_obj.data_name))
    def reset(self,timeout=None,**kwargs):
        ''' Implements the Motion Mind 3's reset command
        Sending the RESET command causes the Motion Mind Controller to stop the motor and software reset.
        '''
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='reset'):
            return 0
        self._json_id += 1
        result =  self.socket_handler.send_rpc('reset',
                                               self._json_id,
                                               timeout=timeout,
                                               params=None,
                                               debug_mode=debug_mode)
        if debug_mode: print "mm3Broker.reset result:{0}".format(result)
        return self._result_checker(result)
    def restore(self,timeout=None,**kwargs):
        ''' Implements the Motion Mind 3's resore command
        The restore command restores the factory default values to EEPROM. Since this command writes to
        EEPROM, the motor is stopped after the command is deemed valid.
        '''
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='restore'): return 0
        self._json_id += 1
        result =  self.socket_handler.send_rpc('restore',
                                               self._json_id,
                                               timeout=timeout,
                                               params=None,
                                               debug_mode=debug_mode)
        if debug_mode: print "mm3Broker.restore result:{0}".format(result)
        return self._result_checker(result)
    def do_write_store(self,params,**kwargs): #Can't call this write-store since there is already a parameter called that
        ''' Implements the Motion Mind 3's write store command
        '''
        if not self._is_initialized(method_name='do_write_store'): return {}
        debug_mode = kwargs.pop('debug_mode',False) 
        result = self.set(params,write_store=True,timeout=None,debug_mode=debug_mode)
        return result
    def store_position(self,position=None,**kwargs):
        '''Store current MM3 position to EEPROM
        If position isn't given, stores current position
        '''
        if not self._is_initialized(method_name='store_position'): return {}
        debug_mode = kwargs.pop('debug_mode',False) 
        if position is None:
            result = self.get_value(['position'],verbose=False,debug_mode=debug_mode)
            position = self.position.value
        if debug_mode: print "Saving position {0} to EEPROM".format(position)
        result = self.do_write_store(params={'position':position}, debug_mode=debug_mode)
        return result
