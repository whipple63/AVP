#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        avp_sched.py
# Purpose:     Handles AVP cast scheduling
#
# Author:      neve
#
# Created:     02/24/2012
#-------------------------------------------------------------------------------

#Built in Modules
from __future__ import print_function
from datetime import datetime, timedelta
import logging
import socket
import sys
import threading
import time
import traceback
#Installed Modules
import pytz.reference 
#Custom Modules
import avp_db
import avp_cast
import avp_util

class AVPScheduleStatus(object):
    '''
    Provides a simple interface to see schedule status and to change it.
    
    use AVPScheduleStatus.state to get status and
    AVPScheduleStatus.state = <status> to set it.
    
    For pauses, use AVPScheduleStatus.resume_time to see when resumed.
    This class will not do the resume, that is done by AVPLauncher.
    '''
    VALID_SCHEDULE_STATES = ('off','on','paused')
    sched_where_condition = {'broker':'sched','param':'status'}
    cast_where_condition = {'broker':'cast','param':'cast_status'}
    select_columns = ('value','time',)
    def __init__(self,config,debug_mode=False):
        '''
        '''
        self.debug_mode = debug_mode
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        # Some database stuff
        IPC_TABLE = config.get('db',{}).get('IPC_TABLE','avp_ipc')
        self.ipc_db = avp_db.AvpDB(config,IPC_TABLE,polling=True,debug_mode=self.debug_mode)
        self.PAUSE_MINUTES = int(config.get('scheduler',{}).get('PAUSE_MINUTES',60))
        self._state = 'unknown'
        self._cast_status = 'unknown'
        self._sched_change_time = None
        self._resume_time = datetime.now(pytz.reference.LocalTimezone())
        self._get_state(first_run=True)
    def _get_state(self,first_run=False):
        poll_result = self.ipc_db.poll()
        if poll_result or self._state not in self.VALID_SCHEDULE_STATES:
            if poll_result and self.debug_mode: self.logger.debug("AVPScheduleStatus poll result {0}".format(poll_result))
            # First the schedule status and then the cast status
            try:
                db_state,db_time = self.ipc_db.select(self.select_columns,
                                                   fetch_type='one',
                                                   where_condition=self.sched_where_condition,
                                                   debug_mode=self.debug_mode)
            except Exception as e:
                db_state = ["Error in AVPScheduleStatus._get_state {0}".format(e),datetime.now(pytz.reference.LocalTimezone())]
                db_time = None
            if self.debug_mode: self.logger.debug("AVPScheduleStatus state: {0} time: {1}".format(db_state,db_time))
            if db_state in self.VALID_SCHEDULE_STATES:
                self._sched_change_time = db_time  # Time can change even if state doesn't (although unlikely)
                if db_state != self._state: # Schedule state change
                    if first_run is False:
                        self.logger.info("Schedule state changed from {0} to {1} at {2}".format(self._state,db_state,db_time))
                    if db_state == 'paused': 
                        try:
                            self._resume_time = self._sched_change_time + timedelta(minutes=self.PAUSE_MINUTES)
                        except Exception as e:
                            self._resume_time = datetime.now(pytz.reference.LocalTimezone()) + timedelta(minutes=self.PAUSE_MINUTES)
                        self.logger.info("Schedule paused until {0}".format(self._resume_time))
                self._state = db_state
            else:
                self._state = 'off' # Default to off.
                self.logger.warning("Schedule state {0} invalid. Setting schedule to {1}".format(db_state,self._state))
            # Now the cast_status
            try:
                select_result = self.ipc_db.select(self.select_columns,
                                                   fetch_type='one',
                                                   where_condition=self.cast_where_condition,
                                                   debug_mode=self.debug_mode)
                self._cast_status = select_result[0]
            except Exception as e:
                select_result = "Error in AVPScheduleStatus._get_state {0}".format(e)
            if self.debug_mode: self.logger.debug("AVPScheduleStatus select_result: {0}".format(select_result))
        return self._state
    def _set_state(self,set_value):
        if set_value in self.VALID_SCHEDULE_STATES:
            if set_value == 'on': # We want to turn on the schedule
                self._resume_time = datetime.now(pytz.reference.LocalTimezone())
                if self._state == 'off':
                    self.logger.debug("Turning on schedule.")
                elif self._state == 'on':
                    self.logger.debug("Schedule already on.")
                elif self._state == 'paused':
                    self.logger.debug("Resuming paused schedule.")
                else:
                    self.logger.warning("Turning off schedule from unknown state {0}.".format(self._state))
            elif set_value == 'off':# We want to turn off the schedule
                if self._state == 'on':
                    self.logger.debug("Turning off schedule.")
                elif self._state == 'off':
                    self.logger.debug("Schedule already off.")
                elif self._state == 'paused':
                    self.logger.debug("Turning off paused schedule.")
                else:
                    self.logger.warning("Turning off schedule from unknown state {0}.".format(self._state))
            elif set_value == 'paused':# We want to pause the schedule
                self._resume_time = datetime.now(pytz.reference.LocalTimezone()) + timedelta(minutes=self.PAUSE_MINUTES)
                if self._state == 'on':
                    self.logger.debug("Pausing schedule. Will resume at {0}.".format(self._resume_time))
                elif self._state == 'off':
                    self.logger.debug("Pausing stopped schedule. Will resume at {0}.".format(self._resume_time))
                elif self._state == 'paused':
                    self.logger.debug("Already paused. Will now resume at {0}.".format(self._resume_time))
                else:
                    self.logger.warning("Pausing schedule until {0} from unknown state {0}.".format(self._resume_time,self._state))
            else:
                pass
            dbset_values={'value':set_value,'time':datetime.now(pytz.reference.LocalTimezone())}
            self.ipc_db.update(dbset_values,
                               where_condition=self.sched_where_condition,
                               where_join='AND',where_oper='=',
                               debug_mode=self.debug_mode)
            print("Schedule state set to {0}.".format(set_value))
        else:
            print("{0} not a valid schedule state ({1}).".format(set_value,self.VALID_SCHEDULE_STATES))
    state = property(_get_state,_set_state)
    def _get_resume_time(self):
        return self._resume_time
    resume_time = property(_get_resume_time) #resume_time is a read-only variable
    def _get_cast_status(self):
        return self._cast_status
    cast_status = property(_get_cast_status)
    def _get_change_time(self):
        return self._sched_change_time 
    change_time = property(_get_change_time)

class AVPLauncher(threading.Thread):
    '''
    This class launches the scheduler thread and then monitors the pending dictionary.
    When there are events in the pending schedule to process, it does so.
    Events are not launched in their own threads so that only one cast can run at a time.
    In addition, if there are two casts scheduled for the same time (usually one is an ISCO cast),
    special measures will be specified
    
    Arguments:
    config          - ConfigObj object
    Keyword Arguments:
    read_only       - If True, casts will not actually be launched. For debugging
    program_name    -
    debug_mode      -
    
    Public methods:
    start   - Starts scheduler and then launcher
    shutdown    - shutsdown scheduler then Launcher.
    Public attributes
    schedule - dictionary of Scheduled casts which are ready to be acted upon
        action_status   = 'queued'  - This is the status when a record is placed in the schedule dictionary
                        = 'casting' - This is the status while casting
                        = 'done'    - This is the status after casting indicating the record can be removed.
    pending - dictionary of Scheduled casts which are more than a minute in the future
        sched_status    = None          - Default
                        = 'scheduled'   - The scheduler has placed this entry in the schedule dictionary
                        = 'processed'  - The launcher has processed the entry but not acted upon it
                        = 'acting'      - We are casting for this entry
    '''
    LAUNCHER_DELAY = 5 # Seconds after scheduler to check results
    def __init__(self,config,read_only=False,program_name=__name__,**kwargs):
        self.debug_mode = kwargs.get('debug_mode',False)
        if self.debug_mode: print("Launcher Initializing")
        self.config = config
        self.read_only = read_only # Don't actually launch any casts.
        self.program_name = program_name
        # Logging...
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        self.logger.debug("Instantiating")
        self.schedule_status = AVPScheduleStatus(self.config,debug_mode=self.debug_mode)
        # Instantiate Scheduler
        #  Note: Because schedule and pending are shared between two threads, all operations
        #        accessing them will require acquiring and releasing locks to insure thread safety.
        self.schedule_lock = threading.RLock()
        self.pending_lock = threading.RLock()
        self.Scheduler = _AVPSchedule(self.config,self.schedule_lock,self.pending_lock,self.schedule_status,debug_mode=self.debug_mode)
        self.schedule = self.Scheduler.schedule 
        self.pending = self.Scheduler.pending 
        self.running = False
        super(AVPLauncher,self).__init__()
        self.daemon = True
        self.name = self.__class__.__name__ # Set thread name to class name sinch there should only be one instance.
        self._state = 'unknown'
        self.PAUSE_MINUTES = int(self.config.get('scheduler',{}).get('PAUSE_MINUTES',60))
    def start(self,read_only=False,**kwargs):
        '''
        Starts Scheduler thread
        '''
        self.read_only=read_only
        self.Scheduler.start()
        self.running=True
        super(AVPLauncher,self).start() #threading.Thread.start(self)
    def run(self):
        '''
        '''
        self.logger.debug("Running {0:24}, {1:2} active threads.".format(self.name,threading.active_count()))
        castargs = {}
        needs_calibration = True # Right now we set this once, but we may want to check for problems during a cast and flag when we may need re-calibration.
        self.logger.debug("Creating Cast instance.")
        self.scheduled_cast = avp_cast.scheduled_cast(self.config,
                                                 program_name=self.program_name,
                                                 debug_mode=self.debug_mode)
        while self.running:
            if self._state != self.schedule_status.state:
                self.logger.info("Launcher state changed from {0} to {1}".format(self._state,self.schedule_status.state))
                self._state = self.schedule_status.state
            if self._state == 'on':
                if needs_calibration is True:
                    self.scheduled_cast.initial_calibration(debug_mode=self.debug_mode)
                    needs_calibration = False
                    continue
                castargs.clear()
                if self.debug_mode:
                    with self.pending_lock:
                        print("Pending\r\n    {0}".format(self.pending))
                    with self.schedule_lock:
                        print("Schedule\r\n    {0}".format(self.schedule))
                with self.schedule_lock:
                    actionable = dict((k,v) for k,v in self.schedule.items() if v['action_status'] is 'queued') # Ignore Dones.
                casts_to_do = len(actionable)
                casts_done = 0
                if casts_to_do > 0:
                    non_isco_casts = dict((k,v) for k,v in actionable.items() if v['isco_cast'] is False) # Also look to exclude done.
                    isco_casts = dict((k,v) for k,v in actionable.items() if v['isco_cast'] is True)
                    # Let's look at our non-ISCO casts. There should be one or less.
                    if len(non_isco_casts) == 0: # No non-ISCO casts
                        self.logger.debug("Launcher found no non-ISCO casts have been scheduled ({0} from {1})".format(non_isco_casts,actionable))
                        depth_entry = []
                        pass
                    elif len(non_isco_casts) == 1: # Single non-isco cast
                        self.logger.debug("Launcher found single non-ISCO cast has been scheduled ({0} from {1})".format(non_isco_casts,actionable))
                        entry_number = list(non_isco_casts.keys())[0]
                        depth_target = non_isco_casts[entry_number].get('depth_target',999.7)
                        depth_entry = [[depth_target,entry_number]] # This will be scheduled first
                        with self.pending_lock:
                            self.pending[entry_number]['sched_status'] = 'processed'
                    else:
                        # TOO MANY NON-ISCO CASTS!!!
                        self.logger.warning("TOO MANY NON_ISCO CASTS SCHEDULED, SKIPPING ({0} from {1})".format(non_isco_casts,actionable))
                        for entry_number in list(non_isco_casts.keys()):
                            with self.schedule_lock:
                                self.schedule[entry_number]['action_status'] = 'done' # Skip them
                        depth_entry = []
                    # Now look at ISCO casts     ------------------------------------------------------------------
                    # First we need to sort the ISCO casts by depth, deepest first.
                    isco_depth_entry = []
                    for entry_number,cast_info in list(isco_casts.items()):
                        isco_depth_entry.append([cast_info['depth_target'],entry_number])
                        with self.pending_lock:
                            self.pending[entry_number]['sched_status'] = 'processed'
                    # Should give us [[depth_A,entry_A],[depth_B],...]
                    isco_depth_entry.sort(reverse=True,key=Noneto99) # Sort it from deepest to shallowest...
                    print("DEPTH ENTRY: {1} + {0} = ".format(isco_depth_entry,depth_entry), end=' ')
                    # Now combine with non-ISCO cast if there is one.
                    if len(isco_depth_entry) > 0:
                        depth_entry.extend(isco_depth_entry) # Do the non-isco cast first
                    print(depth_entry)
                    #Now we can do our casts in the correct order...
                    try:
                        for depth_target,entry_number in depth_entry: 
                            if depth_target is None:
                                depth_target = 999.4
                            if casts_done == 0:
                                castargs['wipe'] = True # We wipe on the first action
                            else:
                                castargs['wipe'] = False # We wipe on the first action
                            if casts_to_do == 1:
                                castargs['park_pos'] = 'default' # We return to the top on the last cast
                            else:
                                castargs['park_pos'] = 'bottom' # Stay at the bottom when there are more casts to do
                            sched_list = actionable[entry_number].get('sched_list')
                            cast_cron = CronTime(date_list=sched_list)
                            cast_time = cast_cron.date_time
                            # Now some optional ones
                            if actionable[entry_number].get('lisst_cast',False):
                                castargs['lisst_cast'] = True
                            else:
                                castargs['lisst_cast'] = False
                            if actionable[entry_number].get('isco_cast',False):
                                castargs['isco_cast'] = True
                                castargs['pre_cal'] = False # Don't calibrate sonde depth at beginning of ISCO cast since sonde is probably in the water.
                                castargs['isco_bottle'] = actionable[entry_number].get('isco_bottle',None)
                                castargs['isco_volume'] = actionable[entry_number].get('isco_volume',None)
                            else:
                                castargs['isco_cast'] = False
                            if None not in list(castargs.values()):
                                self.do_cast(entry_number,depth_target,cast_time,castargs)
                            else:
                                self.logger.warning('Skipping cast entry {0} due to invalid parameters ({1})'
                                                    .format(entry_number,actionable[entry_number]))
                            castargs.clear()
                            casts_to_do -= 1
                            casts_done += 1
                    except Exception as e:
                        self.logger.error('Error in AVPLauncher.run: {0}'.format(e))
                        traceback.print_stack()
                        traceback.print_exc()
                    finally:
                        casts_to_do = 0
                        castargs.clear()
                else: 
                    print("Launcher found no casts queued at {0}.".format(datetime.now(pytz.reference.LocalTimezone())))
                actionable.clear() # Clear dictionary
                castargs.clear() # Clear dictionary
            elif self._state == 'paused':
                if self.schedule_status.resume_time <=  datetime.now(pytz.reference.LocalTimezone()):
                    self.logger.info('Resuming schedule after {0} min pause'.format(self.PAUSE_MINUTES))
                    self.schedule_status.state = 'on'
            elif self._state == 'off':
                pass
            else:
                self.logger.info('Invalid Launcher schedule state {0} ({1}).'.format(self._state,self.schedule_status.state))
                pass
            #Now sleep until LAUNCHER_DELAY seconds after the minute
            sleep_time = self.LAUNCHER_DELAY - datetime.now(pytz.reference.LocalTimezone()).second
            if sleep_time <= 0:
                sleep_time = 60 + sleep_time
            #print "Launcher sleeping for {0} sec.".format(sleep_time)
            time.sleep(sleep_time) # Once per minute, 10 after the minute
        print("Launcher thread no longer running")
    def do_cast(self,entry_number,depth_target,cast_time,castargs):
        try:
            #Cast
            self.logger.info("CASTING: to {0} at {1} with {2}".format(depth_target,cast_time,castargs))
            with self.schedule_lock:
                self.schedule[entry_number]['action_status'] = 'casting'
            with self.pending_lock:
                self.pending[entry_number]['sched_status'] = 'acting'
            if self.read_only is False:
                self.scheduled_cast.pre_config(depth_target,
                                          cast_time,
                                          debug_mode=self.debug_mode,
                                          load_config=True,
                                          **castargs)
                try:
                    cast_result = self.scheduled_cast.start()
                    cast_number = cast_result.get('cast_number','?')
                    self.logger.info("------------CAST {0} DONE------------------".format(cast_number))
                    self.logger.debug("There are now {0} threads.".format(threading.active_count()))
                    if cast_result.get('abort_cast',False):
                        print(avp_util.print_dict(cast_result)) # this prints out a lot of stuff.
                    else:
                        # TEMPORARY FOR DEBUGGING
                        print(avp_util.print_dict(cast_result)) # this prints out a lot of stuff.
                except Exception as e:
                    self.logger.critical('Cast error in {0}.run, {1}'.format(self.__class__.__name__,e))
                    traceback.print_stack()
                    traceback.print_exc()
            with self.schedule_lock:
                self.schedule[entry_number]['action_status'] = 'done'
        except Exception as e:
            self.logger.warning('{0}.run caught exception {1}'.format(self.name,e))
            traceback.print_stack()
            traceback.print_exc()
        return
    def shutdown(self):
        self.Scheduler.shutdown()
        self.running = False
        time.sleep(1)
        self.logger.debug("Shutting down {0:24} {1:2} threads left...".format(self.name,threading.active_count()))
    
class _AVPSchedule(threading.Thread):
    '''
    This class monitors the <hostname>_schedule table which has fields based upon crontab notation.
    The table is parsed when the thread is started and when a database poll() indicates there have been updates to a table.
    When a table is loaded, the time to next action is calculated. If there are multiple entries at the same time, these are strung together using special logic.
    schedule dictionary has the following structure:
    {<entry_no>:{
        'sched_list':[<year>,<month>,<day>,<hour>,<minute>],
        'lisst_cast':<True|False>,
        'isco_cast':<True|False>}
        'isco_bottle':<1-24|null>,
        'depth_target':<isco sample depth>,
        'isco_volume':<isco isco_volume>,
        'PRE_CAST_SETUP_TIME':<time before scheduled cast to process entry in seconds>,
        'action_status':<queued|casting|done>,
        'insert_time':<datetime object representing time entry was put in dictionary>}
    }
    values in the schedule dictionary will remain no longer than one minute unless sch_min = '*'
    There can be more than one entry_no if an isco cast is scheduled at the same time as a regular cast.
    '''
    BROKER_NAME = 'sched'
    def __init__(self,config,schedule_lock,pending_lock,schedule_status,**kwargs):
        '''
        db_last_read    -   Last time database was read in.
        
        '''
        self.config = config
        self.schedule_lock = schedule_lock
        self.pending_lock = pending_lock
        self.schedule_status = schedule_status
        self.debug_mode = kwargs.get('debug_mode',False)
        self.SCHED_OFF_NOTIFICATION_FREQ = timedelta(hours=int(self.config.get('scheduler',{}).get('SCHED_OFF_NOTIFICATION_FREQ',4))) # How often in hours to generate schedule off error message.
        self.last_sched_off_warning = datetime.now(pytz.reference.LocalTimezone()) - self.SCHED_OFF_NOTIFICATION_FREQ # Last time a schedule off notification was generated
        self.PRE_CAST_SETUP_TIME = timedelta(seconds=int(self.config.get('scheduler',{}).get('PRE_CAST_SETUP_TIME',180)))
        self.MAX_SCHEDULED_TIME = timedelta(seconds=int(self.config.get('scheduler',{}).get('MAX_SCHEDULED_TIME',60*60))) #If an entry has been scheduled for more than this amount of time, it is removed.
        self.schedule = {} # schedule dictionary, holds actionable casts
        self.ready = {} # Contains all tasks which have been  parsed from pending, but not yet processed for duplicate functionality.
        self.pending = {} # pending dictionary, holds pending casts
        self.hostname = socket.gethostname()
        self.running = False
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        self.logger.debug("Instantiating")
        super(_AVPSchedule,self).__init__()
        self.name = self.__class__.__name__ # Set thread name to class name sinch there should only be one instance.
        self.daemon = True
        self.db_last_read = None
    def start(self,**kwargs):
        '''
        Connect do DB and load contents
        '''
        if self.running:
            print("scheduler already running")
        else:
            SCHEDULE_TABLE = self.config['db'].get('SCHEDULE_TABLE','{0}_schedule'.format(self.hostname))
            self.sch_db = avp_db.AvpDB(self.config,
                                    table=SCHEDULE_TABLE,
                                    polling=True,           # We will be polling to re-load on changes
                                    RDC=True,               # RealDictionaryCursor
                                    **kwargs)
            self.running = True
            self.load_db(**kwargs)
            super(_AVPSchedule,self).start()       #threading.Thread.start(self)
    def load_db(self,**kwargs):
        '''
        Reads in database to self.select_db then calls parse_db
        '''
        self.logger.debug("Reading schedule database")
        self.select_db = self.sch_db.select(['*'],fetch_type='all',**kwargs)
        self.db_last_read = datetime.now(pytz.reference.LocalTimezone())
        #if self.debug_mode:
        #    print "SELECT SCHEDULE DATABASE RESULT:"    #in debug fork
        #    for something in self.select_db:
        #        print ">",something                     #in debug fork
        self.parse_db(**kwargs) # parse self.select_db
        # re-calculate next cast time for each entry and populate self.pending
    def parse_db(self,**kwargs):
        '''
        Rebuilds pending (dictionary of Scheduled casts which are more than a minute in the future)
        '''
        with self.pending_lock:
            self.pending.clear() # Remove everything from previously parsed schedule
            for record in self.select_db:
                if self.debug_mode: print(">>",record)
                next_time = CronTime(date_time=datetime.now(pytz.reference.LocalTimezone()) + self.PRE_CAST_SETUP_TIME )
                cron = CronTime(date_list=[self.is_wild(record['sch_month']),
                                                self.is_wild(record['sch_day']),
                                                self.is_wild(record['sch_hour']),
                                                self.is_wild(record['sch_min'])])
                if self.debug_mode: print("Looking for : {0} {1} {2} {3} {4}".format(cron.year,
                                                                                cron.month,
                                                                                cron.day,
                                                                                cron.hour,
                                                                                cron.minute))
                iters = 0
                max_iters = 200
                success = False
                while True: # We break out of this
                    iters += 1
                    if iters > max_iters: #Something's wrong, don't get stuck
                        break
                    # Fix invalid values
                    if next_time.minute >= 60:
                        next_time.minute -= 60
                        next_time.hour += 1
                    if next_time.hour >= 24:
                        next_time.hour -= 24
                        next_time.day += 1
                    try: #Check Day
                        datetime(next_time.year,next_time.month,next_time.day)
                    except ValueError: # Postential error here if day is max + 2, but this is unlikely
                        next_time.day = 1
                        next_time.month +=1
                        if next_time.month == 13:
                            next_time.month -= 12
                            next_time.year += 1
                    if next_time.month >= 13:
                        next_time.month = 1
                        next_time.year += 1
                    #Cron Comparisons
                    if cron.month != '*' and next_time.month not in cron.month:
                        next_time.month += 1
                        next_time.day = 1
                        next_time.hour = 0
                        next_time.minute = 0
                        if self.debug_mode: print("M={0}".format(next_time.month), end=' ')
                        continue
                    if cron.day != '*' and next_time.day not in cron.day:
                        next_time.day += 1
                        next_time.hour = 0
                        next_time.minute = 0
                        if self.debug_mode: print("D", end=' ')
                        continue
                    if cron.hour != '*' and  next_time.hour not in cron.hour:
                        next_time.hour += 1
                        next_time.minute = 0
                        if self.debug_mode: print("H", end=' ')
                        continue
                    if cron.minute != '*' and next_time.minute not in cron.minute:
                        next_time.minute += 1
                        if self.debug_mode: print("m", end=' ')
                        continue
                    success = True
                    break #We're done, everything matches
                self.logger.debug("The next scheduled occurance of entry {0:2} is: {1} {2} {3} {4} {5}".format(
                                                                                            record['entry_no'],
                                                                                            next_time.year,
                                                                                            next_time.month,
                                                                                            next_time.day,
                                                                                            next_time.hour,
                                                                                            next_time.minute))
                if success:
                    if self.debug_mode: print("_AVPSchedule.parse_db adding entry {0} to pending".format(record['entry_no']))
                    self.pending[str(record['entry_no'])] = {
                                                        'lisst_cast':record['lisst_cast'],
                                                        'isco_cast':record['isco_cast'],
                                                        'isco_bottle':record['bottle_number'],
                                                        'depth_target':record['sample_depth'],
                                                        'isco_volume':record['sample_volume'],
                                                        'sched_list':[next_time.year,next_time.month,next_time.day,next_time.hour,next_time.minute],
                                                        'sched_status':None} # Set to 'scheduled' when copied to self.schedule dictionary and 'acting' while being done
                elif self.debug_mode: print("_AVPSchedule.parse_db NOT adding entry {0} to pending".format(record['entry_no']))
                    
            if self.debug_mode: print("Pending casts: ",self.pending)
    def is_wild(self,cron_val):
        '''
        Accepts a string and returns either '*' a wild card or a list with one 
        or more integers.
        '''
        if cron_val != '*':
            try:
                result = [int(cron_val)] # Single integer
            except ValueError as e: # List of integers
                result = []
                for item in cron_val.split(','):
                    result.append(int(item))
                #self.logger.debug("Converted {0} to {1}".format(cron_val,result))
        else:
            result = cron_val # Wildcard
        return result
    def shutdown(self,**kwargs):
        self.running = False
        time.sleep(1)
        try:
            self.sch_db.close()
        except AttributeError as e:
            pass # probably never started
        self.logger.debug("Shutting down {0:24} {1:2} threads left".format(self.name,threading.active_count()))
    def run(self):
        self.logger.debug("Running {0:24}, {1:2} active threads.".format(self.name,threading.active_count()))
        while self.running:
            self.ready.clear()
            
            # See if we need to remove any old scheduled casts which haven't been done. This may happen if schedule is off or paused.
            if self.debug_mode: print("Checking schedule at {0}".format(datetime.now(pytz.reference.LocalTimezone())))
            reparse = False
            with self.schedule_lock:
                for entry_number in list(self.schedule.keys()): 
                    how_late = datetime.now(pytz.reference.LocalTimezone()) - self.schedule[entry_number].get('insert_time',datetime.now(pytz.reference.LocalTimezone()))
                    if self.schedule[entry_number].get('action_status',None) is 'done': # They have been done
                        self.logger.debug("Removing done scheduled item {0}.".format(self.schedule[entry_number]))
                        self.schedule.pop(entry_number)
                        reparse = True
                    elif how_late >= self.MAX_SCHEDULED_TIME: # They have been in the schedule too long
                        self.logger.debug("Removing scheduled item after {1} seconds of inactivity.({0})".format(self.schedule[entry_number],how_late.seconds))
                        self.schedule.pop(entry_number)
                        reparse = True
            if reparse is True:
                self.parse_db()
                continue
                    
            # Look for changes to schedule database. If so, reload.
            try: 
                poll_result = self.sch_db.poll(debug_mode=self.debug_mode)
            except Exception as e:
                self.logger.error("{0} db poll failure {1}".format(self.__class__.__name__,e))
                poll_result = False
            if poll_result:
                self.logger.info("Poll indicates need to reload {0}".format(poll_result))
                self.load_db()
                
            # See if any entries can be copied from pending to ready
            comp_time = datetime.now(pytz.reference.LocalTimezone()) + self.PRE_CAST_SETUP_TIME
            comp_time -= timedelta(seconds=comp_time.second, # Now round to nearest minute.
                                 microseconds=comp_time.microsecond)
            reparse = True
            with self.pending_lock:
                for entry_number,pend_cast_data in list(self.pending.items()): # This keeps us from doing this more than once not_scheduled
                    try:
                        sched_status = pend_cast_data.get('sched_status',None)
                        sched_time = datetime(year=pend_cast_data['sched_list'][0],
                                              month=pend_cast_data['sched_list'][1],
                                              day=pend_cast_data['sched_list'][2],
                                              hour=pend_cast_data['sched_list'][3],
                                              minute=pend_cast_data['sched_list'][4],
                                              second=0,
                                              tzinfo=pytz.reference.LocalTimezone())
                        if self.debug_mode:print("comp:{0} == sched{1} & not {2}".format(comp_time,sched_time,sched_status))
                        if comp_time == sched_time: # If the times match and it hasn't been scheduled.
                            reparse = False # Not on a match
                            if sched_status is None: # If the times match and it hasn't been scheduled.
                                self.ready[entry_number] = pend_cast_data # Found a match!
                                self.pending[entry_number]['sched_status'] = 'scheduled'
                                if self.debug_mode: print("Found schedule match")
                        elif sched_status is'scheduled':
                            if  sched_time < datetime.now(pytz.reference.LocalTimezone()):
                                # We've passed the scheduled time. We should be at least 'processing' by now
                                # Generate our message
                                error_msg = "Schedule is {state} since {sched}".format(sched=sched_time,state=self.schedule_status.state)
                                if self.schedule_status.state == 'off':
                                    if datetime.now(pytz.reference.LocalTimezone()) - self.last_sched_off_warning >= self.SCHED_OFF_NOTIFICATION_FREQ:
                                        self.logger.warning(error_msg)
                                        self.last_sched_off_warning = datetime.now(pytz.reference.LocalTimezone())
                                    else:
                                        self.logger.info(error_msg)
                                else:
                                    self.logger.warning(
                                        "Missed schedule item {0}, {1} > {2}. Schedule is {3}".format(entry_number,
                                                                                                      comp_time,
                                                                                                      sched_time,
                                                                                                      self.schedule_status.state))
                            else:
                                reparse = False
                        elif sched_status is 'processing': # Wait until we are done to re-parse schedule
                            reparse = False
                        elif sched_status is 'acting': # The launcher should be done with it.
                            if self.debug_mode: print("Scheduler is acting on entry {0} so re-parse db".format(entry_number))
                        if self.debug_mode:
                                next_sched = sched_time - datetime.now(pytz.reference.LocalTimezone())
                                self.logger.debug("Next scheduled in {0} days, {1} seconds".format(next_sched.days,next_sched.seconds))
                    except Exception as e:
                        self.logger.error("error {0} processing {1}".format(e,pend_cast_data))
            if reparse and len(self.ready) > 0:
                self.parse_db()
                continue
            # If we have something to give to the launcher
            if len(self.ready) > 0: # If we have something to put in the schedule dictionary...
                self.logger.debug("looking for matches in: {0}".format(self.ready))
                #self.schedule.clear()
                # Need to look for duplicates to combine. E.g. a regular and lisst cast.
                for entry_number_o,cast_info_o in list(self.ready.items()):
                    if cast_info_o.get('match',False) is False: # Skip records which have been previously matched
                        for entry_number_i,cast_info_i in list(self.ready.items()):
                            if entry_number_o != entry_number_i: # Don't compare a record with itself
                                # Check if we have the same schedule, not isco and not previously matched 
                                if (cast_info_o['sched_list'] == cast_info_i['sched_list'] and         # Schedules match,
                                                                 cast_info_i['isco_cast'] is False and # Not isco and
                                                                 cast_info_o['isco_cast'] is False and
                                                                 not cast_info_i.get('match',False)):  #  not previously matched
                                    # There's a match, so mark the record so we don't look at it again
                                    self.ready[entry_number_i]['match'] = True # Will now ignore this one.
                                    with self.pending_lock:
                                        self.pending[entry_number_i]['sched_status'] = None  # We will be combining this one with another, so no longer 'scheduled'
                                    self.ready[entry_number_o] = cast_info_o # Use the key from the first one
                                    self.ready[entry_number_o]['lisst_cast'] = cast_info_o['lisst_cast'] or cast_info_i['lisst_cast']
                                    self.ready[entry_number_o]['action_status'] = 'queued' # Use the key from the first one
                                    self.ready[entry_number_o]['PRE_CAST_SETUP_TIME'] = self.PRE_CAST_SETUP_TIME # Use the key from the first one
                                    self.ready[entry_number_o]['insert_time'] = datetime.now(pytz.reference.LocalTimezone()) # Use the key from the first one
                                    #self.ready[entry_number_o].pop('sched_status')  # It's presence in this dict shows that it has been scheduled
                # Now transfer from ready to the schedule 
                for entry_number,value in list(self.ready.items()):
                    if value.get('match',False) is False: # Nothing previously matched
                        with self.schedule_lock:
                            if self.schedule.get(entry_number,False) is False: # or entered.
                                self.logger.debug("Scheduling {0}.".format(value))
                                self.schedule[entry_number] = value
                                self.schedule[entry_number]['action_status'] = 'queued'                
                
            else:
                pass
                #reload_db_time = datetime.now(pytz.reference.LocalTimezone()) + timedelta(days=1) # reload once a day. If all is working this can be much bigger.
            sleep_time = 60 - datetime.now(pytz.reference.LocalTimezone()).second 
            if self.debug_mode: print("Scheduler sleeping {0} sec.".format(sleep_time))
            time.sleep(sleep_time) # Once per minute, on the minute
        #super(_AVPSchedule,self).__init__() # may allow us to re-start thread later

class CronTime(object):
    def __init__(self,date_time=None,date_list=None,**kwargs):
        '''
        docstrings
        '''
        if date_time is None:
            date_time = datetime.now(pytz.reference.LocalTimezone())
        if date_list is None:
            date_list = []
        self.year = self.month = self.day = self.hour = self.minute = None
        if date_list:
            if len(date_list) is 4: # No year, so use current year
                date_list.insert(0,date_time.year)
            if len(date_list) is 5:
                dtargs = {'tzinfo':pytz.reference.LocalTimezone()}
                self.year = date_list[0]
                self.month = date_list[1]
                self.day = date_list[2]
                self.hour = date_list[3]
                self.minute = date_list[4]
                if self.year != '*':
                    dtargs['year'] = self.year
                if self.month != '*':
                    dtargs['month'] = self.month
                if self.day != '*':
                    dtargs['day'] = self.day
                if self.hour != '*':
                    dtargs['hour'] = self.hour
                if self.minute != '*':
                    dtargs['minute'] = self.minute
                try:
                    date_time = datetime(**dtargs)
                except Exception as e:
                     date_time=datetime.now(pytz.reference.LocalTimezone())
            else:
                 date_time=datetime.now(pytz.reference.LocalTimezone())
        if not self.year:
            self.year = date_time.year
        if not self.month:
            self.month = date_time.month
        if not self.day:
            self.day = date_time.day
        if not self.hour:
            self.hour = date_time.hour
        if not self.minute:
            self.minute = date_time.minute
        self.date_time = date_time

def Noneto99(depth):
    # Used as key when sorting depth list to handle None values.
    if depth is None:
        depth = 999.3
    return depth

def main():
    import avp_util
    import sys
    cloptions,config = avp_util.get_config(option_set='sched')
    logger = logging.getLogger('avp_sched')
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    dbh = avp_db.DB_LogHandler(config)
    dbh.setLevel(logging.DEBUG)
    logger.addHandler(dbh)
    launcher = AVPLauncher(config,program_name='avp_sched',debug_mode=False)
    launcher.start()
    schedule = {}
    pending = {}
    i = 0
    while True:
        if schedule != launcher.schedule:
            schedule = launcher.schedule
            i = 0
        if pending != launcher.pending:
            pending = launcher.pending
            i = 0
        if i % 18 == 0:
            if False:
                print("SCHEDULED:")
                for no,sched in list(launcher.schedule.items()):
                    print("    ",no,sched)
                print("PENDING:")
                for no,pend in list(launcher.pending.items()):
                    print("    ",no,pend)
        time.sleep(10)
        i += 1
        
if __name__ == '__main__':
    main()