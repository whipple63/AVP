#Built in Modules
from datetime import datetime, timedelta
import logging
from math import pi
import os
from select import select as sselect
from time import sleep,time
import threading
#Installed Modules
import pytz.reference
#Custom Modules
import avp_db
import avp_util

try:
    # Windows
    from msvcrt import kbhit
except ImportError:
    # Linux
    import termios, sys
    if os.isatty(sys.stdout.fileno()):
        fd = sys.stdin.fileno()
        new_term = termios.tcgetattr(fd) 
        old_term = termios.tcgetattr(fd)
        new_term[3] = new_term[3] & ~termios.ICANON & ~termios.ECHO # & = Bitwise And
        def set_normal_term():
            '''
            Switch to Normal Termainal
            '''
            termios.tcsetattr(fd, termios.TCSAFLUSH, old_term)
        def set_curses_term():
            '''
            switch to unbuffered terminal
            '''
            termios.tcsetattr(fd, termios.TCSAFLUSH, new_term)
        def kbhit():
            '''
            Look for key press
            '''
            dr,dw,de = sselect([sys.stdin], [], [], 0)
            return dr != []
    else:
        def set_normal_term():
            pass
        def set_curses_term():
            pass
        def kbhit():
            return

class Winch(object):
    '''
    This class attempts to encapsulate as much of the winch functionality as possible.
    It should simplify the interface while still allowing as much functionality as possible
    It should move to avp_broker when the context func
    Public Methods:
            move_to_absolute    --  Move to a specified location
            move_to_relative    --  Move a relative number of "clicks"
            move_at_speed       --  Move at a certain speed
            move_to_depth       --  Move to a given water depth
            monitor_move        --  Monitors & controls moving winch. Prints out status info.
            feedback_header     --  Returns a header for feedback output
            press_wl            --  Checks for a change in waterline due to pressure
            cond_wl             --  Checks for a change in waterline due to conductivity
            any_wl              --  Checks for either of the above
            at_depth            --  Checks to see if a given depth has been reached.
            meters_to_clicks    --  Converts meters to clicks
            clicks_to_meters    --  Converts clicks to meters
    Instance Variables:
            added_subscriptions --  ?
            motorspeed          --  ?
    '''
    REQUIRED_MM3_SUBSCRIPTIONS = ('current_limit','desired_position',
                                  'in_position','position','velocity',
                                  'neg_limit_switch','pos_limit_switch',
                                  'pwm_out',
                                  'PWM_limited','amps','amps_limit',
                                  'temp_fault')
    DESIRED_SONDE_SUBSCRIPTIONS = ('depth_m','sampling')
    DESIRED_AIO_SUBSCRIPTIONS = ('relay_5V',
                                 'reset_MM3',
                                 'limit_switch_enable',
                                 'tension_switch_enable',
                                 'voltage_ADC',) # Aliases defined in avp.ini
    
    def __init__(self,context,interactive=True,**kwargs):
        '''
        motor_broker usually passed in as new_cast.mm3
        the sonde_broker and aio_broker are optional. they are only used for monitoring information.
        
        interactive tells the winch if we are connected to the console or not. Effects some print and log statements
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        if debug_mode:
            self.logger.setLevel(logging.INFO)
        self.config = context.config
        self.mm3 = context.mm3
        self.interactive = interactive
        self.stop_reason = None # Updated from ipc_db
        self.load_config(reload_config=False)
        self.added_subscriptions = {} # may want to unsubscribe when done.
        self._add_subscriptions(self.mm3,self.REQUIRED_MM3_SUBSCRIPTIONS)
        self.motorspeed = self.SLOW_SPEED # Used for move_to_absolute and move_to_relative
        # See if we have a sonde or aio object to use and set up dummy values if not
        if hasattr(context, 'sonde') is False:
            self.logger.error('Winch did not recieve sonde class on initialization')
            self.sonde = None
        else:
            self.sonde = context.sonde
            if hasattr(self.sonde,'spcond_mScm'): self.DESIRED_SONDE_SUBSCRIPTIONS = self.DESIRED_SONDE_SUBSCRIPTIONS + ('spcond_mScm',)
            if hasattr(self.sonde,'spcond_uScm'): self.DESIRED_SONDE_SUBSCRIPTIONS = self.DESIRED_SONDE_SUBSCRIPTIONS + ('spcond_uScm',)
            self.sonde.start_sampling()
            self._add_subscriptions(self.sonde,self.DESIRED_SONDE_SUBSCRIPTIONS)
        if context.aio.__class__ == None.__class__:
            self.logger.error('Winch did not recieve aio class on initialization')
        else:
            self.aio = context.aio
            self._add_subscriptions(self.aio,self.DESIRED_AIO_SUBSCRIPTIONS)
        # Callbacks, some of which may be duplicated in supervisor, but that is ok.
        self.mm3.add_callback({'current_limit':self.mm3.motor_cb,
                              'temp_fault':self.mm3.motor_cb})
        self.amps = self.get_amps_limits(context.config,debug_mode=debug_mode) # Populates self.amps
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        '''
        if reload_config is True:
            self.config.reload()
        w_config=self.config.get('winch',{}) #Simplifies code to follow
        self.POSITION_DB        = int(w_config.get('POSITION_DB',100)) # Deadband when comparing position to desired_position
        self.SLOW_SPEED         = int(w_config.get('SLOW_SPEED',   5)) # Slow
        self.MED_SPEED          = int(w_config.get('MED_SPEED',   10)) # Med
        self.FAST_SPEED         = int(w_config.get('FAST_SPEED',  15)) #Fast
        self.SLOWDOWN_POSITION  = int(w_config.get('SLOWDOWN_POSITION',80000)) # When raising, this is the point at which we should slow down to enter the tube.
        self.CAL_POSITION       = int(w_config.get('CAL_POSITION',5000)) # Calibrate the pressure at this position
        self.wl_position        = int(w_config.get('wl_position',49000))
        self.wl_press_position  = int(w_config.get('wl_press_position',48000)) 
        self.wl_cond_position   = int(w_config.get('wl_cond_position',35000)) 
        self.MAX_CAST_DEPTH     = float(w_config.get('MAX_CAST_DEPTH',0.500)) # Low value for safety, will probably be much higher. 
        self.SLOWDOWN_DEPTH     = float(w_config.get('SLOWDOWN_DEPTH',0.020)) #Slow down when raising above this to reduce wear on sonde.
        self.CABLE_LENGTH       = float(w_config.get('CABLE_LENGTH',12.0)) # Limits cast depth to cable length
        self.ZERO_POS_MAX_ERROR = int(w_config.get('ZERO_POS_MAX_ERROR',10000))
        self.CLICKS_PER_REVOLUTION   = int(w_config.get('CLICKS_PER_REVOLUTION',320000)) #
        DRUM_DIAMETER           = float(w_config.get('DRUM_DIAMETER',0.32)) #
        self.CLICKS_PER_METER   = self.CLICKS_PER_REVOLUTION/(DRUM_DIAMETER * pi) 
        return
    def _add_subscriptions(self,instrument_object,subscription_list,**kwargs):
        ''' Subscribes to any needed parameters if they are not aleady subscribed.
        NEED TO HANDLE UPDATE RATES
        '''
        new_subscriptions = []
        for item in subscription_list: # Subscribe to anything we need which isn't already subscribed to
            if item not in instrument_object.subscriptions:
                new_subscriptions.append(item) # remember what we subscribed to
        if len(new_subscriptions) > 0:
            self.logger.debug("Adding winch subscriptions to {0}.{1}".format(instrument_object.BROKER_NAME,new_subscriptions))
            instrument_object.add_subscriptions(new_subscriptions,on_change=True,subscriber=instrument_object.BROKER_NAME,ignore_missing=True,**kwargs)
        self.added_subscriptions.update({instrument_object:new_subscriptions})
        return
    def _done(self):
        ''' Called when we are done with the winch object.
        Does some un-subscribing
        '''
        for instrument_object,subscription_list in list(self.added_subscriptions.items()):
            if len(self[instrument_object]) > 0:
                instrument_object.unsubscribe(subscription_list)
        return
    def move_to_absolute(self,location,speedlimit=None,amps_limit=None,in_water=None,in_pos=False,stop_funct=None,stop_args=None,**kwargs):
        '''
        Moves winch to an absolute position.
        
        Arguments:
            location -- Where to move to
        Keyword Arguments:
            speedlimit -- Velocity limit to impose on the PID controller.
            amps_limit -- Amperage limit to impose on the PID controller.
            debug_mode --
        '''
        debug_mode = kwargs.get('debug_mode',False)
        if speedlimit is None:
            speedlimit = self.mm3.DEFAULT_SPEED
        result = {}
        self.move_warnings()
        self.logger.debug("Moving to {0} at speed {1}.".format(location, speedlimit))
        print("---------- Press ANY key to stop. ----------")
        if not amps_limit:
            if location <= self.mm3.position.value:
                up = True 
            else:
                up = False
            result['amps_limit'] = self.amps_for_speed(speedlimit,
                                                       up=up,
                                                       in_water=in_water,
                                                       debug_mode=debug_mode)
            amps_limit = result['amps_limit'].pop('result',self.mm3.AMPS_LIMIT)
            if debug_mode: print("Set amps_limit to {0}ma".format(amps_limit))
        self._winch_move_setup(debug_mode=debug_mode,
                                limit_stop=False,
                                in_pos=in_pos) # returns nothing
        result['move_to_position'] = self.mm3.move_to_position(location,
                                                               speedlimit=speedlimit,
                                                               amps_limit=amps_limit,
                                                               debug_mode=debug_mode)
        if result['move_to_position'].get('error',{}).get('message',False):
            result['error'] = "move_to_absolute.move_to_position error: {0}".format(result['move_to_position']['error']['message'])
            self.logger.error(result['error'])
        else: # No Error
            if debug_mode: print("move_to_position result: {0} {1}".format(result['move_to_position'],str(datetime.now(pytz.reference.LocalTimezone()))))
            result['monitor_move'] = self.monitor_move(max_stopped=timedelta(seconds=30),# These are all the defaults and optional
                                                       stop_funct=stop_funct,
                                                       stop_args=stop_args,
                                                       max_zero_v=timedelta(seconds=3),
                                                       limit_stop=True,
                                                       neg_lim_max_time=timedelta(seconds=.75), # These should be > in_pos_max_time
                                                       pos_lim_max_time=timedelta(seconds=.75),
                                                       in_pos=in_pos,
                                                       in_pos_max_time=timedelta(seconds=2),
                                                       debug_mode=debug_mode)
            if debug_mode: print("monitor_move result: {0} {1}".format(result['monitor_move'],str(datetime.now(pytz.reference.LocalTimezone()))))
            result['stop_code'] = avp_util.traverse_tree(result['monitor_move'],desired_key='stop_code') #WHY DID WE STOP?
            result['stop_desc'] = avp_util.traverse_tree(result['monitor_move'],desired_key='stop_desc') #WHY DID WE STOP?
            if self.sonde.instr_connected is True:
                try:
                    self.logger.debug("Stopped at {0}m due to {1} ({2})".format(self.sonde.depth_m.value,result['stop_desc'],result['stop_code']))
                except:
                    self.logger.debug("Stopped at {0}m due to {1} ({2})".format('?',result['stop_desc'],result['stop_code']))
        result['_winch_move_finish'] = self._winch_move_finish(stop_code=result.get('stop_code','unknown_code'),debug_mode=debug_mode)
        if debug_mode: print("move_to_absolute _winch_move_finish result: {0} {1}".format(result['_winch_move_finish'],str(datetime.now(pytz.reference.LocalTimezone()))))
        return result #this will tell us why it stopped
    def move_to_relative(self,distance,speedlimit=None,amps_limit=None,in_pos=False,units='clicks',stop_funct=None,stop_args=None,
                         limit_stop=True,in_water=None,max_stopped=timedelta(seconds=30),max_zero_v=timedelta(seconds=3),
                         neg_lim_max_time=timedelta(seconds=1), pos_lim_max_time=timedelta(seconds=1),**kwargs):
        '''
        Moves winch to a relative position.
        
        Arguments:
            distance   -- Distance to move. Positive numbers are down.
            speedlimit -- Velocity limit to impose on the PID controller. Defaults to self.mm3.DEFAULT_SPEED.
            amps_limit -- Current limit to impose on the PID controller.
            stop_funct -- Optional function to evaluate. Typically looks for depth or conductivity.
            stop_args  -- Arguments for stop_funct.
            units      -- The units to use for distance. Must be in ['meters','clicks'].
            limit_stop -- Stop if limit switch is triggered. Defaults to True
            max_stopped -- Will timeout if no updates in this period.
            max_zero_v -- Will timeout if winch stops moving for this long.
            neg_lim_max_time -- Allows faster timeouts on photo switch trip
            pos_lim_max_time -- Allows faster timeouts on tension switch trip
        Keyword Arguments:
            debug_mode --
        Returns:
            Dictionary of results.

        '''
        debug_mode = kwargs.get('debug_mode',False)
        if speedlimit is None:
            speedlimit = self.mm3.DEFAULT_SPEED
        #if stop_funct is None or stop_funct.__class__ == None.__class__:
        #    stop_funct = null
        #    stop_args = []
        #elif debug_mode: print "move_to_relative Using stop_function {0} with arguments {1}".format(stop_funct.func_name,stop_args)
        result = {}
        direction = 'unknown'
        up = False
        if distance > 0 :
            direction = 'down'
        elif distance < 0:
            direction = 'up'
            up = True
        message = "Moving {0}".format(direction)
        if units == 'meters':
            message += " {0} meters".format(abs(distance))
            distance = self.meters_to_clicks(distance) # move_to_relative needs clicks
            message += " ({0} clicks)".format(abs(distance))
        elif units == 'clicks':
            message += " {0} clicks".format(abs(distance))
        else:
            self.logger.error("Error: unknown units {0}.".format(units))
            return 0
        message += " at {0}".format(speedlimit)
        self.move_warnings()
        self.logger.info(message)
        print("---------- Press ANY key to stop. ----------")
        if amps_limit is None:
            result['amps_limit'] = self.amps_for_speed(speedlimit,
                                                       up=up,
                                                       in_water=in_water,
                                                       debug_mode=debug_mode)
            amps_limit = result['amps_limit'].pop('result',self.mm3.AMPS_LIMIT)
        self._winch_move_setup(**kwargs) # returns nothing
        # Now check for limit switches which may cause problems.
        if self.mm3.pos_limit_switch.value == 1 and direction is 'down':
            self.logger.warning('Attempting to lower winch while tension switch is {0}'.format(self.mm3.pos_limit_switch.value))
        elif self.mm3.neg_limit_switch.value == 1 and direction is 'up':
            self.logger.warning('Attempting to raise winch while photo switch is {0}'.format(self.mm3.neg_limit_switch.value))
        print(("1: SPEED IS {0}".format(speedlimit)))
        result['move_to_relative'] = self.mm3.move_to_relative(distance,
                                                               speedlimit=speedlimit,
                                                               amps_limit=amps_limit,
                                                               limit_stop=limit_stop,
                                                               **kwargs)
        try: # See if there was an error
            self.logger.error(result['move_to_relative']['error']['message'])
            result['monitor_move'] = "error on startup"
        except KeyError: #This is the NO error condition
            if debug_mode: print("move_to_relative result: {0}".format(result))
            result['monitor_move'] = self.monitor_move(in_pos=in_pos,
                                                       in_pos_max_time=timedelta(seconds=2),
                                                       stop_funct=stop_funct,
                                                       stop_args=stop_args,
                                                       limit_stop=limit_stop,
                                                       max_stopped=max_stopped, # default
                                                       max_zero_v=max_zero_v, #default
                                                       neg_lim_max_time=neg_lim_max_time, #default
                                                       pos_lim_max_time=pos_lim_max_time, #default
                                                       debug_mode=debug_mode)
            result['stop_code'] = avp_util.traverse_tree(result['monitor_move'],desired_key='stop_code') #WHY DID WE STOP?
            result['stop_desc'] = avp_util.traverse_tree(result['monitor_move'],desired_key='stop_desc') #WHY DID WE STOP?
            try:
                depth_m = self.sonde.depth_m.value
            except AttributeError:
                depth_m = '?'
            self.logger.debug("Stopped at {0}m due to {1} ({2})".format(depth_m,result['stop_desc'],result['stop_code']))
            if debug_mode: print("monitor_move result: {0} {1}".format(result['monitor_move'],str(datetime.now(pytz.reference.LocalTimezone()))))
        result['_winch_move_finish'] = self._winch_move_finish(stop_code=result.get('stop_code','unknown_code'),**kwargs)
        if debug_mode: print("avp_winch.move_to_relative._winch_move_finish result: {0} {1}".format(result['_winch_move_finish'],str(datetime.now(pytz.reference.LocalTimezone()))))
        return result
    def move_at_speed(self,motorspeed,direction=None,amps_limit=None,in_water=None,
                      stop_funct=None,stop_args=None,limit_stop=True,in_pos=True,**kwargs):
        '''
        Moves winch at speed. Use is discouraged due to lack of built in stop condition.
        
        Arguments:
            motorspeed is the speed to move at. Integer >= 0
        Keyword arguments:
            direction  -- Direction to move winch in ['up','down']
            debug_mode --
            speedlimit -- Velocity limit to impose on the PID controller.
            amps_limit -- Amperage limit to impose on the PID controller.
            in_water   --
            stop_funct --
            stop_args  --
            limit_stop --
            max_stopped --
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        result = {}
        if direction == 'up':
            motorspeed = abs(int(motorspeed)) * -1
            up = True
        elif direction == 'down':
            motorspeed = abs(int(motorspeed))
            up = False
        else:
            self.logger.error("Error in move_at: {0} at {1} is an invalid command".format(direction,motorspeed))
            return {'Error':'error'}
        self.move_warnings()
        self.logger.info("Moving {0} at speed {1}.".format(direction, motorspeed))
        print("---------- Press ANY key to stop. ----------")
        if amps_limit is None:
            result['amps_limit'] = self.amps_for_speed(motorspeed,
                                                       up=up,
                                                       in_water=in_water,
                                                       debug_mode=debug_mode)
            amps_limit = result['amps_limit'].pop('result',self.mm3.AMPS_LIMIT)
        self._winch_move_setup(debug_mode=debug_mode,**kwargs) # returns nothing
        result['move_at_speed'] = self.mm3.move_at_speed(motorspeed,
                                                         direction=direction,
                                                         amps_limit=amps_limit,
                                                         debug_mode=debug_mode,**kwargs)
        try:
            self.logger.error(result['move_at_speed']['error']['message'])
            result['monitor_move'] = "error on startup"
        except KeyError:
            if debug_mode: print(("move_at_speed result: {0}".format(result['move_at_speed'])))
            result['monitor_move'] = self.monitor_move(in_pos=in_pos,
                                                       in_pos_max_time=timedelta(seconds=2),
                                                       stop_funct=stop_funct,
                                                       stop_args=stop_args,
                                                       limit_stop=limit_stop,
                                                       #max_stopped=max_stopped, # default
                                                       max_zero_v=timedelta(seconds=10),
                                                       #neg_lim_max_time=neg_lim_max_time, #default
                                                       #pos_lim_max_time=pos_lim_max_time, #default
                                                       debug_mode=debug_mode,
                                                       **kwargs)
            result['stop_code'] = avp_util.traverse_tree(result['monitor_move'],desired_key='stop_code') #WHY DID WE STOP?
            result['stop_desc'] = avp_util.traverse_tree(result['monitor_move'],desired_key='stop_desc') #WHY DID WE STOP?
            try:
                depth_m = self.sonde.depth_m.value
            except AttributeError:
                depth_m = '?'
            self.logger.debug("Stopped at {0}m due to {1} ({2})".format(depth_m,result['stop_desc'],result['stop_code']))
            if debug_mode: print("monitor_result: {0}".format(result['monitor_move']))
        result['_winch_move_finish'] = self._winch_move_finish(stop_code=result.get('stop_code','unknown_code'),debug_mode=debug_mode,**kwargs)
        if debug_mode: print("move_at_speed _winch_move_finish result: {0} {1}".format(result['_winch_move_finish'],str(datetime.now(pytz.reference.LocalTimezone()))))
        return result #this will tell us why it stopped
    def move_to_depth(self,desired_depth,speedlimit=None,amps_limit=None,in_pos=False,limit_stop=True,max_stopped=timedelta(seconds=10),
                         max_zero_v=timedelta(seconds=3),neg_lim_max_time=timedelta(seconds=1), pos_lim_max_time=timedelta(seconds=1),**kwargs):
        '''
        This will attempt to move to a desired depth
        
        Arguments:
            desired_depth   -- Depth to move to
            speedlimit -- Velocity limit to impose on the PID controller. Defaults to self.mm3.DEFAULT_SPEED.
            amps_limit -- Current limit to impose on the PID controller.
            limit_stop -- Stop if limit switch is triggered. Defaults to True
            max_stopped -- Will timout if no updates in this period. 
            max_zero_v -- Will timeout if winch stops moving for this long.
            neg_lim_max_time -- Allows faster timeouts on photo switch trip
            pos_lim_max_time -- Allows faster timeouts on tension switch trip
        Keyword Arguments:
            debug_mode --
        '''
        debug_mode = kwargs.get('debug_mode',False)
        result = {}
        if self.sonde.instr_connected is False:
            print("sonde not connected. Aborting move_to_depth")
            return result
        if desired_depth <= 0: # CHECK IF NUMBER IS TOO BIG OR NEGATIVE
            self.logger.info("Requested depth {0} must be > 0 meters".format(desired_depth))
            return result
        if desired_depth > self.MAX_CAST_DEPTH:
            self.logger.info("Requested depth {0} must be <= {1} meters ".format(desired_depth,self.MAX_CAST_DEPTH))
            desired_depth = self.MAX_CAST_DEPTH
        # Check current depth
        if self.sonde.sampling.value != True: # Is sonde data current?
            self.logger.debug('move_to_depth starting sonde data sampling.({0})'.format(self.sonde.sampling.value))
            result['sonde.start_sampling'] = self.sonde.start_sampling(**kwargs)
            if result['sonde.start_sampling'] == 'ok':
                sleep(1)
            else:
                print(result['sonde.start_sampling'])
                return result
        # Up or down? # We should be subscribed, so...
        if not self.sonde.depth_m.subscribed:
            self.sonde.get_value(['depth_m'])
        # Estimate distance
        position_change = abs(desired_depth - self.sonde.depth_m.value)
        distance = self.meters_to_clicks(position_change)
        if self.sonde.depth_m.value < desired_depth:
            direction = 'down'
            raising = 0
            if self.sonde.depth_m.value <= self.sonde.INWATER_DEPTH:
                self.logger.info( "WARNING: Sonde is at or above waterline so move to depth may be short.")
        elif self.sonde.depth_m.value > desired_depth:
            direction = 'up'
            distance *= -1
            raising = 1
        else:
            print("current depth {0} matches desired depth {1}".format(self.sonde.depth_m.value,desired_depth))
            return result
        # Now move
        self.move_warnings()
        self.logger.info("Moving {0} {1} meters to {2}".format(direction,position_change,desired_depth))
        result['self.move_to_relative'] = self.move_to_relative(distance,
                                                                speedlimit=speedlimit,
                                                                amps_limit=amps_limit,
                                                                stop_funct=self.at_depth,# Stop at desired_depth
                                                                stop_args=[raising,desired_depth],
                                                                in_pos=in_pos,
                                                                limit_stop=limit_stop,
                                                                max_stopped=max_stopped,
                                                                max_zero_v=max_zero_v,
                                                                neg_lim_max_time=neg_lim_max_time,
                                                                pos_lim_max_time=pos_lim_max_time,
                                                                debug_mode=debug_mode)
        return result
    def calibration(self,do_WL=True,end_pos=0,**kwargs):
        '''
            This function will attempt fo calibrate both the sonde and the mm3 with the following procedure:
            Raise until photo-eye trips.
                Make sure we are really at the top (conductivity)
                Set position to 0
                Calibrate sonde pressure
            Lower to Conductivity Water Line (CWL)
                Are we near self.wl_position?
                If so, record self.wl_cond_position.
            Lower to Pressure Water Line (PWL)
                Are we near self.wl_position?
                If so, record self.wl_press_position.
            Lower .5 meters
                Record conductivity to self.sonde.inwater_cond
            Park.
            Backup old avp.ini
            Record changes in database.
            Write new values to avp.ini where appropriate.
        '''
        debug_mode = kwargs.get('debug_mode',False)
        #debug_mode = True
        result = {}
        fatal_faults = ['pos_limit_switch','temp_fault','kbhit','ipc_conn']
        park_step = -1 * self.CLICKS_PER_REVOLUTION #One drum revolution.
        MAX_ITERS = 10
        MAX_STOPPED = 2
        print("Raise until photo-eye trips. ---------------------------------------------------")
        park_location = int(min(self.mm3.position.value - park_step,park_step))
        print("parking to {0}".format(park_location))
        result['park(park_location)'] = self.park(park_location=park_location,
                                                  speedlimit=self.SLOW_SPEED,
                                                  max_stopped=timedelta(seconds=3),
                                                  debug_mode=debug_mode)
        result['stop_code'] = avp_util.traverse_tree(result['park(park_location)'],desired_key='stop_code') #WHY DID WE STOP?
        if result['stop_code'] in fatal_faults: #Make sure it didn't go badly.
            self.logger.critical("calibration Fault {0} while raising to {1} position. Aborting calibration".format(result['stop_code'],park_location))
            return result
        iters = 0
        while self.mm3.neg_limit_switch.value is 0: # If we didn't trip the upper  switch, raise some more
            print("Not at top, raising another {0}".format(abs(park_step)))
            result['move_to_relative.{0}'.format(iters)] = self.move_to_relative(park_step,
                                                                                 speedlimit=self.SLOW_SPEED,
                                                                                 max_stopped=timedelta(seconds=MAX_STOPPED),
                                                                                 in_water=False, # probably
                                                                                 debug_mode=debug_mode)
            result['stop_code'] = avp_util.traverse_tree(result['move_to_relative.{0}'.format(iters)],desired_key='stop_code') #WHY DID WE STOP?
            if result['stop_code'] in fatal_faults: #Make sure it didn't go badly.
                self.logger.critical("Hardware Fault {0} while raising to neg_limit_switch. Aborting calibration".format(result['stop_code']))
                return result
            try:
                print("Stopped at {0} due to {1}".format(self.sonde.depth_m.value,result['stop_code']))
            except AttributeError:
                pass # Sonde probably not connected
            iters += 1
            if iters > MAX_ITERS:
                print("Aborting due to too many raise attempts. Please raise sonde and try again")
                return result
        # This duplication could probably be cleaned up logically
        if self.sonde.instr_connected is False:
            print("sonde not connected, aborting the rest of the calibration procedure")
            self.logger.info("Storing position 0 to mm3's EEPROM. Position error of {0}".format(self.mm3.position.value))
            result['store_position'] = self.mm3.store_position(position=0,debug_mode=debug_mode) # Write position to EEPROM
            return result
        if self.sonde.in_water(instrumnet='any',debug_mode=debug_mode)[0] is False:
            self.logger.info("Storing position 0 to mm3's EEPROM. Position error of {0}".format(self.mm3.position.value))
            result['store_position'] = self.mm3.store_position(position=0,debug_mode=debug_mode) # Write position to EEPROM
            print("   Calibrating sonde pressure to 0.000")
            result['calibrate_pressure'] = self.sonde.calibrate_pressure(check_instruments=False,**kwargs)
        else:
            # Can't be sure what's going on. Log error
            self.logger.warning("Sonde in water? Failed to calibrate sonde position due to conductivity or pressure values.")
            return result
        if do_WL is True:
            print("Lower to Conductivity Water Line (CWL). ----------------------------------------")
            location = self.wl_cond_position + abs(park_step)
            result['move_to_absolute(CWL)'] = self.move_to_absolute(location,
                                                                    speedlimit=self.SLOW_SPEED,
                                                                    max_stopped=timedelta(seconds=MAX_STOPPED),
                                                                    in_water=False,
                                                                    stop_funct=self.any_wl,
                                                                    stop_args=[0],
                                                                    **kwargs)
            result['stop_code'] = avp_util.traverse_tree(result['move_to_absolute(CWL)'],desired_key='stop_code') #WHY DID WE STOP?
            update_comment = "Updated by calibration procedure on {0}".format(datetime.now(pytz.reference.LocalTimezone()).strftime('%Y-%m-%d %H:%M:%S'))
            if result['stop_code'] == 'stop_funct':
                self.mm3.config['winch']['wl_cond_position'] = self.mm3.position.value
                self.mm3.config['winch'].inline_comments['wl_cond_position'] = update_comment
                self.logger.info("Replacing [winch][wl_cond_position] {0} with {1} in {2}"
                    .format(self.wl_cond_position, self.mm3.config['winch']['wl_cond_position'], self.mm3.config.filename))
            else:
                print("No wl_cond_position calibration due to stop_code:{0} not 'stop_funct'".format(result['stop_code']))
            print("Lower to Pressure Water Line (PWL). --------------------------------------------")
            location = max(self.wl_press_position,self.mm3.position.value) + abs(park_step)
            result['move_to_absolute(PWL)'] = self.move_to_absolute(location,
                                                                    speedlimit=self.SLOW_SPEED,
                                                                    max_stopped=timedelta(seconds=MAX_STOPPED),
                                                                    in_water=False,
                                                                    stop_funct=self.press_wl,
                                                                    stop_args=[0],
                                                                    **kwargs)
            result['stop_code'] = avp_util.traverse_tree(result['move_to_absolute(PWL)'],desired_key='stop_code') #WHY DID WE STOP?
            if result['stop_code'] == 'stop_funct':
                self.mm3.config['winch']['wl_press_position'] = self.mm3.position.value
                self.mm3.config['winch'].inline_comments['wl_press_position'] = update_comment
                self.logger.info("Replacing [winch][wl_press_position] {0} with {1} in {2}"
                    .format(self.wl_press_position, self.mm3.config['winch']['wl_press_position'], self.mm3.config.filename))
                self.mm3.config['winch']['wl_position'] = self.mm3.position.value
                self.mm3.config['winch'].inline_comments['wl_position'] = update_comment
                self.logger.info("Replacing [winch][wl_position] {0} with {1} in {2}"
                    .format(self.wl_position, self.mm3.config['winch']['wl_position'], self.mm3.config.filename))
            else:
                print("No wl_press_position calibration due to stop_code:{0} not 'stop_funct'".format(result['stop_code']))
            result['config.write'] = self.mm3.config.write()
            self.wl_cond_position = int(self.mm3.config['winch']['wl_cond_position'])
            self.wl_press_position = int(self.mm3.config['winch']['wl_press_position'])
            self.wl_position = int(self.mm3.config['winch']['wl_position'])
            print('Done with calibration, parking to {0}.'.format(end_pos))
            result['park(park_0)'] = self.park(park_location=end_pos,
                                               speedlimit=self.SLOW_SPEED,
                                               max_stopped=timedelta(seconds=MAX_STOPPED),
                                               **kwargs)
            result['stop_desc'] = avp_util.traverse_tree(result['park(park_location)'],desired_key='stop_desc') #WHY DID WE STOP?
            print("Stopped at {0} due to {1}".format(self.sonde.depth_m.value,result['stop_code']))
        print('DONE ---------------------------------------------------------------------------')
        return result
    def park(self,park_location=0,speedlimit=None,get_surface_cond=False,in_pos=False,**kwargs):
        '''
        Get sonde back to park position in the tube
        We want to be careful when pulling the sonde in to the tube, to go 
        slowly so as not to stress the sonde bail or the lifting line. This is why we slow down at 
        self.SLOWDOWN_POSITION. While we are there, we can check conductivity.
        
        kwargs are passed to move_to_absolute()
        '''
        debug_mode = kwargs.get('debug_mode',False)
        result = {}
        self.logger.info('Park to position {0} from {1}.'.format(park_location,self.mm3.position.value))
        if self.sonde.instr_connected is False:
            get_surface_cond = False
        if self.mm3.position.value > self.SLOWDOWN_POSITION: # We go fast if we are deep
            org_speed = speedlimit
            if speedlimit is None: # We can override default parking speeds.
                speedlimit = self.FAST_SPEED
            else:
                speedlimit = int(speedlimit)
            # Move to position just before any portion of the bail touches the tube.
            # Stop if waterline detected, this means we have gone much too far.
            result['winch.move_to_absolute(fast)'] = self.move_to_absolute(location=self.SLOWDOWN_POSITION,
                                                                    speedlimit=speedlimit,
                                                                    amps_limit=None, # Use default
                                                                    in_water=True,   # These are passed on to lower levels.
                                                                    in_pos=in_pos,
                                                                    stop_funct=self.any_wl,
                                                                    stop_args=[1], # Moving up
                                                                    **kwargs)
            speedlimit = org_speed # Restore old speed setting
        if get_surface_cond is True: # If flag is set, record conductivity
            sonde_in_water,result['sonde.in_water'] = self.sonde.in_water(instrument='all')
            if sonde_in_water is True:
                if hasattr(self.sonde, 'spcond_mScm'):
                    conductivity = self.sonde.spcond_mScm.value
                    cond_units = self.sonde.spcond_mScm.units
                if hasattr(self.sonde, 'spcond_uScm'):
                    conductivity = self.sonde.spcond_uScm.value
                    cond_units = self.sonde.spcond_uScm.units
                result['surface_spcond'] = conductivity
                self.logger.info(
                    'paused at {0} {1} to get near-surface conductivity of {2} {3}'.format(
                        self.sonde.depth_m.value,
                        self.sonde.depth_m.units,
                        conductivity,
                        cond_units))
            else:
                self.logger.info('Pausing at slow-down point during park {0}.'.format(self.mm3.position.value))
                result['surface_spcond'] = None
        else:
            result['surface_spcond'] = None
        # Now the rest of the way slowly
        if speedlimit is None:
            speedlimit = self.SLOW_SPEED
        else:
            speedlimit = int(speedlimit)
        # Now move to park_location
        result['winch.move_to_absolute'] = self.move_to_absolute(location=park_location,
                                                                speedlimit=speedlimit,
                                                                amps_limit=None,
                                                                in_water=False,
                                                                in_pos=in_pos,
                                                                stop_funct=None,
                                                                stop_args=None,
                                                                debug_mode=debug_mode)
        # Now figure out why it stopped....
        if not self.mm3.in_position:
            # The limit switch probably tripped, check how far our position s away from 0 and generate an error if too far.
            # If we're close, don't do anything.
            if self.mm3.neg_limit_switch: # If we tripped the photo eye limit switch....
                # make sure we're really
                if self.mm3.position < (self.ZERO_POS_MAX_ERROR*2):
                    if self.sonde.instr_connected is False or self.sonde.conductivity < self.sonde.inwater_cond:
                        self.mm3.position = 0 # Reset our position
        return result
    def monitor_move(self,max_stopped=timedelta(seconds=30),
                    stop_funct=None,stop_args=None,max_zero_v=timedelta(seconds=3),
                    limit_stop=True,neg_lim_max_time=timedelta(seconds=1),
                    pos_lim_max_time=timedelta(seconds=1),in_pos=False,
                    in_pos_max_time=timedelta(seconds=1.5),ipc_poll=True,**kwargs):
        '''
        This function monitors values from the sonde and motor controller.
        
        Keyword Arguments:
            max_stopped      -- Datetime.timedelta with update timeout. Defaults to 30 seconds.
            stop_funct       -- Optional function to evaluate. Typically looks for depth or conductivity.
            stop_args        -- Arguments for stop_funct.
            max_zero_v       -- Datetime.timedelta with velocity == 0 or no position change timeout . Defaults to 3 seconds.
            limit_stop       -- Exit monitoring loop when a limit switch is tripped for long enough? Defaults to True.
            neg_lim_max_time -- Datetime.timedelta with negative limit switch == 1 timeout. Defaults to 1 second.
            pos_lim_max_time -- Datetime.timedelta with positive limit switch == 1 timeout. Defaults to 1 second.
            in_pos           -- Monitor the in_position flag and stop when == 1 long enough.
            in_pos_max_time  -- Datetime.timedelta with in_position == 1 timeout. Defaults to 1 second.
            ipc_poll         -- Poll ipc_conn database for external notifications. False only for passive monitoring
            debug_mode       -- 
            
        The monitoring loop will exit for a variety of reasons including:
            Detection via a database that an external program has stopped the motor.
            Keyboard press.
            No feedback from sonde or mm3 for a given amount of time.
        Optional resons include:
            Evaluation of a passed in function stop_funct()
            Limit switch trip for more than a certain amount of time.
            Motor controller is in_pos for more than a certain amount of time.
        Diagnostic output is printed.
        '''
        debug_mode = kwargs.get('debug_mode',False)
        if stop_funct is None:
            stop_funct = null
            stop_args = []
        if stop_funct is not null:
            self.logger.debug("monitor_move using stop_function {0} with arguments {1}".format(stop_funct.__name__,stop_args))
        print((self.feedback_header(show_legend=True,top=True)))
        # The flags may have been zeroed in _winch_move_setup(), so lets force a new value for them.
        update_list = []
        if limit_stop is True:
            if self.mm3.pos_limit_switch.subscribed is False:
                update_list.append('pos_limit_switch')
            if self.mm3.neg_limit_switch.subscribed is False:
                update_list.append('neg_limit_switch')
        if in_pos and self.mm3.in_position.subscribed is False:
                update_list.append('in_position')
        if update_list:
            initial_update_thread = threading.Thread(target=self.mm3.get_value,
                                                     name='Mon Move Init Update',
                                                     args=[update_list])
            if (debug_mode): print(("Starting get_value thread for {0}".format(update_list)))
            initial_update_thread.start()
        same_pos_time = stop_time = zero_v_time = lim_sw_on_time = in_pos_on_time = datetime.now(pytz.reference.LocalTimezone()) # Keep time of certain events
        old_ts = datetime(2000,0o1,0o1).replace(tzinfo=pytz.reference.LocalTimezone()) # Way in the past so it fails the first comparison
        # Some database stuff
        select_columns = ('value',)
        where_condition = {'broker':self.mm3.BROKER_NAME,'param':'stop_reason'}
        # Other variables we will need in our loop
        stop_reason = {'stop_code':None,'stop_desc':None} # If we have a reason, there will be two items. The stop_code, and a stop_desc.
        iterations = 0 # times through the while loop
        stop_funct_time = datetime.now() + timedelta(weeks=2) # If this is less than now, stop. As a default we use a time way in the future
        max_stop_funct_time = timedelta(seconds = 1) # Amount of time stop_function must remain true
        set_curses_term() # This has to do with detecting key presses
        last_position = self.mm3.position.value
        desired_position = self.mm3.desired_position.value # may change, we want original value
        while True: #This loop runs until the motor stops for some reason and we break out of it.
            if stop_reason['stop_code']: #If there is a reason.....
                if debug_mode: print("BREAKING: stop_reason={0}".format(stop_reason['stop_desc']))
                # Update database as to why we are stopping
                set_values={'value':'{0}'.format(stop_reason['stop_code']),'time':datetime.now(pytz.reference.LocalTimezone())}
                self.mm3.ipc_db.update(set_values,
                                       where_condition=where_condition,
                                       where_join='AND',
                                       where_oper='=',
                                       debug_mode=debug_mode) #NEED TO ADD TIME FIELD
                self.stop_reason = stop_reason['stop_code']
                break
            # Evaluate any stop functions (waterline, depth, etc) THIS COULD BE A CALLBACK
            try:
                stop_result = stop_funct(*stop_args) 
            except AttributeError: # This might happen if our sonde isn't connected...
                stop_result = False
            if stop_result: # This may be a passed function to be evaluated.
                if datetime.now() + timedelta(weeks=1) < stop_funct_time:
                    stop_funct_time = datetime.now() # Start the timer
                if stop_funct_time < datetime.now() - max_stop_funct_time:
                    stop_reason['stop_code'] = 'stop_funct'.format(stop_result)
                    stop_reason['stop_desc'] = 'Stop Function {0}'.format(stop_result)
                    continue
            else:
                stop_funct_time = datetime.now() + timedelta(weeks=2)
            # Look for external stop notifications, usually due to callbacks
            if ipc_poll is True: # And it usually is...
                try: 
                    poll_result = self.mm3.ipc_db.poll(debug_mode=debug_mode)
                    if poll_result:
                        if debug_mode: print("monitor_move poll result {0}".format(poll_result))
                        try:
                            select_result = self.mm3.ipc_db.select(select_columns,
                                                                   fetch_type='one',
                                                                   where_condition=where_condition,
                                                                   **kwargs)
                            select_result = select_result[0]
                            if select_result:
                                self.stop_reason = select_result
                                stop_reason['stop_code'] = 'ipc_conn'
                                stop_reason['stop_desc'] = 'External notification {0}: {1}'.format(poll_result,select_result)
                                break # NOT continue
                            else:
                                try:
                                    self.mm3.ipc_db.poll(debug_mode=debug_mode)
                                except Exception:
                                    pass
                        except Exception as e:
                            print(("Exception in Winch.monitor_move",e))
                            print(select_columns)
                            print(select_result)
                            print(kwargs)
                except Exception as e:
                    self.logger.error("poll failure {0}".format(e))
                    pass
            if kbhit(): # Look for key press or error condition
                stop_reason['stop_code'] = 'kbhit'
                stop_reason['stop_desc'] = 'Keyboard Press'
                continue
            if hasattr(self.aio, 'relay_5V') is True:
                if self.aio.relay_5V.value == self.aio.RELAY_OFF: # No power to 5V bus. Bad things happen to winch when we loose power to the encoder.
                    stop_reason['stop_code'] = 'relay_5V'
                    stop_reason['stop_desc'] = 'No 5V power to encoder'
                    self.logger.info('No 5V power to encoder')
                    continue
            if datetime.now(pytz.reference.LocalTimezone()) >= stop_time + max_stopped:
                stop_reason['stop_code'] = 'max_stopped'
                stop_reason['stop_desc'] = 'No updates for {0} sec. (>{1})'.format(datetime.now(pytz.reference.LocalTimezone()) - stop_time,max_stopped)
            if stop_reason['stop_code']: continue # Skip this part if we are about to exit
            # Check timestamp to see if we should print out another line of _feedback.
            new_ts = self._newest_ts() # The most recent mm3 or sonde sample_time.
            if new_ts > old_ts: # we have new data from the mm3, so  do some checks
                old_ts = new_ts
                print(self._feedback(new_ts))
                iterations += 1 # Keep track of how many lines we've printed out.
                stop_time = datetime.now(pytz.reference.LocalTimezone()) #Keeps track of time between updates
                # First check flag dependent conditions (limit_stop,in_pos THESE COULD BE CALLBACKS
                if in_pos is True:
                    if self.mm3.in_position.value == 1: #If we are in position
                        time_in_position = datetime.now(pytz.reference.LocalTimezone()) - in_pos_on_time
                        if time_in_position >= in_pos_max_time: # See if we have been in_position long enough to stop
                            stop_reason['stop_code'] = 'in_position'
                            stop_reason['stop_desc'] = 'in_position {0:.1} sec'.format(avp_util.total_seconds(time_in_position))
                    else:
                        in_pos_on_time = datetime.now(pytz.reference.LocalTimezone())
                if limit_stop is True: #We don't want to exit due to a limit switch unless we are really stopped.
                    if (self.mm3.neg_limit_switch.value == 1 or self.mm3.pos_limit_switch.value == 1): #If we have a limit switch asserted...
                        if self.mm3.neg_limit_switch.value == 1 and self.mm3.velocity.value < 0: # Only if we are raising (velocity > 0)
                            neg_limit_time = datetime.now(pytz.reference.LocalTimezone()) - lim_sw_on_time
                            if  neg_limit_time >= neg_lim_max_time: # Has it been asserted long enough to stop
                                stop_reason['stop_code'] = 'neg_limit_switch'
                                stop_reason['stop_desc'] = 'Photo Eye {0}>{1}'.format(neg_limit_time,neg_lim_max_time)
                        if self.mm3.pos_limit_switch.value == 1 and self.mm3.velocity.value > 0: # Only if we are lowering (velocity > 0)
                            pos_limit_time =  datetime.now(pytz.reference.LocalTimezone()) - lim_sw_on_time
                            if pos_limit_time >= pos_lim_max_time:
                                stop_reason['stop_code'] = 'pos_limit_switch'
                                stop_reason['stop_desc'] = 'Tension switch {0}>{1}'.format(pos_limit_time,pos_lim_max_time)
                    else:
                        lim_sw_on_time = datetime.now(pytz.reference.LocalTimezone())
                # Now check operating conditions
                if abs(self.mm3.velocity.value) > self.mm3.MIN_SPEED: # Are we moving very slowly or not at all?
                    zero_v_time = datetime.now(pytz.reference.LocalTimezone()) #Keeps track of time between updates
                elif datetime.now(pytz.reference.LocalTimezone()) > zero_v_time + max_zero_v:
                    stop_reason['stop_code'] = 'max_zero_v'
                    stop_reason['stop_desc'] = 'Velocity == 0 for {0} sec. (>{1})'.format(
                                datetime.now(pytz.reference.LocalTimezone()) - zero_v_time,max_zero_v)
                if last_position != self.mm3.position.value: #We've moved
                    same_pos_time = datetime.now(pytz.reference.LocalTimezone()) # So reset datetime
                elif datetime.now(pytz.reference.LocalTimezone()) > same_pos_time + max_zero_v: # No position change and timed out
                    stop_reason['stop_code'] = 'max_no_pos_change'
                    stop_reason['stop_desc'] = 'Movement stopped for {0} sec. (>{1})'.format(
                                datetime.now(pytz.reference.LocalTimezone()) - same_pos_time,max_zero_v)
                if in_pos is True and iterations >= 20:
                    position_delta = abs(self.mm3.position.value - desired_position)
                    if position_delta <= self.POSITION_DB:
                        stop_reason['stop_code'] = 'in_position'
                        stop_reason['stop_desc'] = 'Position {0} within {1} of {2}'.format(
                                    self.mm3.position.value,self.POSITION_DB,desired_position)
            else: # no new values
                sleep(.05)  #Perhaps better as a select.select() or a trigger from _SubscritionHandler
        # Done with while loop
        print((self._feedback(self._newest_ts()))) # One last line of data...
        if iterations > 10:
            print((self.feedback_header(show_legend=True,top=False))) # And a final header if we've had enough interations
        set_normal_term() # This has to do with detecting key presses
        return stop_reason
    def get_stop_reason(self,**kwargs):
        ''' Get last stop_reason from database
        '''
        debug_mode = kwargs.get('debug_mode',False)
        select_columns = ('value',)
        where_condition = {'broker':self.mm3.BROKER_NAME,'param':'stop_reason'}
        select_result = None
        try:
            select_result = self.mm3.ipc_db.select(select_columns,
                                                   fetch_type='one',
                                                   where_condition=where_condition,
                                                   **kwargs)
            select_result = select_result[0]
            if select_result:
                self.stop_reason = select_result
        except Exception as e:
            self.logger.error("Exception in Winch.get_stop_reason() {e} ({col},{res},{kw}".format(
                        e=e,col=select_columns,res=select_result,kw=kwargs))
        return select_result
    def _winch_move_setup(self,limit_stop=False,in_pos=False,**kwargs):
        """
        Get the winch setup for the move before you start actually moving
        Clears all the flags (until next subscription update). Also prints feedback_header()
        
        Keyword Arguments:
            limit_stop -- Defaults to False.
            in_pos     -- Defaults to False.
        Returns:
            Nothing
        
        """
        debug_mode = kwargs.get('debug_mode',False)
        if limit_stop is True: # Need to look at this part closely
            self.mm3.neg_limit_switch._value = self.mm3.pos_limit_switch._value = 0 
        if in_pos is True:
            self.mm3.in_position._value = 0
        return
    def _winch_move_finish(self,stop_code='',**kwargs):
        '''
        Stops motor at end of winch move.
        
        Keyword arguments:
            stop_code  -- This is the reason the motor was stopped.
            debug_mode --
        '''
        debug_mode = kwargs.get('debug_mode',False)
        self.logger.debug( "Stopping motor:{0}".format(stop_code))
        result = {}
        result['mm3.stop'] = self.mm3.stop(check_defaults=False,debug_mode=debug_mode) #Stop motor
        if debug_mode: print("_winch_move_finish.stop : {0}".format(result['mm3.stop']))
        return result
    def feedback_header(self,show_legend=True,top=True,**kwargs):
        '''Generate the feedback header
        if Top is false, header lines are reversed
        '''
        #debug_mode = kwargs.get('debug_mode',False)
        header = "  Winch                            |Motor           |Sonde       |Sample Time\n    pos    trgt spd  PWM A B C D E |amps/ lim@volts |depth cond  |HH:mm:ss.ii"
        if show_legend is True:
            legend =  " A=InPos,B=NoRaise,C=NoLower, D=PWM Limited, E=Current@limit"
            CR = "\n"
            if top is True:
                header = legend + CR + header
            else:
                header = header + CR + legend
        return header
    def _feedback(self,new_ts):
        '''
        called whenever there is a position update.
        Returns a diagnostic string
        '''
        conductivity = "?"
        diagnostic = "{0:7}/{1:7}{2:4}{3:5}{4:2}{5:2}{6:2}{7:2}{8:2} ".format(
                    self.mm3.position.value,         
                    self.mm3.desired_position.value,
                    self.mm3.velocity.value,
                    self.mm3.pwm_out.value,
                    self.mm3.in_position.value,            #A
                    self.mm3.neg_limit_switch.value,       #B
                    self.mm3.pos_limit_switch.value,       #C
                    self.mm3.PWM_limited.value,            #D
                    self.mm3.current_limit.value)          #E
        try:
            depth_m = self.sonde.depth_m.value
        except AttributeError as e:
            depth_m = "?"
        try:
            if hasattr(self.sonde, 'spcond_mScm'): conductivity = self.sonde.spcond_mScm.value
            if hasattr(self.sonde, 'spcond_uScm'): conductivity = self.sonde.spcond_uScm.value
        except AttributeError as e:
            pass
        diagnostic += "|{0:4}/{1:4}@".format(self.mm3.amps.value,self.mm3.amps_limit.value)
        diagnostic += "{0:6}".format(str(float(self.aio.voltage_ADC.value) * self.aio.VOLTAGE_MULTIPLIER)[:5])
        diagnostic += "|{0:7}{1:7}".format(depth_m,conductivity)
        diagnostic += "|{0}.{1}".format(new_ts.strftime('%H:%M:%S'),new_ts.microsecond/10000) # Only print out hudredths of a second.
        return diagnostic

    # Here are the stop_check functions. They are passed in to move requests as a way of stopping the motor when certain conditions are met.
    def press_wl(self,raising):
        '''
        Checks for a change in waterline due to pressure
        raising=1 for raising and 0 for lowering
        '''
        return self._check_wl(raising,instrument='depth_m')
    def cond_wl(self,raising):
        '''
        Checks for a change in waterline due to conductivity
        raising=1 for raising and 0 for lowering
        '''
        instrument=None
        if hasattr(self.sonde, 'spcond_mScm'): instrument = 'spcond_mScm'
        if hasattr(self.sonde, 'spcond_uScm'): instrument = 'spcond_uScm'
        return self._check_wl(raising,instrument=instrument)
    def any_wl(self,raising):
        '''
        Checks for a change in waterline due to pressure OR conductivity
        raising=1 for raising and 0 for lowering
        '''
        return self._check_wl(raising,instrument='any')
    def all_wl(self,raising):
        '''
        Checks for a change in waterline due to pressure AND conductivity
        raising=1 for raising and 0 for lowering
        '''
        return self._check_wl(raising,instrument='all')
    def _check_wl(self,raising,instrument=None):
        lowering = not raising
        in_water,result = self.sonde.in_water(instrument=instrument)
        if in_water == True: #In water
            if lowering:
                return "Reached {0} waterline on descent: {1}{2}".format(instrument,in_water,result)
        elif in_water == False:
            if raising:
                return "Reached {0} waterline on ascent: {1} {2}".format(instrument,in_water,result)
        else:
            return "Could not determine waterline: {0}".format(result) 
        return
    def at_depth(self,raising,stop_depth):
        lowering = not raising
        if raising and self.sonde.depth_m.value <= stop_depth:
            return "Reached {0}({1}) on ascent".format(stop_depth,self.sonde.depth_m.value)
        if lowering and self.sonde.depth_m.value >= stop_depth:
            return "Reached {0}({1}) on descent".format(stop_depth,self.sonde.depth_m.value)
        return 0

    # Utility functions
    def meters_to_clicks(self,meters,**kwargs):
        clicks = int(meters * self.CLICKS_PER_METER)
        return clicks
    def clicks_to_meters(self,clicks,**kwargs):
        meters = float(clicks) / self.CLICKS_PER_METER
        return meters
    def get_amps_limits(self,config,**kwargs):
        '''
        Sets self.amp_lim dictionary using values in avp_ipc database.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        amps = {}
        default_amps = 3000
        config_wa = config.get('winch',{}).get('amps',{})
        try:
            for direction in ('up','down'):
                amps[direction] = {}
                for location in ('in','out'):
                    amps[direction][location] = {}
                    for speed in ('low','med','high'):
                        amps[direction][location][speed] =  int(config_wa.get(direction,{}).get(location,{}).get(speed,default_amps))
        except Exception as e:
            self.logger.error('Failed to set up {0}.amps from {1} ({2})'.format(self.__class__.__name__,config_wa,e))
            amps = {'error':e}
        if debug_mode: print("amps dictionary: {0}".format(amps))
        return amps
    def amps_for_speed(self,speed_input,up=True,in_water=None,**kwargs):
        '''
        Given a speed integer, direction in (up if it matches up with a speed from avp.ini (FAST_SPEED,MED_SPEED,SLOW_SPEED)
        '''
        debug_mode = kwargs.get('debug_mode',False)
        if in_water is None: # We need to figure it out
            in_water = True
            try:
                if up:
                    result = self.sonde.in_water(instrument='depth_m')
                    if debug_mode: print("depth_m result {0}".format(result))
                    if not result[0]:
                        in_water = False
                else:
                    if hasattr(self.sonde, 'spcond_mScm'): result = self.sonde.in_water(instrument='spcond_mScm')
                    #if hasattr(self.sonde, 'spcond_uScm'): result = self.sonde.in_water(instrument='spcond_uScm')
                    else: result = self.sonde.in_water(instrument='spcond_uScm')
                    if debug_mode: print("spcond_?Scm result {0}".format(result))
                    if not result[0]:
                        in_water = False
            except AttributeError:
                pass # May not have sonde comms.
        speed = int(speed_input)
        if speed == self.FAST_SPEED: speed_type = 'high'
        elif speed == self.MED_SPEED: speed_type = 'med'
        elif speed == self.SLOW_SPEED: speed_type = 'low'
        else:
            self.logger.debug("amps_for_speed(speed_input={0}) Couldn't match to pre-defined speeds {1}.".format(speed,(self.FAST_SPEED,self.MED_SPEED,self.SLOW_SPEED)))
            return {'error':'No match found to {0} in {1}'.format(speed,[self.FAST_SPEED,self.MED_SPEED,self.SLOW_SPEED])}
        if not in_water: in_str = 'out' # Default
        else: in_str = 'in'
        if not up: direction = 'down' # Default
        else: direction = 'up'
        try:
            amp_limit = int(self.amps[direction][in_str][speed_type])
            self.logger.debug("Looked up {3}ma limit for direction={0}, in_water={1}, speed = {2}.".format(direction,in_water,speed_type,amp_limit))
        except Exception as e:
            self.logger.error("({0}) in amps_for_speed looking up amps_limit from {1} with [{2}][{3}][{4}]".format(e,self.amps,direction,in_str,speed_type))
            return {'error':e}
        return {'result':amp_limit}
    def _newest_ts(self,**kwargs):
        """ Returns the latest timestamp.
        """
        try:
            return max(self.mm3.message_time.sample_time,self.sonde.message_time.sample_time)
        except AttributeError:
            return self.mm3.message_time.sample_time
    def move_warnings(self,**kwargs):
        """ Checks to see if there's anything we should be warned about.
        """
        if self.aio.reset_MM3.value == 0:
            self.logger.error("Trying to move winch when MM3 power is off.")
        if self.aio.limit_switch_enable.value == 0:
            self.logger.warning("Moving winch with limit switch disabled. ({0})".format(self.aio.limit_switch_enable.value))
        if self.aio.tension_switch_enable.value == 0:
            self.logger.warning("Moving winch with cable tension switch disabled. ({0})".format(self.aio.tension_switch_enable.value))
                                 
def null(*doesnt_matter,**anything):
    return 0
