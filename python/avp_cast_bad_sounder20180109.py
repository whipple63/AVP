#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        avp_cast
# Purpose:
#
# Author:      neve
#
# Created:     01/02/2012
#-------------------------------------------------------------------------------

#Built in Modules
from datetime import datetime, timedelta
import logging
import sys
import time
import traceback
#Installed Modules
import pytz.reference
#Custom Modules
import avp_db
import avp_util
import avp_winch

class Cast(object):
    ''' 
    Performs sonde cast
    
    see __init__ for arguments.
    Public Methods:
        setup
        pre_cast
        wait
        do_cast
        finish_cast
    '''
    REQUIRED_AIO_SUBSCRIPTIONS = ['voltage_ADC',        # System voltage*required by winch object
                                  'relay_ISCO',
                                  'relay_LISST',
                                  'reset_MM3',
                                  'relay_sonde',
                                  'relay_sounder']
    REQUIRED_GPS_SUBSCRIPTIONS = ('lat','lon','mode')
    REQUIRED_ISCO_SUBSCRIPTIONS = ('isco_status','sample_status')
    ISCO_INTERVAL = 10 # Min sample interval. Should be slow for the ISCO
    REQUIRED_LISST_SUBSCRIPTIONS = [] #('clean_water_level','seawater_pump')
    REQUIRED_MM3_SUBSCRIPTIONS = [
                'neg_limit_switch',  # The photo switch. Set to 1 when we've pulled the sonde too high.*
                'pos_limit_switch',  # The tension switch. Set to 1 when cable tension is too low or too high.*
                'in_position',       # if abs(position - desired_position) < deadband set to 1*
                'position',          # Current position*
                'enable_db',         # deadband enabled
                'deadband',          # deadband value
                'temp_fault',        # set to 1 if there is a temperature fault*
                'amps',              # mA being drawn*
                'amps_limit',        # Max amps allowed*
                'current_limit',     # set to 1 if amps reached amps_limit*
                'velocity',          # winch drum velocity*
                'pwm_out',           # Pulse Width Output*
                'PWM_limited',       # Is PWM limited to reduce amps?*
                'desired_position',  #*
                'save_pos',          # Should always be 1
                'temperature']       # Temperature of motor controller.
                                     # * Required by winch object
    REQUIRED_SONDE_SUBSCRIPTIONS = ['depth_m',      # Depth (pressure)*
                                    'spcond_mScm',  # Conductivity *
                                    'sampling',   # Is sonde in sampling (run) mode?*
                                    'logging']      # Are we logging to the database
                                                    # *Required by winch object
    REQUIRED_SOUNDER_SUBSCRIPTIONS = ['water_depth_working',]
    WIPE_TIMEOUT = 120  # If we're still wiping after this many seconds, abort cast.
    #LISST_WATER_LEVEL_MIN = 10 # No LISST cast if our flush water level is low.
    POST_CAST_OPTIONS = {'top':0,'default':None,'CWL':None,'PWL':None,'bottom':None}
    ADJ_SPCOND_SCALING = 0.4 # Scale the sampled value by this amount before storing to adjusted_spcond
    adjusted_spcond = None # This will be set based upon the conductivity seen at the beginning of a cast. In this way we can handle seasonal changes in conductivity.

        
    def __init__(self,context,program_name=__name__,**kwargs):
        '''
        Initializes Cast attributes, including databases, config values, and subscriptions
        
        Arguments:
            context      -- A context objec as instantiated from avp_util.AVPContext
        Keyword Arguments:
            program_name --
            cast_number  -- Defaults to the last cast number + 1
            cast_time    -- When to cast. Defaults to now.
            lisst_cast   -- Is it a LISST cast? True, False, or 'aborted'. Defaults to False.
            isco_cast    -- Is it a ISCO cast? Defaults to False.
            isco_bottle  -- Which ISCO bottle.
            isco_volume  -- How much water to put in ISCO bottle.
            wipe         -- Do we wipe the sonde before the cast. Defaults to True
            over_cast    -- When moving to the 
            pre_cal      -- Do we pull the sonde to the surface and calibrate it?
                            Usually only False for ISCO casts which aren't the first in a series. 
            park_pos     -- Where do we park when done.
                            'top' = 0
                            'default' = in tube
                            'CWL' = conductivity water line
                            'PWL' = Pressure water line
                            'bottom' = At bottom of cast
        '''
        self.context = context # Contains broker objects and config data.
        self.config = self.context.config
        self.program_name = program_name
        self.debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__) # set up logging
        self.casts_started = 0
        self.casts_completed = 0
        self.IPC_TABLE = self.config.get('db',{}).get('IPC_TABLE','avp_ipc')
        self.ipc_db = avp_db.AvpDB(self.config,self.IPC_TABLE)
        self._update_status('Scheduler re-started.')
        
    def pre_config(self,depth_target,cast_time=datetime.now(pytz.reference.LocalTimezone()),cast_number=None,
                   profile=True,max_sample_time=None,lisst_cast=False,isco_cast=False,
                   isco_bottle=1,isco_volume=1000,wipe=True,over_cast=0.2,pre_cal=True,
                   park_pos='default',load_config=False,**kwargs):
        '''
        Set up all the per-cast parameters.        
        Arguments:
            depth_target -- The depth to which we are casting.
        Keyword Arguments:
            cast_number  -- Defaults to the last cast number + 1
            cast_time    -- When to cast. Defaults to now.
            profile      -- Will we be moving while sampling. NEW
            max_sample_time -- How long should we sample integer (used for non profile casts) NEW
            lisst_cast   -- Is it a LISST cast? Defaults to False.
            isco_cast    -- Is it a ISCO cast? Defaults to False.
            isco_bottle  -- Which ISCO bottle.
            isco_volume  -- How much water to put in ISCO bottle.
            wipe         -- Do we wipe the sonde before the cast. Defaults to True
            over_cast    -- When moving to the 
            pre_cal      -- Do we pull the sonde to the surface and calibrate it?
                            Usually only False for ISCO casts which aren't the first in a series. 
            park_pos     -- Where do we park when done.
                            'top' = 0
                            'default' = in tube
                            'CWL' = conductivity water line
                            'PWL' = Pressure water line
                            'bottom' = At bottom of cast
            load_config -- Call load_config(reload_config=True) for every broker just in case avp.ini has changed.
        '''
        self.lisst_cast = lisst_cast
        self.isco_cast = isco_cast
        self.profile = profile
        self.max_sample_time = max_sample_time
        self.depth_target = float(depth_target)
        self.cast_number = cast_number
        self.cast_time = cast_time
        self.isco_bottle = int(isco_bottle)
        self.isco_volume = int(isco_volume)
        self.wipe = wipe
        self.over_cast = over_cast
        self.pre_cal = pre_cal
        self.park_pos = park_pos
        self.debug_mode = kwargs.get('debug_mode',False)
        self.logger.debug('Cast.pre_config')
        if self.profile == False:
            self.logger.debug('NON PROFILING CAST')
        if load_config is True: # re-read the config file in case it has changed.
            for broker_name in self.context.brokers:
                this_broker = getattr(self.context,broker_name)
                this_broker.load_config(reload_config=True,debug_mode=self.debug_mode)
        # Now some defaults
        self.abort_cast = {} # {type:hard|soft,reason:<description>, park:True|False}
        self.bottom_strike = False # True if we think we hit the bottom
        if self.isco_cast is True: # Can't do both in the same cast.
            if self.lisst_cast is True:
                self.abort_cast['type'] = 'soft'
                self.abort_cast['reason'] = 'Can not perform ISCO and LISST casts at the same time. Canceling LISST functionality'
                self.logger.warning(self.abort_cast['reason'])
                self.lisst_cast = False
            self.profile = False # Isco casts are at a static depth.
        if self.profile is False and self.max_sample_time is None: #If we aren't profiling, we need a max sample time.
            self.max_sample_time = 180.0
        # Get some configuration data There more be a clever way of doing this by iterating over parts of config
        cast_config = self.config.get('cast',{})
        self.PRE_CAST_DELAY     = float(cast_config.get('PRE_CAST_DELAY',0.0)) # Seconds to log data at top before moving sonde
        self.POST_CAST_DELAY    = float(cast_config.get('POST_CAST_DELAY',0.0)) # Seconds to log data at bottom after moving sonde
        self.LISST_START_OFFSET = float(cast_config.get('LISST_START_OFFSET',0.0))
        self.MAX_TARGET_ERROR   = float(cast_config.get('MAX_TARGET_ERROR',0.1))
        self.IPC_TABLE          = self.config.get('db',{}).get('IPC_TABLE','avp_ipc')
    def initial_calibration(self,**kwargs):
        '''
        Just the actions required to calibrate
        '''
        self.debug_mode = kwargs.get('debug_mode',True)
        self.pre_config(0,debug_mode=self.debug_mode)
        result = {}
        self.logger.debug('---------- STARTING CAST CALIBRATION PROCEDURE  ----------')
        result['01 aio_setup']               = self.aio_setup()
        result['02 broker_setup']            = self.broker_setup()
        result['03 get_tokens']              = self.get_tokens()
        result['04 check_instrument_status'] = self.check_instrument_status()
        result['05 check_depth']             = self.check_depth()
        result['06 init_instruments']        = self.init_instruments()
        result['07 init_db']                 = self.init_db()
        # Now the special stuff
        self.logger.info('Performing Initial winch Calibration')
        result['07.5 winch.calibration']          = self.winch.calibration(do_WL=True,end_pos=self.winch.CAL_POSITION,debug_mode=self.debug_mode)
        # Now finish
        result['17 finish_cast']         = self.finish_cast()
        result['abort_cast']             = self.abort_cast
        return result
        
    def start(self):# Now the cast procedure
        '''
        Step through the various actions in the cast procedure
        '''
        result = {}
        self.casts_started +=1
        if self.lisst_cast is True:
            cast_type = 'LISST '
        elif self.isco_cast is True:
            cast_type = '{0} ml in bottle {1} ISCO '.format(self.isco_volume,self.isco_bottle)
        else:
            cast_type = ''
        self.logger.debug('---------- STARTING {0}CAST TO {1} m ----------'.format(cast_type,self.depth_target))
        result['01 aio_setup']               = self.aio_setup()
        result['02 broker_setup']            = self.broker_setup()
        result['03 get_tokens']              = self.get_tokens()
        result['04 check_instrument_status'] = self.check_instrument_status()
        result['05 check_depth']             = self.check_depth()
        result['06 init_instruments']        = self.init_instruments()
        result['07 init_db']                 = self.init_db()
        result['08 check_position']          = self.check_position()
        try:
            result['09 pre_cast_park']       = self.pre_cast_park()
            result['10 pre_calibrate']       = self.pre_calibrate()
            result['11 pre_position']        = self.pre_position()
            result['12 wait_for_sched']      = self.wait_for_sched()
            result['13 start_sampling']      = self.start_sampling()
            result['14 data_collection']     = self.data_collection()
            result['15 stop_sampling']       = self.stop_sampling()
            result['16 post_cast_park']      = self.post_cast_park()
        except Exception as e:
            self.logger.critical("Cast Failed: {0}".format(e))
            traceback.print_stack()
            traceback.print_exc()
        finally:
            result['17 finish_cast']         = self.finish_cast()
            result['18 cast_number']            = self.cast_number
            result['19 casts_started']          = self.casts_started
            result['20 casts_completed']        = self.casts_completed
            result['21 abort_cast']             = self.abort_cast
            result['22 lisst_cast']             = self.lisst_cast
            result['23 isco_cast']             = self.isco_cast
        return result
        
    def aio_setup(self,**kwargs):
        '''
        Just get aio started and check power to instruments
        '''
        result = {}
        if self.abort_cast: return {}
        self.logger.debug('Cast.aio_setup')
        self._update_status('aio_setup')
        self.context.startup(startup='aio',debug_mode=self.debug_mode)
        self.aio = self.context.aio
        result['01 aio.get_token'] = self.aio.get_token(calling_obj=self.__class__.__name__,
                                                     program_name=self.program_name,
                                                     override=True, # Force acquire
                                                     debug_mode=self.debug_mode)
        if self.debug_mode: print("    AIO token acquire result:{0}".format(result['01 aio.get_token']['acquire_result']))
        if 'error' in result['01 aio.get_token'].get('acquire_result',None):
            self.abort_cast['type'] = 'soft'
            self.abort_cast['reason'] = 'Aborting Cast {0}. Unable to acquire aio token.'.format(self.cast_number)
            self.logger.critical(self.abort_cast['reason'])
            return result
        result['02 aio.add_subscriptions'] = self.aio.add_subscriptions(self.REQUIRED_AIO_SUBSCRIPTIONS,
                                                                     on_change=True,ignore_missing=True,
                                                                     debug_mode=self.debug_mode)
        time.sleep(1) # Get some values from aio
        #Make sure everything is on
        power_status = {}
        power_status['sonde'] = 1 if self.aio.relay_sonde.value==self.aio.RELAY_ON else 0
        power_status['sounder'] = 1 if self.aio.relay_sounder.value==self.aio.RELAY_ON else 0
        # These two are optional
        if ( hasattr(self.aio,"relay_LISST") ): power_status['lisst'] = 1 if self.aio.relay_LISST.value==self.aio.RELAY_ON else 0
        if ( hasattr(self.aio, "relay_ISCO")): power_status['isco'] = 1 if self.aio.relay_ISCO.value==self.aio.RELAY_ON else 0
        print("Instrument power status: {0}".format(power_status))
        if self.isco_cast is True: # Make sure ISCO is on
            if self.aio.relay_ISCO.value != self.aio.RELAY_ON: # Use aio since uniquely among brokers, the ISCO broker doesn't turn itself on with a resume
                self.aio.relay_ISCO.value = self.aio.RELAY_ON
                self.logger.debug('Turning on ISCO')
        elif self.lisst_cast is True: # Turn off ISCO
            if self.aio.relay_ISCO.value == self.aio.RELAY_ON: # Use aio since uniquely among brokers, the ISCO broker doesn't turn itself on with a resume
                self.aio.relay_ISCO.value = self.aio.RELAY_OFF
                self.logger.debug('Turning on ISCO')
        result['03 aio.tokenRelease'] = self.aio.tokenRelease(timeout=None,debug_mode=self.debug_mode)
        return result
    def broker_setup(self,interactive=False,**kwargs):
        '''
        Set up the rest of the brokers and their subscriptions
        '''
        if self.abort_cast: return {}
        self.logger.debug('Cast.broker_setup')
        self._update_status('broker_setup')
        result = {}
        # Need config
        needed_objects = ['aio','gps','mm3','sonde','sounder']
        if self.lisst_cast is True:
            needed_objects.append('lisst')
        if self.isco_cast is True:
            needed_objects.append('isco')
        '''
        # We look at self.context.brokers and see if we need to start anything
        for broker in needed_objects:
            if broker not in self.context.brokers:
                self.context.startup(broker)
            else:
                if self.debug_mode: print "Already instantiated {0} broker.".format(broker)
        '''
        result['01 context.startup'] = self.context.startup(needed_objects,debug_mode=self.debug_mode)
        #The Winch is a little special as it doesn't exist in context.
        self.winch = avp_winch.Winch(self.context,interactive)
        self.sonde = self.winch.sonde # Add subscriptions later
        # We can adjust condictivity threshold based upon readings at surface from previous cast
        if self.adjusted_spcond is not None:
            message = 'Adjusting'
            '''changed int to float because we have very low values in fresh water lakes'''
            if float(self.sonde.inwater_cond) > float(self.adjusted_spcond):
                message = 'Lowering'
            elif float(self.sonde.inwater_cond) < float(self.adjusted_spcond):
                message = 'Raising'
            else:
                self.adjuted_spcond = float(self.sonde.inwater_cond)
            if self.sonde.inwater_cond != self.adjusted_spcond:
                self.logger.debug('{0} in water conductivity threshold from {1} to {2} based on previous cast.'.format(message,self.sonde.inwater_cond,self.adjusted_spcond))
                self.sonde.inwater_cond = self.adjusted_spcond
        self.mm3 = self.winch.mm3
        result['02 mm3.add_subscriptions'] = self.mm3.add_subscriptions(self.REQUIRED_MM3_SUBSCRIPTIONS,on_change=False) # Changed on_change from True to False (on_new)
        self.sounder = self.context.sounder
        
        self.lisst = self.isco = self.gps = None
        if hasattr(self.context,'gps') is True:
            self.gps = self.context.gps
            result['03 gps.add_subscriptions'] = self.gps.add_subscriptions(self.REQUIRED_GPS_SUBSCRIPTIONS,on_change=True,verbose=False)
        if self.lisst_cast is True:
            self.lisst = self.context.lisst
        elif self.isco_cast is True:
            self.isco = self.context.isco
        # We will add the rest of the subscriptions later.
        return result
    def get_tokens(self,**kwargs):
        '''
        DO NOT override the mm3 token!
        '''
        if self.abort_cast: return {}
        self.logger.debug('Cast.get_tokens')
        self._update_status('get_tokens')
        result = {}
        result['01 sonde.get_token'] = self.sonde.get_token(calling_obj=self.__class__.__name__,
                                                         program_name=self.program_name,
                                                         override=True,debug_mode=self.debug_mode)
        if self.debug_mode: print("    Sonde token acquire result:{0}".format(result['01 sonde.get_token']['acquire_result']))
        if 'error' in result['01 sonde.get_token'].get('acquire_result',None):
            self.abort_cast['type'] = 'soft'
            self.abort_cast['reason'] = 'Aborting Cast {0}. Unable to acquire sonde token.'.format(self.cast_number)
            self.logger.critical(self.abort_cast['reason'])
            return result
        result['02 mm3.get_token'] = self.mm3.get_token(calling_obj=self.__class__.__name__,
                                                     program_name=self.program_name,
                                                     override=False,debug_mode=self.debug_mode)
        if self.debug_mode: print("    MM3 token acquire result:{0}".format(result['02 mm3.get_token']['acquire_result']))
        if 'error' in result['02 mm3.get_token'].get('acquire_result',None):
            self.abort_cast['type'] = 'soft'
            self.abort_cast['reason'] = 'Aborting Cast {0}. Unable to acquire mm3 token.'.format(self.cast_number)
            self.logger.critical(self.abort_cast['reason'])
            return result['02 mm3.get_token']
        if self.lisst_cast is True:
            result['03 lisst.get_token'] = self.lisst.get_token(calling_obj=self.__class__.__name__,
                                                             program_name=self.program_name,
                                                             override=True,debug_mode=self.debug_mode)
            if self.debug_mode: print("    LISST token acquire result:{0}".format(result['03 lisst.get_token']['acquire_result']))
            if 'error' in result['03 lisst.get_token'].get('acquire_result',None):
                self.abort_cast['type'] = 'soft'
                self.abort_cast['reason'] = 'Aborting Cast {0}. Unable to acquire LISST token.'.format(self.cast_number)
                self.logger.critical(self.abort_cast['reason'])
                return result['03 lisst.get_token']
        if self.isco_cast is True: # We need the ISCO token 
            result['04 isco.get_token'] = self.isco.get_token(calling_obj=self.__class__.__name__,
                                                           program_name=self.program_name,
                                                           override=True,debug_mode=self.debug_mode)
            if self.debug_mode: print("    ISCO token acquire result:{0}".format(result['04 isco.get_token']['acquire_result']))
            if 'error' in result['04 isco.get_token'].get('acquire_result',None):
                self.abort_cast['type'] = 'soft'
                self.abort_cast['reason'] = 'Aborting Cast {0}. Unable to acquire ISCO token.'.format(self.cast_number)
                self.logger.critical(self.abort_cast['reason'])
                return result['04 isco.get_token']
        return result
    def check_instrument_status(self,**kwargs):
        '''
        Makes sure required brokers are connected to their instruments and resumes them as necessary
        Returns:
            dict. 
                {} = already aborted cast
                {{action}{action_result}...}
        Raises:
            None
        '''
        if self.abort_cast: return {}
        self.logger.debug('Cast.check_instrument_status')
        self._update_status('check_instrument_status')
        result = {}
        # Check Sonde connection:
        result['01 sonde.broker_status 1'] = self.sonde.broker_status(timeout=None,debug_mode=self.debug_mode)
        if self.sonde.instr_connected is False:
            result['02 sonde.resume_broker'] = self.sonde.resume_broker(timeout=None,debug_mode=self.debug_mode)
            result['03 sonde.broker_status 2'] = self.sonde.broker_status(timeout=None,debug_mode=self.debug_mode)
            if self.sonde.instr_connected is False:
                self.abort_cast['type'] = 'soft'
                self.abort_cast['reason'] = 'Aborting cast {0}. Sonde broker unable to connect to instrument'.format(self.cast_number)
                self.logger.critical(self.abort_cast['reason'])
        result['04 sonde.add_subscriptions'] = self.sonde.add_subscriptions(self.REQUIRED_SONDE_SUBSCRIPTIONS,on_change=True)
        # Check Sounder connection:
        result['05 sounder.broker_status 1'] = self.sounder.broker_status(timeout=None,debug_mode=self.debug_mode)
        if self.sounder.instr_connected is False:
            result['05 sounder.resume_broker'] = self.sounder.resume_broker(timeout=None,debug_mode=self.debug_mode)
            result['07 sounder.broker_status 2'] = self.sounder.broker_status(timeout=None,debug_mode=self.debug_mode)
            if self.sounder.instr_connected is False:
                self.abort_cast['type'] = 'soft'
                self.abort_cast['reason'] = 'Aborting cast {0}. Sounder broker unable to connect to instrument'.format(self.cast_number)
                self.logger.critical(self.abort_cast['reason'])
        result['08 sounder.add_subscriptions'] = self.sounder.add_subscriptions(self.REQUIRED_SOUNDER_SUBSCRIPTIONS,on_change=True,verbose=False)
        if self.lisst_cast is True:
            result['09 lisst.broker_status 1'] = self.lisst.broker_status(timeout=None,debug_mode=self.debug_mode)
            if self.lisst.power_on is False and self.lisst.instr_connected is True:
                # This is a bad state, and will require some fixing.
                self.logger.warning('avp_cast found LISST connected but with power off.')
                result['09.1 lisst.suspend_broker'] = self.lisst.suspend_broker(timeout=None,debug_mode=self.debug_mode)
                result['09.2 lisst.broker_status 2'] = self.lisst.broker_status(timeout=None,debug_mode=self.debug_mode)
            if self.lisst.suspended is True:
                result['09.3 lisst.resume_broker 1'] = self.lisst.resume_broker(timeout=None,debug_mode=self.debug_mode) # This can take a while (timeout=40 sec)
                if result['09.03 lisst.resume_broker 1'].get('result',False) != 'ok':
                    self.logger.warning('Could not resume LISST, result = {0}. Canceling LISST portion of cast'.format(result['09.03 lisst.resume_broker 1']))
                    self.lisst_cast = 'aborted'
            if self.lisst.instr_connected is False:
                result['09.04 lisst.resume_broker 2'] = self.lisst.resume_broker(timeout=None,debug_mode=self.debug_mode)
                result['09.05 lisst.broker_status 3'] = self.lisst.broker_status(timeout=None,debug_mode=self.debug_mode)
                if self.lisst.instr_connected is False:
                    self.logger.warning('LISST broker unable to connect to instrument'.format(self.cast_number))
                    self.lisst_cast = 'aborted'
            else:
                if self.lisst.data_collection.value: # Are we still sampling from some previous failed cast?
                    result['09.06 lisst.stop_collection'] = self.lisst.stop_collection(timeout=None,debug_mode=self.debug_mode) # Just in case
                if self.lisst.data_file_transferred.value is False: # There's an un-transferred file!
                    if self.lisst.data_file_name.value is not None:
                        self.logger.warning('Found un-transferred LISST file {0}.'.format(self.lisst.data_file_name.value))
                        result['09.07 lisst.get_file'] = self.lisst.get_file(lisst_file=None,debug_mode=self.debug_mode)
                if self.lisst.clean_water_level.value < self.lisst.WATER_LEVEL_MIN:
                    self.logger.warning("LISST flush water at {0}% below minimum of {1}%. LISST will not be used this cast."
                                .format(self.lisst.clean_water_level.value,self.lisst.WATER_LEVEL_MIN))
                elif self.lisst.clean_water_level.value < self.lisst.WATER_LEVEL_WARN:
                    self.logger.warning("LISST flush water at {0}% below warning level of {1}%."
                                .format(self.lisst.clean_water_level.value,self.lisst.WATER_LEVEL_WARN))
                    self.lisst_cast = 'aborted'
            if self.lisst_cast is 'aborted': # Something went wrong
                result['09.08 lisst.tokenRelease'] = self.lisst.tokenRelease(timeout=None,debug_mode=self.debug_mode)
            else:
                result['09.09 lisst.add_subscriptions'] = self.lisst.add_subscriptions(self.REQUIRED_LISST_SUBSCRIPTIONS,on_change=True)
        elif self.isco_cast is True: # Only if not a LISST cast
            result['10 isco.broker_status1'] = self.isco.broker_status(timeout=None,debug_mode=self.debug_mode)
            if self.isco.instr_connected is False:
                # Turn on front panel
                #self.isco.sampler_on(**kwargs) # Not necessary
                result['10.1 isco.resume_broker'] = self.isco.resume_broker(timeout=None,debug_mode=self.debug_mode)
                result['10.2 isco.broker_status2'] = self.isco.broker_status(timeout=None,debug_mode=self.debug_mode)
                if self.isco.instr_connected is False:
                    self.abort_cast['type'] = 'soft'
                    self.abort_cast['reason'] = 'Aborting cast {0}. ISCO broker unable to connect to instrument'.format(self.cast_number)
                    self.logger.critical(self.abort_cast['reason'])
            result['10.3 isco.add_subscriptions'] = self.isco.add_subscriptions(self.REQUIRED_ISCO_SUBSCRIPTIONS,
                                                                           on_change=True,
                                                                           min_interval=self.ISCO_INTERVAL)
        return result
    def check_depth(self,**kwargs):
        '''
        Calculates cast depth
        Returns:
            dict. 
                {} = already aborted cast
                {{action}{action_result}...}
        Raises:
            None
        '''
		DEFAULT_DEPTH=5.5
        if self.abort_cast: return {}
        self.logger.debug('Cast.check_depth')
        self._update_status('check_depth')
        result = {}
        # calculate cast depth
        #result['01 max_depth'] = float(self.sounder.water_depth_working.value - self.sonde.INSTRUMENT_OFFSET - self.sonde.BOTTOM_OFFSET)
        result['01 max_depth'] = float(DEFAULT_DEPTH - self.sonde.INSTRUMENT_OFFSET - self.sonde.BOTTOM_OFFSET)
        if self.depth_target > result['01 max_depth']:
            self.logger.info("Depth target({0}m) exceeded max_depth({1}m). Using max_depth.".format(self.depth_target,result['01 max_depth']))
            self.depth_target = result['01 max_depth']
        elif self.depth_target == 0:
            self.depth_target = result['01 max_depth']
            #self.logger.info("Using calculated depth target of {0}m based upon depth of {1}m.".format(self.depth_target,self.sounder.water_depth_working.value))
            self.logger.info("Using calculated depth target of {0}m based upon depth of {1}m.".format(self.depth_target,DEFAULT_DEPTH))
        else:
            self.logger.info("Depth target is {0}m.".format(self.depth_target))
        return result
    def init_instruments(self,**kwargs):
        '''
        make sure all brokers we need are connected to their instruments.
        Turn on Sonde sampling, ISCO as necessary
        '''
        if self.abort_cast: return {}
        self.logger.debug('Cast.init_instruments')
        self._update_status('init_instruments')
        result = {}
        if self.sonde.sampling.value != True: # Are we sampling?
            #print "a Starting sampling= {0}".format(self.sonde.sampling.value)
            result['01 sonde.start_sampling'] = self.sonde.start_sampling()
            try:
                if 'error' in result['01 sonde.start_sampling']:
                    self.abort_cast['type'] = 'soft'
                    self.abort_cast['reason'] = 'Aborting Cast{0}. Error starting sampling: {1}'.format(self.cast_number,result['01 sonde.start_sampling'])
                    self.logger.critical(self.abort_cast['reason'])
                else:
                    self.logger.debug("Started sonde sampling.")
            except Exception as e:
                result['02 error'] = e
                self.abort_cast['type'] = 'soft'
                self.abort_cast['reason'] = 'Failed to start sonde sampling: {0}'.format(result['02 error'])
                self.logger.critical(self.abort_cast['reason'])
        return result
    def init_db(self,**kwargs):
        '''
        Insert a record into the cast database, and get or assign the cast_number.
        '''
        self.logger.debug('Cast.init_db')
        self._update_status('init_db')
        result = {}
        set_values = {}
        try:
            self.cast_db = avp_db.CastDB(self.config) # Instantiate database object
        except Exception as e:
            self.abort_cast['type'] = 'soft'
            self.abort_cast['reason'] = 'Error in Cast.init_db initializing Cast database: {0}'.format(e)
            self.logger.critical(self.abort_cast['reason'])
            return result
        try:
            # Database stuff
            self.ipc_db = avp_db.AvpDB(self.config,self.IPC_TABLE)
        except Exception as e:
            self.logger.critical('Error in Cast.__init__ initializing IPC database {0}'.format(e))
        if self.abort_cast: return result
        set_values['cast_time'] = datetime.now(pytz.reference.LocalTimezone())
        set_values['lat'] = 0
        set_values['lon'] = 0
        try:
            if self.gps.suspended is False:
                if self.gps.mode.value in (2,3): #Check if we are getting good position data
                    set_values['lat'] = self.gps.lat.value
                    set_values['lon'] = self.gps.lon.value
                else:
                    self.logger.debug('Bad GPS mode ({0}) for lat={1}, lon={2}'.format(self.gps.mode.value,
                                                                                         self.gps.lat.value,
                                                                                         self.gps.lon.value))
        except:
            pass
        set_values['sonde_id'] = self.sonde.sonde_ID.value
        set_values['sonde_sn'] = self.sonde.sonde_SN.value
        set_values['isco'] = self.isco_cast
        if self.lisst_cast == True: # can have value aborted, which won't go in database as boolean
            set_values['lisst'] = self.lisst_cast
        else:
            set_values['lisst'] = False
        set_values['bottom_strike'] = False
        result['01 set_values'] = set_values # Debugging
        result['02 cast_db.insert'] = self.cast_db.insert(set_values,**kwargs)
        try:
            db_cast_number = self.cast_db.cast_number(**kwargs).get('result',0)
        except Exception as e:
            self.abort_cast['type'] = 'soft'
            self.abort_cast['reason'] = 'Unable to get cast number from {0}. Aborting Cast: {1}'.format(result,e)
            self.logger.critical(self.abort_cast['reason'])
            return result
        if self.cast_number is None: # Automatically assign cast number. This is the default.
            self.cast_number = db_cast_number
        elif self.cast_number >= db_cast_number:
            self.logger.info('Using requested cast number {0} instead of {1}.'.format(self.cast_number,db_cast_number))
        else:
            self.logger.warning('Requested cast number {0} < {1}. '.format(self.cast_number,db_cast_number))
            self.cast_number = db_cast_number
        self.logger.info('This is cast {0} L={1} I={2} to {3}m'.format(self.cast_number,self.lisst_cast,self.isco_cast,self.depth_target))
        return result
    def check_position(self,**kwargs):
        '''
        Check to see if we really need to park.
        '''
        self.logger.debug('Cast.check_position')
        result = {}
        result['01 sonde.in_water'],result['02 sonde.in_water(reason)'] = self.sonde.in_water(debug_mode=self.debug_mode)
        if self.isco_cast is True:
            self.logger.info('No pre-cast calibration during ISCO casts')
            self.pre_cal = False
        elif self.profile is False:
            self.logger.info('No pre-cast calibration during non-profiling casts')
            self.pre_cal = False
        elif result['01 sonde.in_water']:
            self.logger.info('Sonde in water, not altering park routine ({0})'.format(result['02 sonde.in_water(reason)']))
        elif self.mm3.position.value > self.winch.wl_cond_position:
            self.logger.info('Sonde in water, not altering park routine ({0})'.format(result['02 sonde.in_water(reason)']))
        elif abs(self.sonde.depth_m.value) > self.sonde.PRESSURE_ERROR:
            self.logger.info('Sonde pressure {0}, greater than maximum allowable error ({1})'.format(self.sonde.depth_m.value,self.sonde.PRESSURE_ERROR))
        else:
            # No need to re-calibrate.
            self.logger.info('Sonde is out of water and pressure {0} is within allowable drift {1}. \
                              No calibration required.'.format(self.sonde.depth_m.value,self.sonde.PRESSURE_ERROR))
            self.pre_cal = False
        return result   
    def pre_cast_park(self,pre_park_location=0,**kwargs):
        '''
        Get us ready to perform cast. At the end of this function, we should be 
        at our calibration position.
        Returns:
            dict. 
                {'error': reason for error}
                {{sonde.get_token:}{mm3.get_token:}...}
            
        Raises:
            None
        '''
        if self.abort_cast: return {}
        if self.pre_cal == False: 
            self.logger.debug('Skipping Cast.pre_cast_park')
            return {}
        self.logger.debug('Cast.pre_cast_park')
        self._update_status('pre_cast_park')
        result = {}
        # Park at position self.CAL_POSITION and error check
        result['01 mm3.get_token'] = self.mm3.get_token(calling_obj=self.__class__.__name__,
                                                     program_name=self.program_name,
                                                     override=False,debug_mode=self.debug_mode)
        result['02 park'] = self.winch.park(park_location=self.winch.CAL_POSITION,
                                         limit_stop=True,
                                         debug_mode=self.debug_mode)
        if self.debug_mode: print("Park result: {0}".format(result['02 park']))
        result['03 stop_desc'] = avp_util.traverse_tree(result['02 park'],desired_key='stop_code')
        if result['03 stop_desc'] in ['pos_limit_switch','temp_fault']: #Make sure it didn't go badly.
            self.abort_cast['type'] = 'hard'
            self.abort_cast['reason'] = 'Aborting cast {0}. Hardware Fault {0}.'.format(self.cast_number,result['03 stop_desc'])
            self.abort_cast['park'] = False
            self.logger.critical(self.abort_cast['reason'])
        elif result['03 stop_desc'] == 'neg_limit_switch': #Tripped photo eye on the way up. Probably not a problem
            if self.mm3.position.value > self.winch.ZERO_POS_MAX_ERROR: #Unexpected. Shouldn't trip so far down.
                self.logger.warning("Unexpectedly tripped photoeye at position {0}.".format(self.mm3.position.value))
                # abort? RYAN
            else: #No big deal.
                self.logger.info("Tripped photo-eye at position {0}.".format(self.mm3.position.value))
        return result
    def pre_calibrate(self,**kwargs):
        '''
        If conditions are correct, we calibrate sonde pressure sensor.
        '''
        result = {}
        self.logger.debug('Cast.pre_calibrate')
        if self.abort_cast: return {}
        if self.pre_cal == False: return {} # There are a number of cases where we do not want to calibrate pressure sensor.
        self._update_status('pre_calibrate')
        # Are we out of the water?
        result['01 sonde.in_water'],result['02 sonde.in_water(reason)'] = self.sonde.in_water(instrument='all',**kwargs) # returns list with two elements
        if result['01 sonde.in_water'] is True:
            #We are in the water but shouldn't be
            self.abort_cast['type'] = 'hard'
            self.abort_cast['reason'] = 'Aborting Cast {0}. Unexpectedly in water at position {1}:{2}'.format(
                                self.cast_number,self.mm3.position.value,result['02 sonde.in_water(reason)'])
            self.abort_cast['park'] = True # We can still park
            self.logger.critical(self.abort_cast['reason'])
            return {'error':self.abort_cast['reason']}
        result['03 check_sonde_calibration'] = self.check_sonde_calibration()# See if we need to re-calibrate sonde pressure
        return result
    def pre_position(self,**kwargs):
        '''
        Move to waterline, wipe (optionally), then move more if an ISCO cast to make sure we don't suck air.
        '''
        if self.abort_cast: return {}
        self.logger.debug('Cast.pre_position')
        self._update_status('pre_position')
        result = {}
        abs_distance = self.winch.wl_position + self.winch.meters_to_clicks(self.over_cast) # over_cast is Fudge factor. Shouldn't ever go that far.
        rel_distance = abs_distance - self.mm3.position.value # If we are not at 0
        result['01 mm3.get_token'] = self.mm3.get_token(calling_obj=self.__class__.__name__,
                                                     program_name=self.program_name,
                                                     override=False,debug_mode=self.debug_mode)
        self.logger.info('Move {0} to position {1:6} ({2:6}) ------------------------------'.format(rel_distance, abs_distance,self.winch.wl_position))
        result['02 move_to_relative(WL)'] = self.winch.move_to_relative(rel_distance,
                                                                 speedlimit=self.winch.MED_SPEED,
                                                                 max_stopped=timedelta(seconds=5),
                                                                 stop_funct=self.winch.all_wl, # was using press_wl, but had problems with spurious values
                                                                 stop_args=[0], # 0 is lowering
                                                                 units='clicks',
                                                                 debug_mode=self.debug_mode)
        # MAKE SURE MOVE WENT WELL
        result['03 stop_code'] = avp_util.traverse_tree(result['02 move_to_relative(WL)'],desired_key='stop_code')
        if result['03 stop_code'] in ['pos_limit_switch','neg_limit_switch','temp_fault','ipc_conn']: #Make sure it didn't go badly.
            self.abort_cast['type'] = 'hard'
            self.abort_cast['reason'] = 'Hardware Fault {0} while lowering to waterline. Aborting cast'.format(result['03 stop_code'])
            self.abort_cast['park'] = False
            self.logger.critical(self.abort_cast['reason'])
            result['04 error'] = self.abort_cast['reason']
            return result
        #Do we want to wipe?
        if self.wipe: 
            if self.sonde.sampling.value == True: 
                result['05 sonde.stop_sampling'] = self.sonde.stop_sampling()
            time.sleep(5)	# added by Tony because self.sampling.Value is not up to date yet
            result['06 sonde.wipe'] = self.sonde.wipe()
            self.logger.info('Starting sonde wipe procedure, {0} wipes left'.format(self.sonde.wipes_left.value))
            # Wait until the wiping is done
            wipe_start = datetime.now(pytz.reference.LocalTimezone())
            while self.sonde.wipes_left.value > 0:
                time.sleep(1)
                if datetime.now(pytz.reference.LocalTimezone()) - timedelta(seconds=self.WIPE_TIMEOUT) > wipe_start:
                    self.abort_cast['type'] = 'soft'
                    self.abort_cast['reason'] = 'Unknown Fault, still wiping after {0} sec. ({1})'.format(self.WIPE_TIMEOUT,self.sonde.wipes_left)
                    self.abort_cast['park'] = True
                    self.logger.critical(self.abort_cast['reason'])
                    return result
            if self.sonde.sampling.value != True:
                print("c Starting sampling= {0}".format(self.sonde.sampling.value))
                result['07 sonde.start_sampling'] = self.sonde.start_sampling()
        else:
            result['08 wipe'] = 'no wipe requested'
        # If this is an ISCO or non-profile cast, we want to move down to our desired depth BEFORE we start sampling.
        if self.isco_cast is True or self.profile is False: 
            result['09 mm3.get_token'] = self.mm3.get_token(calling_obj=self.__class__.__name__,
                                                         program_name=self.program_name,
                                                         override=False,debug_mode=self.debug_mode)
            result['10 move_to_depth'] = self.winch.move_to_depth(self.depth_target,
                                                               speedlimit=self.winch.FAST_SPEED,
                                                               amps_limit=None,
                                                               limit_stop=True,
                                                               max_stopped=timedelta(seconds=5),
                                                               debug_mode=self.debug_mode)
            result['11 stop_code'] = avp_util.traverse_tree(result['10 move_to_depth'],desired_key='stop_code')
            if self.debug_mode: print("Pre-position result: {0}".format(result['move_to_depth']))
            # MAKE SURE pre-position MOVE WENT WELL
            if result.get('11 stop_code',{}) in ['pos_limit_switch','neg_limit_switch','temp_fault']: #Make sure it didn't go badly.
                self.abort_cast['type'] = 'hard'
                self.abort_cast['reason'] = 'Hardware Fault {0} while lowering to waterline. Aborting cast'.format(result['11 stop_code'])
                self.abort_cast['park'] = False
                self.logger.critical(self.abort_cast['reason'])
                result['12 error'] = self.abort_cast['reason']
        return result
    def wait_for_sched(self,**kwargs):
        # Wait until the correct time to cast.
        if self.abort_cast: return {}
        self.logger.debug('Cast.wait_for_sched')
        # _update_status called below
        result = {}
        if self.lisst_cast is True: # Sleep less so we have time to flush the lines
            result['01 time_buffer'] = timedelta(seconds=(self.lisst.SAMPLE_LATENCY*2)) # Time to flush the tube
        else:
            result['01 time_buffer'] = timedelta(seconds=0) # No wait 
        sleep_time = self.cast_time - datetime.now(pytz.reference.LocalTimezone()) - result['01 time_buffer']
        if sleep_time > timedelta(seconds=0):
            self._update_status('wait_for_sched')
            result['02 sleep_time'] = sleep_time
            self.logger.info("Sleeping {0} sec for beginning of cast".format(sleep_time))
            time.sleep(sleep_time.seconds)
        else:
            result['02 sleep_time'] = 0
        return result
    def start_sampling(self,**kwargs):
        '''
        Get all instruements sampling to the db and ready to move.
        '''
        if self.abort_cast: return {}
        self.logger.debug('Cast.start_sampling')
        self._update_status('start_sampling')
        result = {}
        if self.lisst_cast is True:
            result['01 sonde.in_water'] = self.sonde.in_water(instrument='spcond_mScm',debug_mode=self.debug_mode) # When instrument was 'all', sometimes it would fale when there were waves.
            if result['01 sonde.in_water'][0] == True:
                self.logger.info('Starting LISST pump and waiting {0:3} sec --------------------'.format(self.lisst.SAMPLE_LATENCY * 2))
                result['02 lisst.start_pump'] = self.lisst.start_pump(debug_mode=self.debug_mode)
                time.sleep(self.lisst.SAMPLE_LATENCY * 2) # Purge tube
                result['03 lisst.start_collection'] = self.lisst.start_collection(cast_number=self.cast_number,
                                                                               pump_delay=self.lisst.SAMPLE_LATENCY,
                                                                               debug_mode=self.debug_mode)
                self.logger.info("Started LISST collection on cast {0}: {1}".format(self.cast_number,result['03 lisst.start_collection']))
            else:
                self.logger.warning("Won't start LISST while sonde out of water{0}. Canceling LISST functions".format(result['01 sonde.in_water']))
                self.lisst_cast = 'aborted'
                time.sleep(self.lisst.SAMPLE_LATENCY * 2) # We still have some time until the sonde should start. Could call wait_for_sched() again....
        # Update cast time in database
        result['04 cast_db.start'] = self.cast_db.start(self.cast_number,debug_mode=self.debug_mode)
        # Start sonde logging to db
        result['05 sonde.start_logging'] = self.sonde.start_logging(self.cast_number,debug_mode=self.debug_mode)
        self.logger.info("Started sonde logging cast {0}: {1}".format(self.cast_number,result['05 sonde.start_logging']))
        if self.isco_cast is True:
            self.logger.debug("No pre-cast sleep during ISCO cast.")
        else:
            self.logger.info("Sleeping for {0} sec to get extra data".format(self.PRE_CAST_DELAY))
            time.sleep(self.PRE_CAST_DELAY) # Gives us time to gather some data before moving.
        return result
    def data_collection(self,**kwargs):
        '''
        Perform immediate cast
        Returns:
            dict. 
                {'error': reason for error}
                {{sonde.get_token:}{mm3.get_token:}...}
            
        '''
        if self.abort_cast: return {}
        self.logger.debug('Cast.data_collection')
        self._update_status('data_collection')
        result = {}
        if self.profile is True:
            self.logger.info('Performing cast to {0:6} m. at speed {1} ----------------------'.format(self.depth_target,self.winch.MED_SPEED))
            result['01 mm3.get_token'] = self.mm3.get_token(calling_obj=self.__class__.__name__,
                                                         program_name=self.program_name,
                                                         override=False,debug_mode=self.debug_mode)
            result['02 sonde.move_to_depth'] = self.winch.move_to_depth(self.depth_target,
                                                                    speedlimit=self.winch.MED_SPEED,
                                                                    amps_limit=None,
                                                                    limit_stop=True,
                                                                    in_pos=True,
                                                                    max_stopped=timedelta(seconds=10),
                                                                    pos_lim_max_time=timedelta(seconds=5),
                                                                    debug_mode=self.debug_mode)
            # Experimental try again code, only near the surface
            if self.sonde.depth_m.value < 1.5 and abs(self.sonde.depth_m.value - self.depth_target) > self.MAX_TARGET_ERROR:
                self.logger.warning('Cast stopped prematurely.  Trying to raise a little, then lower again.')
                result['02.1 sonde.move_to_depth'] = self.winch.move_to_depth(self.sonde.depth_m.value-0.20,	# try moving up 20 cm
                                                                        speedlimit=self.winch.MED_SPEED,
                                                                        amps_limit=None,
                                                                        limit_stop=True,
                                                                        in_pos=True,
                                                                        max_stopped=timedelta(seconds=10),
                                                                        pos_lim_max_time=timedelta(seconds=5),
                                                                        debug_mode=self.debug_mode)
                result['02.2 sonde.move_to_depth'] = self.winch.move_to_depth(self.depth_target,	# try a second time to make it to the target
                                                                        speedlimit=self.winch.MED_SPEED,
                                                                        amps_limit=None,
                                                                        limit_stop=True,
                                                                        in_pos=True,
                                                                        max_stopped=timedelta(seconds=10),
                                                                        pos_lim_max_time=timedelta(seconds=5),
                                                                        debug_mode=self.debug_mode)
                
			
            result['03 stop_code'] = avp_util.traverse_tree(result['02 sonde.move_to_depth'],desired_key='stop_code')
            if result['03 stop_code'] in ['neg_limit_switch','temp_fault','ipc_conn']: #Make sure it didn't go badly.
                self.abort_cast['type'] = 'hard'
                self.abort_cast['reason'] = 'Hardware Fault {0} while lowering to waterline. Aborting cast.'.format(result['03 stop_code'])
                self.abort_cast['park'] = False
                self.logger.critical(self.abort_cast['reason'])
                result['04 error'] = self.abort_cast['reason']
        elif self.isco_cast is True: # It is an ISCO cast
            if self.isco.isco_status.value == 1: # ready to sample'
                isco_start = datetime.now(pytz.reference.LocalTimezone())
                isco_timeout = isco_start + timedelta(seconds=self.isco.SAMPLE_TIMEOUT)
                self.logger.info('Taking {0} ml ISCO sample to bottle {1} from {2}m'.format(self.isco_volume,self.isco_bottle,self.sonde.depth_m.value))
                result['05 isco.take_sample'] = self.isco.take_sample(bottle=self.isco_bottle,
                                                                   volume=self.isco_volume,
                                                                   cast_number=self.cast_number,
                                                                   sample_depth=self.sonde.depth_m.value,
                                                                   debug_mode=self.debug_mode)
                time.sleep(10) # It will take much longer than this, but need to wait for sample_status to change.
                while self.isco.sample_status.value == 12: # 12 = Sample in progress
                    time.sleep(self.ISCO_INTERVAL)
                    if datetime.now(pytz.reference.LocalTimezone()) > isco_timeout:
                        self.logger.warning('ISCO timed out after {0} sec while sampling.'.format(self.isco.SAMPLE_TIMEOUT))
                        break
                if self.isco.sample_status.value == 0:
                    isco_elapsed = datetime.now(pytz.reference.LocalTimezone()) - isco_start
                    self.logger.info('ISCO sample successful after {0} sec.'.format(isco_elapsed.seconds))
                else:
                    self.logger.error('Unexpected ISCO sample status: {0}, ({1}).'.format(self.isco.get_isco_status(),self.isco.sample_status.value))
            else:
                # ISCO wasn't ready to sample.
                self.abort_cast['type'] = 'soft'
                self.abort_cast['reason'] = 'Aborting cast {0}. ISCO sample error {1} ({2}).'.format(self.cast_number,self.isco.get_isco_status(),self.isco.isco_status.value)
                self.logger.critical(self.abort_cast['reason'])
        elif self.profile is False: # This is a non-profile non-isco cast.
            self.logger.info("Sleeping {0} to sample during non-profiling cast.".format(self.max_sample_time))
            time.sleep(self.max_sample_time)
        if abs(self.sonde.depth_m.value - self.depth_target) > self.MAX_TARGET_ERROR:
            self.logger.warning('Cast to {0}{1} missed target of {2}.'.format(self.sonde.depth_m.value,self.sonde.depth_m.units,self.depth_target))
        return result
    def stop_sampling(self,**kwargs):
        '''
        Wait a little at the end of the cast to get more sonde data,then stop the sonde logging.
        Check for bottom strike.
        '''
        self.logger.debug('Cast.stop_sampling')
        self._update_status('stop_sampling')
        result = {}
        if self.lisst_cast is True:
            post_cast_delay = max(self.POST_CAST_DELAY,self.lisst.SAMPLE_LATENCY)
        else:
            post_cast_delay = self.POST_CAST_DELAY
        if self.isco_cast is True:
            self.logger.debug("No pre-cast sleep during ISCO or non-profiling cast.")
        else:
            self.logger.debug("Sleeping {0} sec after cast to get more sonde data".format(post_cast_delay))
            time.sleep(post_cast_delay)
        if self.lisst_cast is True:             
            self.logger.debug("Stopping LISST collection & pump")
            result['01 lisst.stop_collection'] = self.lisst.stop_collection(debug_mode=self.debug_mode)
            result['02 lisst.stop_pump'] = self.lisst.stop_pump(debug_mode=self.debug_mode)   
            # We will flush and get data after we park
        #Stop logging sonde data
        result['03 sonde.stop_logging'] = self.sonde.stop_logging(timeout=None,debug_mode=self.debug_mode)
        self.logger.debug("Stopped sonde logging: {0}".format(result['03 sonde.stop_logging']))
        if self.mm3.pos_limit_switch.value == 1: #probably a bottom strike.
            self.bottom_strike = True
            self.logger.warning('Bottom strike at {0} m on cast {1}'.format(self.sonde.depth_m.value,self.cast_number))
            self.cast_db.bottom_strike(self.cast_number) # Set the flag in the DB
        return result
    def post_cast_park(self,**kwargs):
        '''
        Post cast parking procedure
        '''
        if self.abort_cast.get('park',True) is False: #Skip parking if it was not a hardware problem
            return
        self.logger.debug('Cast.post_cast_park')
        self._update_status('post_cast_park')
        result = {}
        # Calculate the options.
        self.POST_CAST_OPTIONS['default'] = int(self.winch.wl_position/3.0)
        self.POST_CAST_OPTIONS['PWL'] = self.winch.wl_press_position
        self.POST_CAST_OPTIONS['CWL'] = self.winch.wl_cond_position
        self.POST_CAST_OPTIONS['bottom'] = None # Don't move, we're here already
        if self.park_pos not in list(self.POST_CAST_OPTIONS.keys()):
            self.logger.warning("Invalid park_pos value {0}. Must be in {1}. Using 'default'".format(self.park_pos,list(self.POST_CAST_OPTIONS.keys())))
            self.park_pos = 'default'
        result['01 mm3.get_token'] = self.mm3.get_token(calling_obj=self.__class__.__name__,
                                                     program_name=self.program_name,
                                                     override=False,debug_mode=self.debug_mode)
        park_location = self.POST_CAST_OPTIONS.get(self.park_pos,None)
        if park_location is not None:
            self.logger.debug("PARKING TO {0} at {1}".format(self.park_pos,park_location))
            if self.park_pos == 'default':
                get_surface_cond = True 
            else:
                get_surface_cond = False
            result['02 park'] = self.winch.park(park_location=park_location,
                                             limit_stop=False,
                                             get_surface_cond=get_surface_cond,
                                             in_pos=True,
                                             debug_mode=self.debug_mode)
            # We will use the conductivity here at the surface as our threshold for the rest of this cast, and the beginning of the next cast.
            self.adjusted_spcond = result['02 park'].get('surface_spcond',None)
            if self.adjusted_spcond is not None:
                self.adjusted_spcond *= self.ADJ_SPCOND_SCALING
                self.logger.info('Changing conductivity threshold from {0} to {1}'.format(self.sonde.inwater_cond,self.adjusted_spcond))
        else:
            message = "NOT parking, park_pos is {0}".format(self.park_pos)
            self.logger.debug(message)
            result['02 park'] = {'result':message}
        return result
    def finish_cast(self,**kwargs):
        ''' Finish up cast. These are things which should be done even if the cast has been aborted.
        '''
        self.logger.debug('Cast.finish_cast')
        self._update_status('finish_cast')
        result = {}
        if self.lisst_cast is True: # Get our LISST clean water sample
            result['01 lisst.get_file'] = self.lisst.get_file(lisst_file=None,debug_mode=self.debug_mode) # This should be blocking, and take a little while...
            if self.abort_cast == {}: # Everything went well.
                result['02 lisst.zero_sample'] = self.lisst.zero_sample(cast_number=self.cast_number,debug_mode=self.debug_mode)
                result['03 lisst.get_file(zero)'] = self.lisst.get_file(lisst_file=None,debug_mode=self.debug_mode)
        if self.profile is True and self.abort_cast == {} and self.park_pos is 'default': # No need to check if we know we are in the water.
            result['04 sonde.in_water'],result['05 sonde.in_water(reason)'] = self.sonde.in_water(debug_mode=self.debug_mode)
            result['06 check_sonde_calibration'] = self.check_sonde_calibration()# See if we need to re-calibrate sonde pressure
        if self.sonde.sampling.value == True: # It should be still running.
            result['07 stop_sampling'] = self.sonde.stop_sampling(debug_mode=self.debug_mode)
        # Fisnish off LISST and ISCO 
        if self.lisst_cast is True or self.lisst_cast is 'aborted':
            result['08 lisst.unsubscribe_all'] = self.lisst.unsubscribe_all(debug_mode=self.debug_mode)
            # Turn LISST off to save .400 mA
            result['09 lisst.suspend_broker'] = self.lisst.suspend_broker(debug_mode=self.debug_mode)
            result['10 lisst.tokenRelease'] = self.lisst.tokenRelease(debug_mode=self.debug_mode)
            if self.aio.relay_LISST.value == self.aio.RELAY_ON:
                # We need the aio token again....
                print("Waiting 2 sec and turning off LISST power")
                time.sleep(2)  # So broker can finish suspending
                result['11 aio.get_token'] = self.aio.get_token(calling_obj=self.__class__.__name__,
                                                             program_name=self.program_name,
                                                             override=True, # Force acquire
                                                             debug_mode=self.debug_mode)
                self.aio.relay_LISST.value = self.aio.RELAY_OFF 
        if self.isco_cast is True:
            result['12 isco.unsubscribe_all'] = self.isco.unsubscribe_all(debug_mode=self.debug_mode)
            result['13 isco.suspend_broker'] = self.isco.suspend_broker(debug_mode=self.debug_mode)
            result['14 isco.tokenRelease'] = self.isco.tokenRelease(debug_mode=self.debug_mode)
            result['15 aio.get_token'] = self.aio.get_token(calling_obj=self.__class__.__name__,
                                                         program_name=self.program_name,
                                                         override=True, # Force acquire
                                                         debug_mode=self.debug_mode)
            self.aio.relay_ISCO.value = self.aio.RELAY_OFF # Turn it off
        # unsubscribe everything else
        if hasattr(self,'gps') is True:
            result['16 gps.unsubscribe_all'] = self.gps.unsubscribe_all(debug_mode=self.debug_mode)
        result['17 sounder.unsubscribe_all'] = self.sounder.unsubscribe_all(debug_mode=self.debug_mode)
        result['18 sonde.unsubscribe_all'] = self.sonde.unsubscribe_all(debug_mode=self.debug_mode)
        result['19 mm3.unsubscribe_all'] = self.mm3.unsubscribe_all(debug_mode=self.debug_mode)
        result['20 aio.unsubscribe_all'] = self.aio.unsubscribe_all(debug_mode=self.debug_mode)
        # Release all other tokens
        if self.aio.token_acquired is True:
            result['21 aio.tokenRelease'] = self.aio.tokenRelease(debug_mode=self.debug_mode)
        result['22 sonde.tokenRelease'] = self.sonde.tokenRelease(debug_mode=self.debug_mode)
        result['23 mm3.tokenRelease'] = self.mm3.tokenRelease(debug_mode=self.debug_mode)
        self.cast_db.finish()        # Close the database.
        self._update_status('done')
        if self.abort_cast == {}:
            self.casts_completed += 1
        return result
    #Utility Functions
    def _update_status(self,status,**kwargs):
        '''
        Updates cast status filed in avp_ipc database table
        '''
        result = {}
        if hasattr(self,'ipc_db'):
            try:
                set_values={'value':status,'time':datetime.now(pytz.reference.LocalTimezone())}
                where_condition = {'broker':'cast','param':'cast_status'}
                result['01 db.update'] = self.ipc_db.update(set_values,
                                                         where_condition=where_condition,
                                                         where_join='AND',  # Same as default
                                                         where_oper='=',    # Same as default
                                                         debug_mode=self.debug_mode)
            except Exception as e:
                result['01 db.update'] = 'Failed to update cast status'
                self.logger.error("Failed to update cast status to {0}:{1}".format(status,e))
        return result
    def check_sonde_calibration(self):
        result = {}
        if abs(self.sonde.depth_m.value) <= self.sonde.PRESSURE_ERROR:
            self.logger.info('Sonde pressure of {0}m within {1}m of 0. Not calibrating'.format(self.sonde.depth_m.value,self.sonde.PRESSURE_ERROR))
            self.sonde.pressure_error = self.sonde.depth_m.value # Set the internal calibration offset
        else:
            # calibrate_pressure should leave the sonde in the same state it found it: sampling.
            result['01 sonde.calibrate_pressure'] = self.sonde.calibrate_pressure(check_instruments=True)
            time.sleep(1) # time to update subscription rates.
            if self.sonde.sampling.value != True: # This should not be needed.
                print("Starting sampling = {0}".format(self.sonde.sampling.value))
                result['02 sonde.start_sampling'] = self.sonde.start_sampling() # We need the sonde to check for WL    
        return result

def scheduled_cast(config,program_name=__name__,**kwargs):
    '''
    This function is used to cast when the calling process doesn't have its own context to pass in.
    It returns a cast object which will than need to be configured and started.
    '''
    logger = logging.getLogger('')
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    dbh = avp_db.DB_LogHandler(config)
    dbh.setLevel(logging.DEBUG)
    logger.addHandler(dbh)
    needed_objects = ['aio','gps','mm3','sonde','sounder']
    time_fmt = '%Y%m%d%H%M%S' # E.g. 20120222083000 for 8:30:00 on Feb 22, 2012
    debug_mode = kwargs.get('debug_mode',False)
    context = avp_util.AVPContext(config,startup=needed_objects,program_name=program_name,debug_mode=debug_mode) # Set up console context
    sched_cast = Cast(context,
                     program_name=program_name,
                     debug_mode=debug_mode)
    return sched_cast
     # Now pre_config() and start() will need to be called.

if __name__ == '__main__':
    '''
    '''
    kwargs = {}
    cloptions,config = avp_util.get_config(option_set='avp_cast') # parse command Line options
    logger = logging.getLogger('')
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    dbh = avp_db.DB_LogHandler(config)
    dbh.setLevel(logging.DEBUG)
    logger.addHandler(dbh)
    needed_objects = ['aio','gps','mm3','sonde','sounder']
    time_fmt = '%Y%m%d%H%M%S' # E.g. 20120222083000 for 8:30:00 on Feb 22, 2012
    debug_mode = cloptions.get('debug_mode',False)
    context = avp_util.AVPContext(config,
                                  startup=needed_objects,
                                  program_name='avp_cast',
                                  debug_mode=debug_mode) # Set up console context
    # How long do we need to wait
    cast_time_str = cloptions.get('cast_time',None)
    park_location = cloptions.get('park_location',0)
    depth_target = cloptions.get('depth_target',999.8)
    lisst_cast = cloptions.get('lisst_cast',False)
    isco_cast = cloptions.get('isco_cast',False)
    cast_time = datetime.now(pytz.reference.LocalTimezone())
    
    if cast_time_str is not None:
        try:
            cast_time = datetime.strptime(cast_time_str,time_fmt).replace(tzinfo=pytz.reference.LocalTimezone())
        except Exception as e:
            logger.error('Cast time {0} not in format {1}, casting now ({2})'.format(cast_time_str,time_fmt,e))
    isco_bottle = cloptions.get('isco_bottle',0)
    isco_volume = cloptions.get('isco_volume',1000) # in mL
    cast = Cast(context)
    cast.pre_config(cast_time_str=cast_time_str,
                park_location=park_location,
                depth_target=depth_target,
                cast_time=cast_time,
                lisst_cast=lisst_cast,
                isco_cast=isco_cast,
                isco_bottle=isco_bottle,
                isco_volume=isco_volume)
    result = cast.start()
    sys.exit()
 
