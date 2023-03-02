#! /usr/bin/env python
# -------------------------------------------------------------------------------
# Name:        supervisor
# Purpose:     Monitors processes and system resources in an effort to keep the entire system running.
#
# Author:      whipple
#
# Created:     01/02/2012
# -------------------------------------------------------------------------------
# Built in Modules
from collections import deque
from datetime import datetime, timedelta
import logging
import os
import signal
import socket
from subprocess import Popen, PIPE
import sys
import threading
from time import sleep, strptime
# Installed Modules
from configobj import ConfigObj
# if os.name is 'posix':
import psutil
import pytz
# Custom Modules
import avp_db
import avp_power
import avp_sched
import avp_util
import gislib
import notification
# import pertd2


def dump(obj):
    for attr in dir(obj):
        print("obj.%s = %s" % (attr, getattr(obj, attr)))


class Supervisor(object):
    def __init__(self, program_name=__name__, **kwargs):
        """This is the main Class for monitoring profiler health."""
        self.program_name = program_name
        self._running = True
        # catch some signals and perform an orderly shutdown
        signal.signal(signal.SIGTERM, self._stop_running)
        signal.signal(signal.SIGHUP, self._stop_running)
        # signal.signal(signal.SIGINT,  self._stop_running)
        signal.signal(signal.SIGQUIT, self._stop_running)
        signal.signal(signal.SIGILL, self._stop_running)
        signal.signal(signal.SIGABRT, self._stop_running)
        signal.signal(signal.SIGFPE, self._stop_running)
        signal.signal(signal.SIGSEGV, self._stop_running)
        # Read the config file
        self._config = ConfigObj(sys.argv[1])  
        self.HOME_PATH = self._config.get('supervisor', {}).get('HOME_PATH', '/home/avp')
        self.LOG_PATH = self._config.get('supervisor', {}).get('LOG_PATH', self.HOME_PATH + '\log')
        self.CHECK_FREQ = int(self._config.get('supervisor', {}).get('CHECK_FREQ', 1))
        self.LOG_FREQ = int(self._config.get('supervisor', {}).get('LOG_FREQ', 1))
        self.LOCAL_INTERFACE = avp_util.t_or_f(self._config.get('supervisor', {}).get('LOCAL_INTERFACE', True))
        # Time in sec to sleep after starting aio for the first time
        self.POST_AIO_BROKER_SLEEP = float(self._config.get('supervisor', {}).get('POST_AIO_BROKER_SLEEP', 5))
        # There is a bug where strptime will give an attribute error when first used in a new thread.
        # Supposedly using it from the main thread first will keep this from happening.
        strptime("20110131", "%Y%m%d")
        # set up logging with a root level logger
        self._logger = logging.getLogger(self.__class__.__name__)
        # Set up notifications
        self.notification = notification.Notification(self._config)
        self.notification.start()
        # some startup messages
        self._logger.info('Starting AVP System Supervisor')
        # set the environment variable required for the aio broker to run
        try:
            os.environ['LD_LIBRARY_PATH'] = self._config['aio']['LD_LIBRARY_PATH']
        except KeyError as e:
            self._logger.critical('Error finding configuration key '+str(e))
            sys.exit(1)
        # Do some database things....
        power_table = self._config['db'].get('POWER_TABLE', '{0}_power'.format(socket.gethostname()))
        self.power_db = avp_db.AvpDB(self._config, power_table)
        # time of most recent warning issued by gps or compass (set to ten minutes ago)
        self.latq = deque([])  # list from which the averages are taken
        self.lonq = deque([])  # list from which the averages are taken
        self.latlontimeq = deque([])  # list of associated times
        self.gpsWarnTime = datetime.now(pytz.reference.LocalTimezone()) - timedelta(seconds=600)
        self.compassWarnTime = datetime.now(pytz.reference.LocalTimezone()) - timedelta(seconds=600)
        self.loops = 0 # Reset to 0 on any broker start so that we don't start scheduler too soon.
        self.log_items = {} # Will hold field:value pairs to insert into database
        self.py_processes = {}
        
    def _initialize_broker_clients(self):
        self._logger.debug('_initialize_broker_clients')
        # ['aio','gps','sonde','wind','sounder','isco','lisst','mm3','powerMon']
        self.broker_list = list(self._config.get('supervisor', {}).get('brokerList', {}).values())
        self.context = avp_util.AVPContext(self._config, startup=self.broker_list, program_name=self.program_name,
                                           debug_mode=False) # Set up console context
        try:
            self.aio = self.context.aio
            self._logger.debug('Instantiating AIO broker')
        except AttributeError as e:
            self._logger.critical('Unable to instantiate AIO broker: {0}'.format(e))
        # To monitor schedule status
        self.schedule_status = avp_sched.AVPScheduleStatus(self._config, debug_mode=False)

    def main_loop(self, **kwargs):
        """Main routine. Loops while running"""
        check_cs = True
        hostname = socket.gethostname()
        self.py_processes['sched'] = {'search_str': 'avp_sched.py',
                                      'spawn_str': '/home/avp/python/avp_sched.py',
                                      'args': '-c /home/avp/python/{hostname}_avp.ini'.format(hostname=hostname),
                                      'pid': None,
                                      'old_pid': None,
                                      'root': False}
        self.py_processes['ping_test'] = {'search_str': 'ping_test.py',
                                          'spawn_str': '/home/avp/python/ping_test.py',
                                          'args': '/home/avp/python/{hostname}_avp.ini'.format(hostname=hostname),
                                          'pid': None,
                                          'old_pid': None,
                                          'root': False}
        self.py_processes['Local_Interface'] = {'search_str': 'Local_Interface',
                                                'spawn_str': '/home/avp/python/Local_Interface.py',
                                                'args': '/home/avp/python/{hostname}_avp.ini'.format(hostname=hostname),
                                                'pid': None,
                                                'old_pid': None,
                                                'root': False}
        while self._running:
            if datetime.now(pytz.reference.LocalTimezone()).second == 0 or check_cs is True:
                if datetime.now(pytz.reference.LocalTimezone()).minute % self.CHECK_FREQ == 0 or check_cs is True:
                    self._check_serial()    # check and set up the serial ports
                    self._check_java_brokers()   # check the brokers
                    if self.loops >= 1:  # Skip the first loop to give brokers time to get going.
                        if hasattr(self, 'aio') is False:   # Skip the first loop to give brokers time to get going.
                            self._initialize_broker_clients()
                        else:
                            self._logger.debug('aio initialized')
                        self._check_py_processes()  # Check python processes.
                    self._check_connections_and_subscriptions()   # Uses aio but returns if broker not yet instantiated
                    self._check_controller()
                    # Uses aio but returns if broker not yet instantiated
                    self._do_power_status()
                    self._gps_checks()
                    self._wind_checks()
                    self.loops += 1
                if datetime.now(pytz.reference.LocalTimezone()).minute % self.LOG_FREQ == 0:
                    self._do_env_logging()
            if self.loops == 1:
                sleep(20)   # TESTING
                # sleep(60)
            else:
                sleep(1)
                # Now check if any brokers have disconnected and re-check every 1second.
                check_cs = False
                for broker in self.context.brokers:
                    if getattr(self, broker).socket_handler.connected is False:
                        self._logger.warning('{0} broker is not connected'.format(broker))
                        check_cs = True
        self.shutdown()

    def _gps_checks(self):
        if hasattr(self, 'gps') is False:
            self._logger.debug('No GPS client yet, skipping _gps_checks')
            return
        elif self.gps.initialized is False:
            self._logger.debug('GPS client not initialized, skipping _gps_checks')
            return
        if self.gps.connected() is True:
            try:
                out_of_position_message = ''
                self.ANCHOR_WATCH_CENTER = (self.gps.ANCHOR_WATCH_LAT, self.gps.ANCHOR_WATCH_LON,)
            except KeyError as e:
                self._logger.warning('Error finding configuration key '+str(e))
                return
            # Check our GPS Position
            lat = None
            lon = None
            mode = None
            try:
                mode = self.gps.mode.value
                if mode == 3:   # only check gps for 3d fixes
                    self.latq.append(self.gps.lat.value)
                    self.lonq.append(self.gps.lon.value)
                    self.latlontimeq.append(self.gps.lat.sample_time)
                    # keep 900 seconds, and protect against bad data
                    if self.latlontimeq[-1] - self.latlontimeq[0] > timedelta(seconds=900) or \
                       self.latlontimeq[-1] - self.latlontimeq[0] < timedelta(seconds=0):
                        self.latq.popleft()
                        self.lonq.popleft()
                        self.latlontimeq.popleft()
                    lat = sum(self.latq) / len(self.latq)
                    lon = sum(self.lonq) / len(self.lonq)
            except Exception as e:
                print("Exception checking gps position: ", e)
            if mode == 3:   # only check gps for 3d fixes
                try:
                    if lat is not 'NaN' and lon is not 'NaN':
                        distance, bearing = gislib.get_distance_bearing(self.ANCHOR_WATCH_CENTER, (lat, lon))
                        self._logger.debug("GPS location is {0:d}m at {1:5.4} deg. "
                                           "from expected location.".format(int(distance*1000), bearing))
                        if distance > self.gps.ANCHOR_WATCH_RADIUS:
                            out_of_position_message += "{0:d}m at {1:5.4} deg. from expected " \
                                                       "location.".format(int(distance*1000), bearing)
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
                except Exception as e:
                    print("Failed to evaluate position from {0},{1} ({2})".format(lat, lon, e))
                if out_of_position_message and\
                        (datetime.now(pytz.reference.LocalTimezone()) >
                             (self.gpsWarnTime + timedelta(seconds=self.gps.WARNING_REPEAT_TIME))):
                    self._logger.warning('GPS position error: {0}'.format(out_of_position_message))
                    self.gpsWarnTime = datetime.now(pytz.reference.LocalTimezone())
        else:
            print("Skipping gps checks")

    def _wind_checks(self):
        """Tries checking our compass heading. Generates a warning if a problem is found"""
        if hasattr(self, 'wind') is False:
            self._logger.debug('No wind client yet, skipping _wind_checks')
            return
        elif self.wind.initialized is False:
            self._logger.debug('Wind client not initialized, skipping _wind_checks')
            return
        elif self.wind.connected() is True:
            heading = self.wind.compass_direction.value
            warning = False
            self._logger.debug('Profiler heading is {0}, target is {1}'.format(heading, self.wind.COMPASS_TARGET))
            cwlimit = self.wind.COMPASS_TARGET + self.wind.COMPASS_MARGIN 
            ccwlimit = self.wind.COMPASS_TARGET - self.wind.COMPASS_MARGIN
            # Make sure everything is between 0 and 360
            if cwlimit >= 360:
                cwlimit -= 360
            if cwlimit < 0:
                cwlimit += 360
            if ccwlimit >= 360:
                ccwlimit -= 360
            if ccwlimit < 0:
                ccwlimit += 360
            if datetime.now(pytz.reference.LocalTimezone()) > (self.compassWarnTime + timedelta(seconds=600)):
                if cwlimit < ccwlimit:
                    if ccwlimit > heading > cwlimit:
                        warning = True
                else:
                    if heading > cwlimit or heading < ccwlimit:
                        warning = True
            if warning is True:
                self._logger.warning('Platform heading of {0} indicates possible mooring problem'.format(heading))
                self.compassWarnTime = datetime.now(pytz.reference.LocalTimezone())
        else:
            print("Skipping compass checks")

    def _log_CPU_temp(self, temperature):
        """Logs CPU temperature, generates warning if too high.

        Keyword arguments:
        temperature -- The cpu temperature.
        """
        cpu_temp_threshold = float(self._config['supervisor'].get('CPU_TEMP_THRESHOLD', 60))
        self.log_items['temp_cpu'] = temperature
        cpu_message = 'CPU Temperature is {temp:.0f} deg C which is {range} the threshold of {cpu:.0f} degC'
        if temperature > cpu_temp_threshold:
            message = cpu_message.format(range='above', temp=temperature, cpu=cpu_temp_threshold)
            self._logger.warning(message)
        else:
            message = cpu_message.format(range='within', temp=temperature, cpu=cpu_temp_threshold)
            self._logger.debug(message)

    def _check_controller(self):
        """Checks controller attributes including:
            Root drive space
            Data drive space
            Memory usage
            CPU temperature
        """
        low_drive_threshold = float(self._config['supervisor'].get('LOW_DRIVE_THRESHOLD', 0.10))
        low_ram_threshold = float(self._config['supervisor'].get('LOW_RAM_THRESHOLD', 0.10))
        drives = {'root': {'mount': '/', 'field': 'disk_free_root'},
                  'database': {'mount': '/data', 'field': 'disk_free_data'}}
        for drive, info in list(drives.items()):
            if os.name is 'posix':
                s_drive = os.statvfs(info['mount'])
                drive_pct = float(s_drive.f_bavail) / s_drive.f_blocks
                self.log_items[info['field']] = drive_pct * 100
            else:
                drive_pct = 1
            drive_message = '{drive} drive free space is {r1} {pct:.1f}%,' \
                            'which is {r2} the threshold of {thresh:.1f}%'
            if drive_pct < low_drive_threshold:
                pct = drive_pct * 100
                thresh = low_drive_threshold * 100
                r1 = 'down to'
                r2 = 'below'
                self._logger.warning(drive_message.format(pct=pct, thresh=thresh, drive=drive, r1=r1, r2=r2))
            else:
                pct = drive_pct * 100
                thresh = low_drive_threshold * 100
                r1 = ''
                r2 = 'above'
                self._logger.debug(drive_message.format(pct=pct, thresh=thresh, drive=drive, r1=r1, r2=r2))
        # check percentage of available memory
        # mem = psutil.phymem_usage()
        # if os.name is 'posix':
        # free_memory_pct = float(mem.total - mem.used + psutil.cached_phymem()) / mem.total
        free = 100.0 - psutil.virtual_memory().percent
        # else:
        #   free_memory_pct = float(mem.total - mem.used) / mem.total
        self.log_items['free_memory'] = free
        mem_message = 'Free memory (non-cache) is {free:.1f}%, which is {range} the threshold of {thresh:.1f}%'
        if free < low_ram_threshold:
            self._logger.warning(mem_message.format(free=free, range='below', thresh=low_ram_threshold*100))
        else:
            self._logger.debug(mem_message.format(free=free, range='above', thresh=low_ram_threshold*100))
        # check CPU temperature
        if os.uname()[4] == 'armv7l':
            # On the RPi
            temp_deg_c = int(open('/sys/class/thermal/thermal_zone0/temp').read()) / 1e3
            self._log_CPU_temp(temp_deg_c)
        else:
            # On x68 systems
            process = Popen('sensors', stdout=PIPE)
            temp_deg_cstr = process.communicate()[0]
            process.wait()
            w = temp_deg_cstr.find('Core 0:')  # Find our line
            str_x = temp_deg_cstr[w:]  # and extract just this line
            y = str_x.find('+')  # Mark our extents
            z = str_x.find('\xc2')
            try:
                temp_deg_c = float(str_x[y:z])  # Extract and convert
                if temp_deg_c == 40.0:  # If the temperature == 40.0 it is actually something less than 40
                    message = 'CPU Temperature is < {0:.0f} deg C'.format(temp_deg_c)
                    self._logger.debug(message)
                else:
                    self._log_CPU_temp(temp_deg_c)
            except ValueError:
                message = 'Could not parse CPU Temp: {0}\n{1}\n{2}\n{3}\n{4}'.format(temp_deg_cstr, w, str_x, y, z)
                self._logger.debug(message)

    def _do_power_status(self):
        """Gets status of various power items:
        voltage
        one minute voltage (system voltage)
        charge current
        """

        if hasattr(self, 'aio') is False:
            self._logger.debug('No AIO client yet, skipping _doPowerStatusi686')
            return
        elif self.aio.initialized is False:
            self._logger.debug('AIO lient not initialized, skipping _doPowerStatusi686')
            return
        elif hasattr(self, 'power_obj') is False:
            self._logger.debug('power_obj not initialized, skipping _doPowerStatusi686')
            return
        try:
            low_amp_hours = float(self._config['supervisor'].get('LOW_AMP_HOURS', -100))
            low_batt_voltage = float(self._config['supervisor'].get('LOW_BAT_VOLTAGE', 11.2))
            shutdown_voltage = float(self._config['supervisor'].get('SHUTDOWN_VOLTAGE', 10.7))
            high_humidity = float(self._config['supervisor'].get('HIGH_HUMIDITY', 70))
        except KeyError as e:
            self._logger.critical('Error finding configuration key ' + str(e))
            sys.exit(1)
        # Get values
        load_amp_hours = self.load_current.amp_hours
        charge_amp_hours = self.charge_current.amp_hours
        system_voltage = self.voltage.one_min_ave
        charge_current = self.charge_current.one_min_ave
        load_current = self.load_current.one_min_ave
        net_charge = charge_amp_hours - load_amp_hours
        try:
            ambient_temp = self.mm3.temperature.value
        except AttributeError:
            ambient_temp = 0
        try:
            sensor__r_h = self.aio.humidity_ADC.value
            humidity = ((sensor__r_h / 5.0) - 0.16) / .0062  # This is what we log
            # This is derived from ambient_temp so can be calculated again in SQL
            corrected_humidity = humidity / (1.0546 - (0.00216 * ambient_temp))
            # humidity = max(humidity,100)
        except AttributeError:
            humidity = 0
            corrected_humidity = 0
        # Add to log dictionary
        self.log_items['system_voltage'] = system_voltage
        self.log_items['charge_current'] = charge_current
        self.log_items['charge_power'] = system_voltage * charge_current
        self.log_items['charge_current_max'] = self.charge_current.maximum
        self.log_items['charge_amp_hours'] = charge_amp_hours
        self.log_items['load_power'] = system_voltage * self.load_current.one_min_ave
        self.log_items['load_current_max'] = self.load_current.maximum
        self.log_items['load_current'] = load_current
        self.log_items['load_amp_hours'] = load_amp_hours
        self.log_items['humidity'] = humidity
        self.log_items['temp_ambient'] = ambient_temp
        # Report and log any values out of spec.
        if net_charge < low_amp_hours:
            self._logger.warning('Net charge: {0:.2f} Amp-Hours is less than the threshold of {1:.2f} Amp-Hours'.format(
                net_charge, low_amp_hours))
        else:
            self._logger.debug('Net charge: {0:.2f} Amp-Hours'.format(net_charge))
        if system_voltage < low_batt_voltage and system_voltage != 0:
            self._logger.warning('One min avg voltage: {0:.2f} V is less than the threshold'
                                 'of {1:.2f} V. Pausing schedule'.format(system_voltage, low_batt_voltage))
            # Suspend casting while voltage is too low
            if self.schedule_status.state == 'on': 
                self._logger.warning('Pausing schedule due to low voltage')
            # This will just extend the pause time, but no need for another message.
            self.schedule_status.state = 'paused'
        if humidity >= high_humidity:
            self._logger.warning('Humidity: {0:.2f}% ({1:.2f} temperature corrected) is greater than the warning level'
                                 ' of {2:.2f}%'.format(humidity, corrected_humidity, high_humidity))
     
        # If the voltage gets too low the solar charger won't be able to recharge the batteries.
        # When we get close to that threshold, we will shut the sytem down via the power relay.
        # This will require an operator to start the system manually by re-energizing the power relay
        # through the modem using the at+bdoset=do1,0 command.
        if (system_voltage < shutdown_voltage) and (system_voltage != 0):
            self._do_env_logging()
            self._logger.critical('One min avg voltage: {0:.2f} V is less than the shutdown threshold of'
                                  ' {1:.2f} V'.format(system_voltage, shutdown_voltage))
            self._logger.critical('VERY LOW VOLTAGE: {0}V. SYSTEM SHUTTING DOWN VIA POWER RELAY'.format(system_voltage))
            self._logger.critical('VERY LOW VOLTAGE: {0}V. SYSTEM SHUTTING DOWN VIA POWER RELAY'.format(system_voltage))
            self._logger.critical('VERY LOW VOLTAGE: {0}V. SYSTEM SHUTTING DOWN VIA POWER RELAY'.format(system_voltage))
            self.notification.notify_now()
            # SHUTDOWN THE SYSTEM
            # subprocess.Popen(['sudo','/home/avp/bin/postgres_shutdown.sh'],shell=False,stdout=subprocess.PIPE)
            new_daemon = self.HOME_PATH + '/bin/suicide_shutdown.sh'
            stdout = self.LOG_PATH + '/suicide_shutdown.log'
            stderr = self.LOG_PATH + '/suicide_shutdown.log'
            try:
                avp_util.spawnDaemon(new_daemon.split(), stdout=stdout, stderr=stderr)
            except SystemExit:
                pass    # the child process will exit as part of creating a daemon process

    def _do_env_logging(self):
        self.log_items['sample_time'] = datetime.now(pytz.reference.LocalTimezone())
        self.power_db.buffered_insert(self.log_items)
        self.log_items.clear()

    def _check_serial(self):
        """Check serial ports and try to set correct baud rate."""
        self._logger.debug('Checking serial ports')
        try:
            # check and/or set the baud rates on the serial ports
            serial_devices = self._config['serial']['SERIAL_DEVICES']
            serial_bauds = self._config['serial']['SERIAL_BAUDS']
        except KeyError as e:
            self._logger.critical('Error finding configuration key ' + str(e))
            sys.exit(1)

        for device, baud in zip(serial_devices, serial_bauds):
            # User must be a member of group dialout for this to work
            d_speed = os.popen("stty -F " + device + " speed").read().rstrip('\n')
            if d_speed != baud:
                self._logger.info("Baud rate mis-match. Calling: stty -F {0} {1}".format(device, baud))
                os.popen("stty -F {0} {1}".format(device, baud))

    def _check_py_processes(self):
        """Checks for the following python processes and instantiates them as necessary:
        Scheduler
        Ping Test
        Local Interface
        """
        try:
            for py_process, pp_info in list(self.py_processes.items()):
                pp_info['old_pid'] = pp_info['pid']
                pp_info['pid'] = None
                search_str = str(pp_info['search_str'])
                try:
                    for process in psutil.process_iter():
                        if psutil.version_info[0] > 1:
                            cmdline = process.cmdline()
                        else:
                            cmdline = process.cmdline
                        # print "Looking for {0} in {1}".format(search_str,' '.join(cmdline))
                        if search_str in ' '.join(cmdline):
                            pp_info['pid'] = process.pid
                            # print(("FOUND {0} in {1}".format(pp_info['search_str'],' '.join(cmdline))))
                            break
                except Exception as e:
                    print(e)
                    pp_info['pid'] = pp_info['old_pid']
                    continue
            try:
                for py_process, pp_info in list(self.py_processes.items()):
                    if pp_info['pid'] is None:
                        if pp_info.get('root', False) is False:
                            # Re-spawn
                            os.chmod(pp_info['spawn_str'], 0o770)  # Make sure it is executable
                            new_daemon = "{0} {1}".format(pp_info['spawn_str'], pp_info['args'])
                            if pp_info['old_pid'] is None:
                                self._logger.info('Spawning: {0}'.format(new_daemon))
                            else:
                                self._logger.warning('Re-spawning: {0}'.format(new_daemon))
                            stdout = '{0}/{1}.log'.format(self.LOG_PATH, py_process)
                            avp_util.spawnDaemon(new_daemon.split(), stdout=stdout, stderr=stdout)
                        else:
                            self._logger.warning('{0} process is not running. '
                                                 'Can only be started by root.'.format(py_process))
                    else:
                        self._logger.debug('Found {0} python process'.format(py_process))
            except Exception as e:
                print("_check_py_processes respawn {0}".format(e))
        except Exception as e:
            print("_check_py_processes psutil{0}".format(e))

    def _check_java_brokers(self):
        """Tests for existence and status of all necessary brokers and instantiates them if necessary."""
        self._logger.debug('Checking broker processes')
        broker_info_list = []
        super_config = self._config.get('supervisor', {})
        try:
            broker_list = super_config['brokerList']
            rel_file = super_config.get('RELEASE_NUMBER_FILE')  # No longer used
            if os.path.isfile(rel_file) is False:
                # If version file doens't exist, we're probably using new maven style broker.
                broker_version = None
            else:
                with open(rel_file, "r") as f:
                    broker_version = f.read()
            java_install_dir = super_config.get('JAVA_INSTALL_DIR')
            if broker_version is not None:
                java_install_dir += broker_version.strip()
            java_arg = super_config.get('JAVA_ARG', '')
            javp_jar = super_config.get('JAVP_JAR')
            if broker_version is not None:
                javp_jar += broker_version.strip()
            # Need to see if there is a * in javp_jar and if so, take care of it.
            if '*' in javp_jar:
                import glob
                infile = "{path}{file}".format(path=java_install_dir, file=javp_jar)
                javp_jar = glob.glob(infile)[0]
            json_jar = super_config.get('JSON_JAR')
            if json_jar == "None":
                json_jar = None
            postgres_jar = super_config.get('POSTGRES_JAR')
            if postgres_jar == "None":
                postgres_jar = None
        except KeyError as e:
            self._logger.critical('Error finding configuration key '+str(e))
            sys.exit(1)
        # Set up a data structure for each broker in the broker list
        for broker in list(broker_list.keys()):
            # Strip off the '.conf' # COULD THIS BE DONE MORE SIMPLY WITH A DICTIONARY?
            broker_info_list.append(BrokerInfo(name=broker[:-5]))
            confpath = '../lib/{hostname}'.format(hostname=socket.gethostname())
            if broker_version is not None:
                confpath = 'bin'
            # Look for brokers by name in the process status list
            try:    # process_iter can throw an exception
                for process in psutil.process_iter():
                    # processes can disappear -- make local copies of process info
                    try:
                        if psutil.version_info[0] > 1:
                            cmdline = process.cmdline()
                        else:
                            cmdline = process.cmdline
                        pid = process.pid
                    except Exception:
                        continue    # if the process is gone just move on to the next one
                    cmd = '{0}/{confpath}/{1}'.format(java_install_dir, broker, confpath=confpath)
                    if cmd in cmdline:
                        self._logger.debug('Found broker ' + str(broker))
                        broker_info_list[-1].pid = pid
                        # will broker respond to a request
                        # The names in broker are not generic.  brokerList is a dictionary that maps to generic names.
                        if hasattr(self, broker_list[broker]):
                            if getattr(self, broker_list[broker]).connected() is True:
                                try:
                                    # what will this really do, timeout?
                                    if len(getattr(self, broker_list[broker]).list_data()) < 1:
                                        l_data = getattr(self, broker_list[broker]).list_data()
                                        self._logger.debug("list_data: {}".format(l_data))
                                        self._logger.debug("len: {}".format(len(l_data)))
                                        # Broker is not responding
                                        self._logger.warning('Broker {0} not responding.'
                                                             'Killing for restart.'.format(broker))
                                        getattr(self, '_' + broker_list[broker]).disconnect()
                                        if os.name is 'posix':
                                            os.kill(pid, signal.SIGTERM)
                                        broker_info_list[-1].pid = 0     # Mark the broker as needing startup
                                except Exception as e:
                                    self._logger.warning('Broker {0} not responding -'
                                                         ' threw exception {1}. Killing for restart.'.format(broker, e))
                                    getattr(self, '_'+broker_list[broker]).disconnect()
                                    if os.name is 'posix':
                                        os.kill(pid, signal.SIGTERM)
                                    broker_info_list[-1].pid = 0     # Mark the broker as needing startup
                            else:
                                # we aren't connected
                                self._logger.debug("Supervisor broker {0} not connected".format(broker_list[broker]))
                        else:
                            # we don't have this attribute in Supervisor.
                            self._logger.debug("Supervisor doesn't have broker {0}".format(broker_list[broker]))
            except Exception:
                """If something goes wrong, just keep going.  The most likely thing to catch here is when a process
                disappears while we are iterating through the list. This should be a bit more specific, catching only 
                the exceptions we expect."""
                continue
            if broker_info_list[-1].pid == 0:     # broker was not found, let's start it up
                first_start = True
                # broker was not found, see if we need to disconnect
                if hasattr(self, broker_list[broker]) and getattr(self, broker_list[broker]).connected() is True:
                    self._logger.warning('Broker process {0} missing after having been connected.'.format(broker))
                    first_start = False
                new_daemon = '/usr/bin/java {arg} -cp {javp}'.format(arg=java_arg, dir=java_install_dir, javp=javp_jar)
                if json_jar is not None:
                    new_daemon += ':{dir}{json}'.format(dir=java_install_dir, json=json_jar)
                if postgres_jar is not None:
                    new_daemon += ':{pgj}'.format(pgj=postgres_jar)
                new_daemon += ' edu.unc.ims.avp.Broker '
                new_daemon += '{dir}/{confpath}/db.conf {dir}/{confpath}/{broker}'.format(dir=java_install_dir, confpath=confpath,
                                                                               broker=broker)
                self._logger.info('Spawning: {0}'.format(new_daemon))
                # To name the log files we will add .log
                # This assumes that the names in broker end in .conf
                stdout = '{0}/{1}.log'.format(self.LOG_PATH, broker_list[broker])
                stderr = stdout
                avp_util.spawnDaemon(new_daemon.split(), stdout=stdout, stderr=stderr)
                if broker_list[broker] == 'aio' and first_start is True:
                    # If we're starting aio for the first time, give it time to start before starting other brokers
                    self._logger.debug('First aio startup, {d}s delay'.format(d=self.POST_AIO_BROKER_SLEEP))
                    sleep(self.POST_AIO_BROKER_SLEEP)
                self.loops = 0

    def _check_connections_and_subscriptions(self, **kwargs):
        """set up brokers. If we just started the aio broker it may be a few seconds before we can connect."""
        if hasattr(self, 'aio') is False:
            self._logger.debug('No aio or io broker client yet, skipping _check_connections_and_subscriptions')
            return
        if self.aio.initialized is True:
            if hasattr(self, 'power_obj') is False:
                # Look in power_db for most recent ah value
                last_env_dt = self.power_db.select(columns=('max(sample_time)',))[0][0]
                d_now = datetime.now()
                try:
                    if (last_env_dt.year == d_now.year and
                                last_env_dt.month == d_now.month and last_env_dt.day == d_now.day):
                        where_condition = {'sample_time': last_env_dt}
                        last_ah = self.power_db.select(columns=('load_amp_hours', 'charge_amp_hours', ),
                                                       where_condition=where_condition,
                                                       where_oper='=')[0]
                        last_load_ah, last_charge_ah = last_ah
                    else:  # It's a new day
                        last_load_ah = last_charge_ah = 0
                except AttributeError:
                    # The table may be empty
                    last_load_ah = last_charge_ah = 0
                self.power_obj = avp_power.AVP_Power(self.aio, self._config, last_load_ah, last_charge_ah)
                self.charge_current = self.power_obj.charge_current
                self.load_current = self.power_obj.load_current
                self.voltage = self.power_obj.voltage
            # Check aio default settings
            aio_defaults = {} 
            aio_to_set = {}
            for pin, desired_value in list(aio_defaults.items()):
                aio_value = getattr(self.aio, pin).value
                if aio_value != desired_value:
                    aio_to_set[pin] = desired_value
            if len(aio_to_set) > 0:
                self._logger.info("Setting aio values: {0}".format(aio_to_set))
                self.aio.get_token(calling_obj=self.__class__.__name__,
                                   override=False, **kwargs)
                self.aio.set(aio_to_set)
                self.aio.tokenRelease()
        else:
            # Need to try re-initializing the broker.
            self.aio.re_structure_data(connect_tries=1)
        if 'mm3' in self.broker_list:
            if hasattr(self, 'mm3') is False:
                self.mm3 = self.context.mm3
            if self.mm3.initialized is False:  # Need to try re-initializing the broker.
                self.mm3.re_structure_data(connect_tries=1)
                self.mm3.add_subscriptions(['current_limit', 'temp_fault'], on_change=True)
        if 'sonde' in self.broker_list:
            if hasattr(self, 'sonde') is False:
                self.sonde = self.context.sonde
            if self.sonde.initialized is False:  # Need to try re-initializing the broker.
                self.sonde.re_structure_data(connect_tries=1)
        if 'wind' in self.broker_list:
            if hasattr(self, 'wind') is False:
                self.wind = self.context.wind
            if self.wind.initialized is False:  # Need to try re-initializing the broker.
                self.wind.re_structure_data(connect_tries=1)
        if 'sounder' in self.broker_list: 
            if hasattr(self, 'sounder') is False:
                self.sounder = self.context.sounder
            if self.sounder.initialized is False:  # Need to try re-initializing the broker.
                self.sounder.re_structure_data(connect_tries=1)
        if 'gps' in self.broker_list:
            if hasattr(self, 'gps') is False:
                self.gps = self.context.gps
            if self.gps.initialized is False:  # Need to try re-initializing the broker.
                self.gps.re_structure_data(connect_tries=1)
        if 'isco' in self.broker_list:
            if hasattr(self, 'isco') is False:
                self.isco = self.context.isco
            # Need to try re-initializing the broker if it is on.
            if self.isco.initialized is False and self.aio.relay_ISCO.value == self.aio.RELAY_ON:
                self.isco.re_structure_data(connect_tries=1)
        if 'lisst' in self.broker_list:
            if hasattr(self, 'lisst') is False:
                self.lisst = self.context.lisst
            # Need to try re-initializing the broker if it is on.
            if self.lisst.initialized is False and self.aio.relay_LISST.value == self.aio.RELAY_ON:
                self.lisst.re_structure_data(connect_tries=1)

    def _stop_running(self, signal_number, *args):
        self._running = False
        self._logger.warning('Caught signal number {0}, shutting down.'.format(signal_number))

    def shutdown(self):
        self._logger.info("Unsubscribing from all broker data")
        self._logger.info("disconnecting brokers")
        try:
            self.context.shutdown('all')  # Shutdown all brokers
        except AttributeError:
            pass
        self.notification.shutdown()
        sleep(1)
        self._logger.info("There are {0} remaining threads:{1}".format(threading.active_count(),threading.enumerate()))
        self._logger.info("shutting down logger")
        logging.shutdown()     # shutdown the logging system
        while threading.active_count() > 1:
            print((threading.active_count(),"threads left"))
            sleep(1)
        sys.exit(0)

    # Now callbacks

    def current_limit_callback(self, sample_dt, callback_obj, pv={'firstCall':True}):
        # Called on mm3 current limit fault.
        # This should stop the motor and generate a log message if appropriate.
        self.mm3.motor_cb(sample_dt, callback_obj)

    def temp_fault_callback(self, sample_dt, callback_obj, pv={'firstCall':True}):
        # Called on mm3 temperature fault.
        # This should stop the motor and generate a log message if appropriate.
        self.mm3.motor_cb(sample_dt, callback_obj)


class BrokerInfo(object):
    """Holds information about each broker that we manage."""
    def __init__(self, name='', pid=0):
        self.name = name
        self.pid = pid


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: ', sys.argv[0], ' ini-file')
        sys.exit(1)
    if os.path.exists(sys.argv[1]) is False:
        print(sys.argv[1], "does not exist")
        sys.exit(1)
    try:
        logger = logging.getLogger('')
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG,
                            format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        config = ConfigObj(sys.argv[1])  # Read the config file
        dbh = avp_db.DB_LogHandler(config)
        dbh.setLevel(logging.DEBUG)
        logger.addHandler(dbh)
        sup = Supervisor(program_name='supervisor', debug_mode=False)
        sup.main_loop()
    except KeyboardInterrupt:
        sup.shutdown()
