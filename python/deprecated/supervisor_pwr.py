#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        supervisor
# Purpose:     Monitors processes and system resources in an effort to keep the entire system running.
#
# Author:      whipple
#
# Created:     01/02/2012
#-------------------------------------------------------------------------------
#Built in Modules
from collections import deque
from datetime import datetime,timedelta
import logging
import os
import signal
import socket
from subprocess import Popen,PIPE
import sys
import threading
from time import sleep, strptime
#Installed Modules
from configobj import ConfigObj
if os.name is 'posix':
    import psutil
import pytz.reference
#Custom Modules
import avp_broker
import avp_db
import avp_sched
import avp_util
import gislib
import localInterface
import notification
import pertd2

import avp_power

class Supervisor(object):
    def __init__(self,program_name=__name__,**kwargs):
        '''
        '''
        self.program_name = program_name
        self._running = True
        # catch some signals and perform an orderly shutdown
        signal.signal(signal.SIGTERM, self._stopRunning)
        signal.signal(signal.SIGHUP,  self._stopRunning)
        #signal.signal(signal.SIGINT,  self._stopRunning)
        signal.signal(signal.SIGQUIT, self._stopRunning)
        signal.signal(signal.SIGILL,  self._stopRunning)
        signal.signal(signal.SIGABRT, self._stopRunning)
        signal.signal(signal.SIGFPE,  self._stopRunning)
        signal.signal(signal.SIGSEGV, self._stopRunning)
        # Read the config file
        self._config = ConfigObj(sys.argv[1])  
        self.HOME_PATH = self._config.get('supervisor',{}).get('HOME_PATH','/home/avp')
        self.LOG_PATH = self._config.get('supervisor',{}).get('LOG_PATH',self.HOME_PATH + '\log')
        self.CHECK_FREQ = int(self._config.get('supervisor',{}).get('CHECK_FREQ',1))
        self.LOG_FREQ = int(self._config.get('supervisor',{}).get('LOG_FREQ',1))
        self.LOCAL_INTERFACE = avp_util.t_or_f(self._config.get('supervisor',{}).get('LOCAL_INTERFACE',True))
        # There is a bug where strptime will give an attribute error when first used in a new thread.
        # Supposedly using it from the main thread first will keep this from happening.
        strptime("20110131","%Y%m%d")
        # set up logging with a root level logger
        self._logger = logging.getLogger(self.__class__.__name__)
        # Set up notifications
        self.notification = notification.Notification(self._config)
        self.notification.start()
        # some startup messages
        self._logger.info('Starting AVP System Supervisor')
        if self.LOCAL_INTERFACE == True:
            self._logger.info('Initializing LCD')
            self._lcd = pertd2.Pertelian()
            self._lcd.delay_time(100000) # Set delay time to .1 a second
        else:
            self._logger.info('LCD Not Initialized {0}'.format(self.LOCAL_INTERFACE))
            self._lcd = Passer() # Accepts anything and returns nothing
        # set the environment variable required for the aio broker to run
        try:
            os.environ['LD_LIBRARY_PATH']=self._config['aio']['LD_LIBRARY_PATH']
        except KeyError, e:
            self._logger.critical('Error finding configuration key '+str(e))
            sys.exit(1)
        # Dome database things....
        power_table = self._config['db'].get('POWER_TABLE','{0}_power'.format(socket.gethostname()))
        self.power_db = avp_db.AvpDB(self._config,power_table)
        # time of most recent warning issued by gps or compass (set to ten minutes ago)
        self.latq = deque([])  # list from which the averages are taken
        self.lonq = deque([])  # list from which the averages are taken
        self.latlontimeq = deque([])  # list of associated times
        self.gpsWarnTime = datetime.now(pytz.reference.LocalTimezone()) - timedelta(seconds=600)
        self.compassWarnTime = datetime.now(pytz.reference.LocalTimezone()) - timedelta(seconds=600)\
        
    def _initialize_broker_clients(self):
        self.broker_list = self._config.get('supervisor',{}).get('brokerList',{}).values() # ['aio','gps','sonde','wind','sounder','isco','lisst','mm3']
        self.context = avp_util.AVPContext(self._config,startup=self.broker_list,program_name=self.program_name, debug_mode=False) # Set up console context
        try:
            self.aio = self.context.aio
        except AttributeError,e:
            self._logger.critical('Unable to instantiate AIO broker: {0}'.format(e))
        # To monitor schedule status
        self.schedule_status = avp_sched.AVPScheduleStatus(self._config,debug_mode=False)
        # create the local user interface thread
        if self.LOCAL_INTERFACE == True:
            self._logger.info('Initializing Local Interface')
            self._locInterface = localInterface.LocalInterface(self)    # pass along our context (as self)
        else:
            self._logger.info('No Local Interface Initialized')
            self._locInterface = Passer() # Accepts anything and returns nothing
        
    def main_loop(self,**kwargs):
        ''' This is basically the main routine. '''
        self.loops = 0 # Reset to 0 on any broker start so that we don't start scheduler too soon.
        checkCS = True
        self.log_items = {} # Will hold field:value pairs to insert into database
        self.py_processes = {}
        self.py_processes['sched'] = {'search_str':'avp_sched.py',
                                 'spawn_str':'/home/avp/bin/cast_sched.sh',
                                 'args':'',
                                 'pid':None,
                                 'old_pid':None,
                                 'root':False}
        self.py_processes['pingTest'] = {'search_str':'pingTest.py',
                                    'spawn_str':None,
                                    'args':'',
                                    'pid':None,
                                    'old_pid':None,
                                    'root':True}
        while self._running == True:
            if datetime.now(pytz.reference.LocalTimezone()).second == 0 or checkCS is True:
                if datetime.now(pytz.reference.LocalTimezone()).minute % self.CHECK_FREQ == 0 or checkCS is True:
                    self._checkSerial()    # check and set up the serial ports
                    self._checkJavaBrokers()   # check the brokers
                    if self.loops >= 1: #Skip the first loop to give brokers time to get going.
                        if hasattr(self,'aio') is False: #Skip the first loop to give brokers time to get going.
                            self._initialize_broker_clients()
                        self._checkPyProcesses() # Check python processes. 
                    self._checkConnectionsAndSubscriptions() # Uses aio but returns if broker not yet instantiated
                    self._check_controller()
                    self._doPowerStatus() # Uses aio but returns if broker not yet instantiated
                    self._gps_checks()
                    self._wind_checks()
                    self.loops += 1
                if datetime.now(pytz.reference.LocalTimezone()).minute % self.LOG_FREQ == 0:
                    self._do_env_logging()
            if self.loops == 1:
                sleep(60)
            else:
                sleep(1)
                # Now check if any brokers have disconnected and re-check every 1second.
                checkCS = False
                for broker in self.context.brokers:
                    if getattr(self,broker).socket_handler.connected is False:
                        self._logger.warning('{0} broker is not connected'.format(broker))
                        checkCS = True
        self.shutdown()
    def _gps_checks(self):
        if hasattr(self,'gps') is False:
            self._logger.debug('No gps broker client yet, skipping _gps_checks')
            return
        elif self.wind.initialized is False:
            self._logger.debug('gps broker client not initialized, skipping _gps_checks')
            return
        if self.gps.connected is True:
            try:
                out_of_position_message = ''
                self.ANCHOR_WATCH_CENTER = (self.ANCHOR_WATCH_LAT,self.ANCHOR_WATCH_LON,)
            except KeyError,e:
                self._logger.warning('Error finding configuration key '+str(e))
                return
            # Check our GPS Position
            try:
                mode= self.gps.mode.value
                if mode == 3:   # only check gps for 3d fixes
                    self.latq.append(self.gps.lat.value)
                    self.lonq.append(self.gps.lon.value)
                    self.latlontimeq.append(self.gps.lat.sample_time)
                    if self.latlontimeq[-1] - self.latlontimeq[0] > timedelta(seconds=900):  # keep 900 seconds
                        self.latq.popleft()
                        self.lonq.popleft()
                        self.latlontimeq.popleft()
                    lat = sum(self.latq) / len(self.latq)
                    lon = sum(self.lonq) / len(self.lonq)
            except Exception,e:
                print "Exception checking gps position: ",e
                lat = lon = mode = None
            if mode == 3:   # only check gps for 3d fixes
                try:
                    if lat is not 'NaN' and lon is not 'NaN':
                        distance,bearing = gislib.get_distance_bearing(self.ANCHOR_WATCH_CENTER,(lat,lon))
                        self._logger.debug("GPS location is {0:d}m at {1:5.4} deg. from expected location.".format(int(distance*1000),bearing))
                        if distance > self.ANCHOR_WATCH_RADIUS:
                            out_of_position_message += "{0:d}m at {1:5.4} deg. from expected location.".format(int(distance*1000),bearing)
                    '''
                    if lat is not 'NaN':
                        if float(lat) > watchBoxN:
                            out_of_position_message += "Lat {0} North of limit {1}. ".format(lat,watchBoxN)
                        elif float(lat) < watchBoxS:
                            out_of_position_message += "Lat {0} South of limit {1}. ".format(lat,watchBoxS)
                    if lon is not 'NaN':
                        # Note that our longditudes are negative
                        if float(lon) < watchBoxW:
                            out_of_position_message += "Lon {0} West of limit {1}. ".format(lon,watchBoxW)
                        if float(lon) > watchBoxE:
                            out_of_position_message += "Lon {0} East of limit {1}. ".format(lon,watchBoxE)
                    # Out of watch box - issue warnings every so often
                    '''
                except Exception,e:
                    print "Failed to evaluate position from {0},{1} ({2})".format(lat,lon,e)
                if out_of_position_message and (datetime.now(pytz.reference.LocalTimezone()) > (self.gpsWarnTime + self.WARNING_REPEAT_TIME)):
                    self._logger.warning('GPS position error: {0}'.format(out_of_position_message))
                    self.gpsWarnTime = datetime.now(pytz.reference.LocalTimezone())
        else:
            print "Skipping gps checks"
    def _wind_checks(self):
        '''
        Try checking our compass heading and see if it si withing expected range.
        '''
        if hasattr(self,'wind') is False:
            self._logger.debug('No wind broker client yet, skipping _wind_checks')
            return
        elif self.wind.initialized is False:
            self._logger.debug('wind broker client not initialized, skipping _wind_checks')
            return
        elif self.wind.connected is True:
            heading = self.wind.compass_direction.value
            warning = False
            print "compass heading:{0}".format(heading) # For debugging
            cwlimit = self.wind.COMPASS_TARGET + self.wind.COMPASS_MARGIN 
            ccwlimit = self.wind.COMPASS_TARGET - self.wind.COMPASS_MARGIN
            # Make sure everything is between 0 and 360
            if cwlimit  >= 360: cwlimit  -= 360
            if cwlimit  <    0: cwlimit  += 360
            if ccwlimit >= 360: ccwlimit -= 360
            if ccwlimit <    0: ccwlimit += 360
            if datetime.now(pytz.reference.LocalTimezone()) > (self.compassWarnTime + timedelta(seconds=600)):
                if cwlimit < ccwlimit:
                    if ( heading > cwlimit and heading < ccwlimit):
                        warning = True
                else:
                    if ( heading > cwlimit or heading < ccwlimit):
                        warning = True
            if warning is True:
                self._logger.warning('Platform heading of {0} indicates possible mooring problem'.format(heading))
                self.compassWarnTime = datetime.now(pytz.reference.LocalTimezone())
        else:
            print "Skipping compass checks"
    def _check_controller(self):
        '''
        Check controller attributes including:
        Root drive space
        Data drive space
        Memory usage
        CPU temperature
        '''
        LOW_DRIVE_THRESHOLD = float(self._config['supervisor'].get('LOW_DRIVE_THRESHOLD',0.10))
        CPU_TEMP_THRESHOLD = float(self._config['supervisor'].get('CPU_TEMP_THRESHOLD',60))
        LOW_RAM_THRESHOLD = float(self._config['supervisor'].get('LOW_RAM_THRESHOLD',0.10))
        drives = {'root':{'mount':'/','field':'disk_free_root'},'database':{'mount':'/data','field':'disk_free_data'}}
        for drive,info in drives.items():
            if os.name is 'posix':
                s_drive = os.statvfs(info['mount'])
                drive_pct = float(s_drive.f_bavail) / s_drive.f_blocks
                self.log_items[info['field']] = drive_pct * 100
            else:
                drive_pct = 1
            if drive_pct < LOW_DRIVE_THRESHOLD:
                message = '{drive} drive free space is down to {0:.1f}%, which is below the threshold of {1:.1f}%'.format(drive_pct*100,LOW_DRIVE_THRESHOLD*100,drive=drive) 
                self._logger.warning(message)
            else:
                message = '{drive} drive free space is {0:.1f}%, which is above the threshold of {1:.1f}%'.format(drive_pct*100,LOW_DRIVE_THRESHOLD*100,drive=drive) 
                self._logger.debug(message)
        # check percentage of available memory
        mem = psutil.phymem_usage()
        if os.name is 'posix':
            freeMemoryPct = float(mem.total - mem.used + psutil.cached_phymem()) / mem.total
        else:
            freeMemoryPct = float(mem.total - mem.used) / mem.total
        self.log_items['free_memory'] = freeMemoryPct * 100
        if freeMemoryPct < LOW_RAM_THRESHOLD:
            message = 'Free memory (non-cache) is down to {0:.1f}%, which is below the threshold of {1:.1f}%'.format(freeMemoryPct*100,LOW_RAM_THRESHOLD*100)
            self._logger.warning(message)
        else:
            message = 'Free memory is {0:.1f}%, which is above the threshold of {1:.1f}%'.format(freeMemoryPct*100,LOW_RAM_THRESHOLD*100)
            self._logger.debug(message)
        # check CPU temperature
        process = Popen('sensors',stdout=PIPE)
        tempDegCstr = process.communicate()[0]
        exit_code = process.wait()
        w = tempDegCstr.find('Core 0:') # Find our line
        str_x = tempDegCstr[w:] # and extract just this line
        y = str_x.find('+') # Mark our extents
        z = str_x.find('\xc2')
        try:
            tempDegC = float(str_x[y:z]) # Extract and convert
            if tempDegC == 40.0: # If the temperature is being reported as 40.0 it is actually something less than 40
                message = 'CPU Temperature is < {0:.0f} deg C'.format(tempDegC)
                self._logger.debug(message)
            else:
                self.log_items['temp_cpu'] = tempDegC
                if tempDegC > CPU_TEMP_THRESHOLD:
                    message = 'CPU Temperature is {0:.0f} deg C which is above the threshold of {1:.0f} deg C'.format(tempDegC,CPU_TEMP_THRESHOLD)
                    self._logger.warning(message)
                else:
                    message = 'CPU Temperature is {0:.0f} deg C which is below the threshold of {1:.0f} deg C'.format(tempDegC,CPU_TEMP_THRESHOLD)
                    self._logger.debug(message)
        except ValueError,e:
            message = 'Could not parse CPU Temperature: {0} \n{1} \n{2} \n{3} \n{4}'.format(tempDegCstr,w,x,y,z)
            self._logger.debug(message)
            
    def _doPowerStatus(self):
        '''
        Gets status of:
            voltage
            one minute voltage (system voltage)
            charge current
            
        '''
        if hasattr(self,'aio') is False:
            self._logger.debug('No aio broker client yet, skipping _doPowerStatusi686')
            return
        elif self.aio.initialized is False:
            self._logger.debug('aio broker client not initialized, skipping _doPowerStatusi686')
            return
        elif hasattr(self,'power_obj') is False:
            self._logger.debug('power_obj not initialized, skipping _doPowerStatusi686')
            return
        try:
            LOW_AMP_HOURS = float(self._config['supervisor'].get('LOW_AMP_HOURS',-100))
            LOW_BAT_VOLTAGE= float(self._config['supervisor'].get('LOW_BAT_VOLTAGE',11.2))
            SHUTDOWN_VOLTAGE=float(self._config['supervisor'].get('SHUTDOWN_VOLTAGE',10.7))
            HIGH_HUMIDITY=float(self._config['supervisor'].get('HIGH_HUMIDITY',70))
        except KeyError, e:
            self._logger.critical('Error finding configuration key '+str(e))
            sys.exit(1)
        # Get values
        load_amp_hours   = self.load_current.amp_hours
        charge_amp_hours = self.charge_current.amp_hours
        system_voltage   = self.voltage.one_min_ave
        charge_current   = self.charge_current.one_min_ave
        load_current     = self.load_current.one_min_ave
        netCharge        = charge_amp_hours - load_amp_hours
        try:
            ambient_temp     = self.mm3.temperature.value
            sensor_RH = self.aio.humidity_ADC.value
            humidity         = (( sensor_RH/ 5.0) - 0.16) / .0062 # This is what we log
            corrected_humidity = humidity / (1.0546 - (0.00216 * ambient_temp)) # This is derived from ambient_temp so can be calculated again in SQL
        except AttributeError,e:
            ambient_temp = 0
            humidity = 0
            corrected_humidity = 0
        # Add to log dictionary
        self.log_items['system_voltage']     = system_voltage
        self.log_items['charge_current']     = charge_current
        self.log_items['charge_power']       = system_voltage * charge_current
        self.log_items['charge_current_max'] = self.charge_current.maximum
        self.log_items['charge_amp_hours']   = charge_amp_hours
        self.log_items['load_power']         = system_voltage * self.load_current.one_min_ave
        self.log_items['load_current_max']   = self.load_current.maximum
        self.log_items['load_current']       = load_current
        self.log_items['load_amp_hours']     = load_amp_hours
        self.log_items['humidity']           = humidity
        self.log_items['temp_ambient']       = ambient_temp
        
        # Report and log any values out of spec.
        if netCharge < LOW_AMP_HOURS:
            self._logger.warning('Net charge: {0:.2f} Amp-Hours is less than the threshold of {1:.2f} Amp-Hours'.format(
                netCharge, LOW_AMP_HOURS))
        else:
            self._logger.debug('Net charge: {0:.2f} Amp-Hours'.format(netCharge))
        if system_voltage < LOW_BAT_VOLTAGE and system_voltage != 0:
            self._logger.warning('One min avg voltage: {0:.2f} V is less than the threshold of {1:.2f} V. Pausing schedule'.format(
                system_voltage, LOW_BAT_VOLTAGE))
            # Suspend casting while voltage is too low
            if self.schedule_status.state == 'on': 
                self._logger.warning('Pausing schedule due to low voltage')
            self.schedule_status.state = 'paused' # This will just extend the pause time, but no need for another message.
        if humidity >= HIGH_HUMIDITY:
            self._logger.warning('Humidity: {0:.2f}% ({1:.2f} temperature corrected) is greater than the warning level of {2:.2f}%'.format(
                humidity, corrected_humidity,HIGH_HUMIDITY))
     
        # If the voltage gets too low the solar charger won't be able to recharge the batteries.
        # When we get close to that threshold, we will shut the sytem down via the power relay.
        # This will require an operator to start the system manually by re-energizing the power relay
        # through the modem using the at+bdoset=do1,0 command.
        if (system_voltage < SHUTDOWN_VOLTAGE) and (system_voltage != 0): 
            self._do_env_logging()
            self._logger.critical('One min avg voltage: {0:.2f} V is less than the shutdown threshold of {1:.2f} V'.format(
                system_voltage, SHUTDOWN_VOLTAGE))
            self._logger.critical('VERY LOW VOLTAGE: {0}V. SYSTEM SHUTTING DOWN VIA POWER RELAY'.format(system_voltage))
            self._logger.critical('VERY LOW VOLTAGE: {0}V. SYSTEM SHUTTING DOWN VIA POWER RELAY'.format(system_voltage))
            self._logger.critical('VERY LOW VOLTAGE: {0}V. SYSTEM SHUTTING DOWN VIA POWER RELAY'.format(system_voltage))
            self.notification.notify_now()
            # SHUTDOWN THE SYSTEM
            #subprocess.Popen(['sudo','/home/avp/bin/postgres_shutdown.sh'],shell=False,stdout=subprocess.PIPE)
            newDaemon = self.HOME_PATH + '/bin/suicide_shutdown.sh'
            stdout = self.LOG_PATH + '/suicide_shutdown.log'
            stderr = self.LOG_PATH + '/suicide_shutdown.log'
            try:
                avp_util.spawnDaemon(newDaemon.split(), stdout=stdout, stderr=stderr)
            except SystemExit:
                pass    # the child process will exit as part of creating a daemon process
    def _do_env_logging(self):
        self.log_items['sample_time'] = datetime.now(pytz.reference.LocalTimezone())
        self.power_db.buffered_insert(self.log_items)
        self.log_items.clear()
    def _checkSerial(self):
        self._logger.debug('Checking serial ports')

        try:
            # check and/or set the baud rates on the serial ports
            SERIAL_DEVICES = self._config['serial']['SERIAL_DEVICES']
            SERIAL_BAUDS   = self._config['serial']['SERIAL_BAUDS']
        except KeyError, e:
            self._logger.critical('Error finding configuration key '+str(e))
            sys.exit(1)

        for device, baud in zip(SERIAL_DEVICES, SERIAL_BAUDS):
            #User must be a member of group dialout for this to work
            dSpeed = os.popen("stty -F " + device + " speed").read().rstrip('\n')
            if dSpeed != baud:
                self._logger.info("Baud rate mis-match. Calling: stty -F {0} {1}".format(device,baud))
                os.popen("stty -F {0} {1}".format(device,baud))
    def _checkPyProcesses(self):
        '''
        Checks for the following python processes and instantiates them as necessary:
        Scheduler
        '''
        try:
            for py_process,pp_info in self.py_processes.items():            
                pp_info['old_pid'] = pp_info['pid']
                pp_info['pid'] = None
                search_str = str(pp_info['search_str'])
                try:
                    for process in psutil.process_iter():
                        #print "Looking for {0} in {1}".format(search_str,' '.join(process.cmdline))
                        if search_str in ' '.join(process.cmdline):
                            pp_info['pid'] = process.pid
                            #print "FOUND {0} in {1}".format(pp_info['search_str'],' '.join(process.cmdline))
                            break
                except Exception,e:
                    print e
                    pp_info['pid'] = pp_info['old_pid']
                    continue
            #print self.py_processes
            try:
                for py_process,pp_info in self.py_processes.items():
                    if pp_info['pid'] is None:
                        if pp_info.get('root',False) is False:
                            # Respawn
                            newDaemon = "{0} {1}".format(pp_info['spawn_str'],pp_info['args'])
                            if pp_info['old_pid'] is None:
                                self._logger.info('Spawning: {0}'.format(newDaemon))
                            else:
                                self._logger.warning('Re-spawning: {0}'.format(newDaemon))
                            stdout = '{0}/{1}.log'.format(self.LOG_PATH,py_process)
                            avp_util.spawnDaemon(newDaemon.split(), stdout=stdout, stderr=stdout) #------------------------------------------UNCOMMENT
                        else:
                            self._logger.warning('{0} process is not running. Can only be started by root.'.format(py_process))
                    else:
                        self._logger.debug('Found {0} python process'.format(py_process))
            except Exception,e:
                print "_checkPyProcesses respawn {0}".format(e)
        except Exception,e:
            print "_checkPyProcesses psutil{0}".format(e)
    def _checkJavaBrokers(self):
        '''
        Tests for existance and status of all necessary brokers and instantiates
        them if necessary
        '''
        self._logger.debug('Checking broker processes')
        brokerInfoList = []
        super_config = self._config.get('supervisor',{})
        try:
            brokerList = super_config['brokerList']
            JAVA_INSTALL_DIR    = super_config.get('JAVA_INSTALL_DIR')
            JAVP_JAR           = super_config.get('JAVP_JAR')
            JSON_JAR            = super_config.get('JSON_JAR')
            POSTGRES_JAR        = super_config.get('POSTGRES_JAR')
        except KeyError, e:
            self._logger.critical('Error finding configuration key '+str(e))
            sys.exit(1)
        # Set up a data structure for each broker in the broker list
        for broker in brokerList.keys():
            brokerInfoList.append(BrokerInfo(name=broker[:-5])) #Strip off the '.conf' # COULD THIS BE DONE MORE SIMPLY WITH A DICTIONARY?

            # Look for brokers by name in the process status list
            try:    # process_iter can throw an exception
                for process in psutil.process_iter():
                    # processes can disappear -- make local copies of process info
                    try:
                        cmdline = process.cmdline
                        pid = process.pid
                    except Exception:
                        continue    # if the process is gone just move on to the next one

                    cmd = '{0}/bin/{1}'.format(JAVA_INSTALL_DIR,broker)
                    if cmd in cmdline:
                        self._logger.debug('Found broker ' + str(broker) )
                        brokerInfoList[-1].pid = pid
                        # will broker respond to a request
                        # The names in broker are not generic.  brokerList is a dictionary that maps to generic names.
                        if hasattr(self, brokerList[broker]):
                            if getattr(self, brokerList[broker]).connected == True:
                                try:
                                    if len(getattr(self, brokerList[broker]).list_data()) < 1: # what will this really do, timeout?
                                        self._logger.debug("list_data: " + getattr(self, brokerList[broker]).list_data() )
                                        self._logger.debug("len: " + len(getattr(self, brokerList[broker]).list_data()) )
                                        # Broker is not responding
                                        self._logger.warning('Broker {0} not responding. Killing for restart.'.format(broker))
                                        getattr(self,'_'+brokerList[broker]).disconnect()
                                        if os.name is 'posix':
                                            os.kill(pid, signal.SIGTERM)
                                        brokerInfoList[-1].pid = 0     # Mark the broker as needing startup
                                except Exception,e:
                                    self._logger.warning('Broker {0} not responding - threw exception {1}. Killing for restart.'.format(broker,e))
                                    getattr(self, '_'+brokerList[broker]).disconnect()
                                    if os.name is 'posix':
                                        os.kill(pid, signal.SIGTERM)
                                    brokerInfoList[-1].pid = 0     # Mark the broker as needing startup
            except Exception:
                continue    # If something goes wrong, just keep going.  The most likely thing to catch here
                            # is when a process disappears while we are iterating through the list.
                            # This should be a bit more specific, catching only the exceptions we expect.

            if brokerInfoList[-1].pid == 0:     # broker was not found, let's start it up

                # broker was not found, see if we need to disconnect
                if hasattr(self, brokerList[broker]) and getattr(self, brokerList[broker]).connected == True:
                    self._logger.warning('Broker process {0} missing after having been connected.'.format(broker))
                            
                newDaemon = 'java -cp {0}{1}:{2}:{3} org.renci.avp.Broker {0}/bin/db.conf {0}/bin/{4}'.format(JAVA_INSTALL_DIR,JAVP_JAR,JSON_JAR,POSTGRES_JAR,broker)
                self._logger.info('Spawning: {0}'.format(newDaemon))
                # To name the log files we will add .log
                # This assumes that the names in broker end in .conf
                stdout = '{0}/{1}.log'.format(self.LOG_PATH,brokerList[broker])
                stderr = stdout
                avp_util.spawnDaemon(newDaemon.split(), stdout=stdout, stderr=stderr)
                self.loops = 0
    def _checkConnectionsAndSubscriptions(self,**kwargs):

        # set up brokers
        # if we just started the aio broker it may be a few seconds before we can connect
        if hasattr(self,'aio') is False:
            self._logger.debug('No aio broker client yet, skipping _checkConnectionsAndSubscriptions')
            return
        if self.aio.initialized is True:
            if hasattr(self,'power_obj') is False:
                # Look in power_db for most recent ah value
                last_env_dt = self.power_db.select(columns=('max(sample_time)',))[0][0]
                d_now = datetime.now()
                if (last_env_dt.year  == d_now.year and 
                    last_env_dt.month == d_now.month and 
                    last_env_dt.day   == d_now.day):
                    where_condition = {'sample_time':last_env_dt}
                    last_ah = self.power_db.select(columns=('load_amp_hours','charge_amp_hours',),
                                                            where_condition=where_condition,
                                                            where_oper='=')[0]
                    last_load_ah,last_charge_ah = last_ah
                else: #It's a new day
                    last_load_ah = last_charge_ah = 0
                self.power_obj = avp_power.AVP_Power(self.aio,self._config,last_load_ah,last_charge_ah)
                self.charge_current   = self.power_obj.charge_current
                self.load_current     = self.power_obj.load_current
                self.voltage          = self.power_obj.voltage
            # Check aio default settings
            aio_defaults = {'power_sounder':1,        # Sounder
                                 'power_sonde':1,          # Sonde
                                 'power_wind':1,           # Wind
                                 'power_MM3':1,            # MotionMind3
                                 'limit_switch_disable':0} # Limit Switch must be grounded
            aio_to_set = {}
            for pin,desired_value in aio_defaults.items():
                aio_value = getattr(self.aio,pin).value
                if aio_value != desired_value:
                    aio_to_set[pin] = desired_value
            if len(aio_to_set) > 0:
                self._logger.info("Setting aio values: {0}".format(aio_to_set))
                self.aio.get_token(calling_obj=self.__class__.__name__,
                                   override=False,**kwargs)
                self.aio.set(aio_to_set)
                self.aio.tokenRelease()
        else:
            # Need to try re-initializing the broker.
            self.aio.re_structure_data(connect_tries=1)
        if 'mm3' in self.broker_list:
            if hasattr(self,'mm3') is False:
                self.mm3 = self.context.mm3
            if self.mm3.initialized is False: # Need to try re-initializing the broker.
                self.mm3.re_structure_data(connect_tries=1)
                self.mm3.add_subscriptions(['current_limit', 'temp_fault'], on_change = True)
                self.mm3.add_callback({'current_limit' : self.current_limit_callback, 'temp_fault' : self.temp_fault_callback})
        if 'sonde' in self.broker_list:
            if hasattr(self,'sonde') is False:
                self.sonde = self.context.sonde
            if self.sonde.initialized is False: # Need to try re-initializing the broker.
                self.sonde.re_structure_data(connect_tries=1)
        if 'wind' in self.broker_list:
            if hasattr(self,'wind') is False:
                self.wind = self.context.wind
            if self.wind.initialized is False: # Need to try re-initializing the broker.
                self.wind.re_structure_data(connect_tries=1)
        if 'sounder' in self.broker_list: 
            if hasattr(self,'sounder') is False:
                self.sounder = self.context.sounder
            if self.sounder.initialized is False: # Need to try re-initializing the broker.
                self.sounder.re_structure_data(connect_tries=1)
        if 'gps' in self.broker_list:
            if hasattr(self,'gps') is False:
                self.gps = self.context.gps
            if self.gps.initialized is False: # Need to try re-initializing the broker.
                self.gps.re_structure_data(connect_tries=1)
        if 'isco' in self.broker_list:
            if hasattr(self,'isco') is False:
                self.isco = self.context.isco
            if self.isco.initialized is False and self.aio.power_ISCO.value == 1: # Need to try re-initializing the broker if it is on.
               self.isco.re_structure_data(connect_tries=1)
        if 'lisst' in self.broker_list:
            if hasattr(self,'lisst') is False:
                self.lisst = self.context.lisst
            if self.lisst.initialized is False and self.aio.power_LISST.value == 1: # Need to try re-initializing the broker if it is on.
               self.lisst.re_structure_data(connect_tries=1)
        if self._locInterface.running is False:
            self._locInterface.start()
    def _stopRunning(self, signal_number, *args):
        self._running = False
        self._logger.warning('Caught signal number {0}, shutting down.'.format(signal_number))
    def shutdown(self):
        self._logger.info("Unsubscribing from all broker data")
        try:        
            self._locInterface.shutdown()
        except AttributeError,TypeError:
            pass
        self._logger.info("disconnecting brokers")
        try:
            self.context.shutdown('all') # Sut down all brokers
        except AttributeError:
            pass
        self.notification.shutdown()
        sleep(1)
        thread_count = threading.active_count()
        self._logger.info("There are {0} remaining threads:{1}".format(threading.active_count(),threading.enumerate()))
        self._logger.info("shutting down logger")
        logging.shutdown()     # shutdown the logging system
        while threading.active_count() > 1:
            print threading.active_count(),"threads left"
            sleep(1)
        sys.exit(0)
    # Now callbacks
    def current_limit_callback(self, sample_dt, callback_obj, pv={'firstCall':True}):
        # Called on mm3 current limit fault.
        self.mm3.motor_cb(sample_dt,callback_obj) # This should stop the motor and generate a log message if appropriate.
        if callback_obj.value == 1:
            self._lcd.insert(3, 'Motor current limit shutdown  ', 'up')
        else:
            if pv['firstCall'] == False:
                self._logger.info('Motor current limit reset')
                self._lcd.insert(3, 'Motor current limit reset  ', 'up')
            else:
                pv['firstCall'] = False
    def temp_fault_callback(self, sample_dt, callback_obj, pv={'firstCall':True}):
        # Called on mm3 temperature fault.
        self.mm3.motor_cb(sample_dt,callback_obj) # This should stop the motor and generat a log message if appropriate.
        if callback_obj.value == 1:
            self._lcd.insert(3, 'Motor temp fault shutdown  ', 'up')
        else:
            if pv['firstCall'] == False:
                self._logger.info('Motor temp fault reset')
                self._lcd.insert(3, 'Motor temp fault reset  ', 'up')
            else:
                pv['firstCall'] = False

class BrokerInfo(object):
    '''
    Holds information about each broker that we manage
    '''
    def __init__(self,name='',pid=0):
        self.name = name
        self.pid = pid
        
class Passer(object):
    ''' Takes the place of a real LCD if we don't have one
    '''
    def __init__(self,*args,**kwargs):
        pass
    def __getattr__(self,*args,**kwargs):
        pass
    def __setattr__(self,*args,**kwargs):
        pass
    
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print 'Usage: ', sys.argv[0], ' ini-file'
        sys.exit(1)
    if os.path.exists(sys.argv[1]) is False:
        print sys.argv[1], "does not exist"
        sys.exit(1)

    try:
        logger = logging.getLogger('')
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

        config = ConfigObj(sys.argv[1])  # Read the config file
        dbh = avp_db.DB_LogHandler(config)
        dbh.setLevel(logging.DEBUG)
        logger.addHandler(dbh)
        s = Supervisor(program_name='supervisor', debug_mode=False)
        s.main_loop()
    except KeyboardInterrupt:
        s.shutdown()



