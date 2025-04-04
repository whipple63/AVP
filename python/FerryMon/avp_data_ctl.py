#!/usr/bin/python

#Built in Modules

from datetime import datetime, timedelta
import logging
import signal
import sys
import time
#Installed Modules
import pytz.reference 
#Custom Modules
import avp_db
# Installed Modules
from configobj import ConfigObj
import os
from time import sleep
import gislib
import avp_broker
from shapely.geometry import Point, Polygon, LineString
import numpy as np

class Transect(object):
    ''' 
    Performs sonde transect
    
    see __init__ for arguments.
    Public Methods:
        setup
        pre_transect
        wait
        do_transect
        finish_transect
    '''
    REQUIRED_SONDE_SUBSCRIPTIONS = ['sampling',   # Is sonde in sampling (run) mode?*
                                    'logging']      # Are we logging to the database
    REQUIRED_GPS_SUBSCRIPTIONS = ('lat','lon','mode')
    REQUIRED_FLOW_SUBSCRIPTIONS = ['flowrate', 'flowrate_mean30']
    WIPE_TIMEOUT = 240  # If we're still wiping after this many seconds, abort transect.
    
    def __init__(self,program_name=__name__,**kwargs):
        '''
        Initializes Transect attributes, including databases and config values
        '''
        
        self.config = ConfigObj(sys.argv[1])
        self.program_name = program_name
        self.debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__) # set up logging
        self.transects_started = 0
        self.transects_completed = 0
        
    def pre_config(self, transect_time=datetime.now(pytz.reference.LocalTimezone()), transect_number=None,
                   wipe=True, load_config=False, **kwargs):
        '''
        Set up all the per-transect parameters.        
        Keyword Arguments:
            transect_number  -- Defaults to the last transect number + 1
            transect_time    -- When to transect. Defaults to now.
            wipe         -- Do we wipe the sonde before the transect. Defaults to True
            load_config -- Call load_config(reload_config=True) for every broker just in case avp.ini has changed.
        '''
        self.transect_number = transect_number
        self.transect_time = transect_time
        self.wipe = wipe
        self.debug_mode = kwargs.get('debug_mode',False)
        self.logger.debug('Transect.pre_config')
        if load_config is True: # re-read the config file in case it has changed.
            for broker_name in self.context.brokers:
                this_broker = getattr(self.context,broker_name)
                this_broker.load_config(reload_config=True,debug_mode=self.debug_mode)
        # Now some defaults
        self.abort_transect = {} # {type:hard|soft,reason:<description>}
        self._get_brokers()
        
    def _get_brokers(self):
        # get sonde broker
        self.sonde = avp_broker.SondeBroker(config)
        self.gps = avp_broker.GpsBroker(config)
        self.flow = avp_broker.FlowBroker(config)
        
    def start_transect(self, **kwargs):
        self.logger.debug('Transect.start_transect');
        self.abort_transect = {}
        result = {}
		
		# increment the transect number if it has already been set
        if self.transect_number:
            self.transect_number = self.transect_number + 1
			
		
        result['01 get_tokens'] = self.get_tokens()
        result['02 check_instrument_status'] = self.check_instrument_status()
        self.logger.info("Turning on water valve")
        self.flow.water_on()	# open the valve (if it exists)
        result['03 wipe_sensor'] = self.wipe_sensor()
        result['04 init_instruments'] = self.init_instruments()		# this starts sonde sampling
        result['05 init_db'] = self.init_db()     
        result['06 start_logging'] = self.start_logging()
        if self.abort_transect:
            self.logger.error('Transect.start_transect aborted.  Trying a second time.')
            time.sleep(5) 	# give it some time
            self.abort_transect = {}
            result = {}
		
            result['01 get_tokens'] = self.get_tokens()
            result['02 check_instrument_status'] = self.check_instrument_status()
            self.logger.info("Turning on water valve")
            self.flow.water_on()	# open the valve (if it exists)
            result['03 init_instruments'] = self.init_instruments()
            result['04 init_db'] = self.init_db()     
            result['05 wipe_sensor'] = self.wipe_sensor()
            result['06 start_logging'] = self.start_logging()
        if self.abort_transect:
            transect_started = False
        else:
            transect_started = True
            self.check_flow_rate()		# must be run after check_instrument_status and init_db, issues warning if out of range
			
        return transect_started

    def check_flow_rate(self, **kwargs):
        flowrate = self.flow.flowrate_mean30.value
        if flowrate < self.flow.LOW_THRESH:
            self.logger.warn("Flow rate {0} lower than threshold of {1} for transect {2}.".format(flowrate, self.flow.LOW_THRESH, self.transect_number))
        if flowrate > self.flow.HI_THRESH:
            self.logger.warn("Flow rate {0} higher than threshold of {1} for transect {2}.".format(flowrate, self.flow.HI_THRESH, self.transect_number))	
		#self.config['flow']['constants']['LOW_THRESH']
        return
	
    def get_tokens(self,**kwargs):
        if self.abort_transect: return {}
        self.logger.debug('Transect.get_tokens')
        result = {}
        result['01 sonde.get_token'] = self.sonde.get_token(calling_obj=self.__class__.__name__,
                                           program_name=self.program_name, override=True,debug_mode=self.debug_mode)
        if self.debug_mode: print("    Sonde token acquire result:{0}".format(result['01 sonde.get_token']['acquire_result']))
        if 'error' in result['01 sonde.get_token'].get('acquire_result',None):
            self.abort_transect['type'] = 'soft'
            self.abort_transect['reason'] = 'Aborting Transect {0}. Unable to acquire sonde token.'.format(self.transect_number)
            self.logger.critical(self.abort_transect['reason'])
            return result
        return result

    def check_instrument_status(self,**kwargs):
        '''
        Makes sure required brokers are connected to their instruments and resumes them as necessary
        Returns:
            dict. 
                {} = already aborted transect
                {{action}{action_result}...}
        Raises:
            None
        '''
        if self.abort_transect: return {}
        self.logger.debug('Transect.check_instrument_status')
        result = {}
        # Check Sonde connection:
        result['01 sonde.broker_status 1'] = self.sonde.broker_status(timeout=None,debug_mode=self.debug_mode)
        if self.sonde.instr_connected is False:
            result['02 sonde.resume_broker'] = self.sonde.resume_broker(timeout=None,debug_mode=self.debug_mode)
            result['03 sonde.broker_status 2'] = self.sonde.broker_status(timeout=None,debug_mode=self.debug_mode)
            if self.sonde.instr_connected is False:
                self.abort_transect['type'] = 'soft'
                self.abort_transect['reason'] = 'Aborting transect {0}. Sonde broker unable to connect to instrument'.format(self.transect_number)
                self.logger.critical(self.abort_transect['reason'])
        result['04 sonde.add_subscriptions'] = self.sonde.add_subscriptions(self.REQUIRED_SONDE_SUBSCRIPTIONS,on_change=True)
        result['05 gps.add_subscriptions'] = self.gps.add_subscriptions(self.REQUIRED_GPS_SUBSCRIPTIONS,on_change=True,verbose=False)
        result['06 flow.add_subscriptions'] = self.flow.add_subscriptions(self.REQUIRED_FLOW_SUBSCRIPTIONS,on_change=True,verbose=False)
        return result
        
    def init_instruments(self,**kwargs):
        '''
        make sure all brokers we need are connected to their instruments.
        Turn on Sonde sampling.
        '''
        if self.abort_transect: return {}
        self.logger.debug('Transect.init_instruments')
        result = {}
        if self.sonde.sampling.value != True: # Are we sampling?
            #print "a Starting sampling= {0}".format(self.sonde.sampling.value)
            result['01 sonde.start_sampling'] = self.sonde.start_sampling()
            try:
                if 'error' in result['01 sonde.start_sampling']:
                    self.abort_transect['type'] = 'soft'
                    self.abort_transect['reason'] = 'Aborting Transect{0}. Error starting sampling: {1}'.format(self.transect_number,result['01 sonde.start_sampling'])
                    self.logger.critical(self.abort_transect['reason'])
                else:
                    self.logger.debug("Started sonde sampling.")
            except Exception as e:
                result['02 error'] = e
                self.abort_transect['type'] = 'soft'
                self.abort_transect['reason'] = 'Failed to start sonde sampling: {0}'.format(result['02 error'])
                self.logger.critical(self.abort_transect['reason'])
        return result
    
    def init_db(self,**kwargs):
        '''
        Insert a record into the transect database, and get or assign the transect_number.
        '''
        if self.abort_transect: return {}
        self.logger.debug('Transect.init_db')
        result = {}
        set_values = {}
        try:
            self.transect_db = avp_db.TransectDB(self.config) # Instantiate database object
        except Exception as e:
            self.abort_transect['type'] = 'soft'
            self.abort_transect['reason'] = 'Error in Transect.init_db initializing Transect database: {0}'.format(e)
            self.logger.critical(self.abort_transect['reason'])
            return result
        if self.abort_transect: return result
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
        set_values['flow_rate'] = self.flow.flowrate_mean30.value
        result['01 set_values'] = set_values # Debugging
        result['02 transect_db.insert'] = self.transect_db.insert(set_values,**kwargs)
        try:
            db_transect_number = self.transect_db.transect_number(**kwargs).get('result',0)
        except Exception as e:
            self.abort_transect['type'] = 'soft'
            self.abort_transect['reason'] = 'Unable to get transect number from {0}. Aborting Transect: {1}'.format(result,e)
            self.logger.critical(self.abort_transect['reason'])
            return result
        if self.transect_number is None: # Automatically assign transect number. This is the default.
            self.transect_number = db_transect_number
        elif self.transect_number > db_transect_number:
            self.logger.info('Using requested transect number {0} instead of {1}.'.format(self.transect_number,db_transect_number))
        elif self.transect_number < db_transect_number:
            self.logger.warning('Requested transect number {0} < {1}. '.format(self.transect_number,db_transect_number))
            self.transect_number = db_transect_number
        return result
    
    def wipe_sensor(self,**kwargs):
        if self.abort_transect: return {}
        self.logger.debug('Transect.wipe_sensor')
        result = {}
        
        #Do we want to wipe?
        if self.wipe: 
            if self.sonde.sampling.value == True: 
                result['05 sonde.stop_sampling'] = self.sonde.stop_sampling()
            time.sleep(5)    # added by Tony because self.sampling.Value is not up to date yet
            result['06 sonde.wipe'] = self.sonde.wipe()
            self.logger.info('Starting sonde wipe procedure, {0} wipes left'.format(self.sonde.wipes_left.value))
            # Wait until the wiping is done
            wipe_start = datetime.now(pytz.reference.LocalTimezone())
            while self.sonde.wipes_left.value > 0:
                time.sleep(1)
                if datetime.now(pytz.reference.LocalTimezone()) - timedelta(seconds=self.WIPE_TIMEOUT) > wipe_start:
                    self.abort_transect['type'] = 'soft'
                    self.abort_transect['reason'] = 'Unknown Fault, still wiping after {0} sec. ({1})'.format(self.WIPE_TIMEOUT,self.sonde.wipes_left)
                    self.abort_transect['park'] = True
                    self.logger.critical(self.abort_transect['reason'])
                    return result
            if self.sonde.sampling.value != True:
                #print("c Starting sampling= {0}".format(self.sonde.sampling.value))
                result['07 sonde.start_sampling'] = self.sonde.start_sampling()
        else:
            result['08 wipe'] = 'no wipe requested'
        return result
    
    def start_logging(self,**kwargs):
        '''
        Get all instruements sampling to the db and ready to move.
        '''
        if self.abort_transect: return {}
        self.logger.debug('Transect.start_logging')
        self.gps.get_token(calling_obj=self.__class__.__name__, program_name=self.program_name, override=True,debug_mode=self.debug_mode)
        self.gps.set({'log_period':0.02})
        self.gps.tokenRelease(debug_mode=self.debug_mode)
        result = {}
        # Update transect time in database
        result['04 transect_db.start'] = self.transect_db.start(self.transect_number,debug_mode=self.debug_mode)
        # Start sonde logging to db
        result['05 sonde.start_logging'] = self.sonde.start_logging(self.transect_number,debug_mode=self.debug_mode)
        self.logger.info("Started sonde logging transect {0}: {1}".format(self.transect_number,result['05 sonde.start_logging']))
        return result
    
    def stop_sampling(self,**kwargs):
        '''
        Wait a little at the end of the transect to get more sonde data,then stop the sonde logging.
        '''
        self.logger.debug('Transect.stop_sampling')
        self.gps.get_token(calling_obj=self.__class__.__name__, program_name=self.program_name, override=True,debug_mode=self.debug_mode)
        self.gps.set({'log_period':2.0})
        self.gps.tokenRelease(debug_mode=self.debug_mode)
        result = {}
        #Stop logging sonde data
        result['03 sonde.stop_logging'] = self.sonde.stop_logging(timeout=None,debug_mode=self.debug_mode)
        self.logger.debug("Stopped sonde logging: {0}".format(result['03 sonde.stop_logging']))
        return result
    
    def finish_transect(self,**kwargs):
        ''' Finish up transect. These are things which should be done even if the transect has been aborted.
        '''
        self.logger.debug('Transect.finish_transect')
        result = {}
        self.stop_sampling()
        if self.sonde.sampling.value == True: # It should be still running.
            result['07 stop_sampling'] = self.sonde.stop_sampling(debug_mode=self.debug_mode)
        # unsubscribe everything else
        self.logger.info("Turning off water valve")
        self.flow.water_off()	# close the valve (if it exists)
        self.logger.info("Unsubscribing from all transect broker data")
        result['16 gps.unsubscribe_all'] = self.gps.unsubscribe_all(debug_mode=self.debug_mode)
        result['18 sonde.unsubscribe_all'] = self.sonde.unsubscribe_all(debug_mode=self.debug_mode)
        # Release all other tokens
        result['22 sonde.tokenRelease'] = self.sonde.tokenRelease(debug_mode=self.debug_mode)
        self.transect_db.finish()        # Close the database.
        if self.abort_transect == {}:
            self.transects_completed += 1
        return result

    def shutdown(self):
        self.gps.disconnect()
        self.sonde.disconnect()
        self.flow.disconnect()
            
class DataControl(object):
    def __init__(self, **kwargs):
        self._running = True
        # catch some signals and perform an orderly shutdown
        signal.signal(signal.SIGTERM, self._stop_running)
        signal.signal(signal.SIGHUP, self._stop_running)
        signal.signal(signal.SIGINT,  self._stop_running)
        signal.signal(signal.SIGQUIT, self._stop_running)
        signal.signal(signal.SIGILL, self._stop_running)
        signal.signal(signal.SIGABRT, self._stop_running)
        signal.signal(signal.SIGFPE, self._stop_running)
        signal.signal(signal.SIGSEGV, self._stop_running)
        # Read the config file
        self._config = ConfigObj(sys.argv[1])  
        # set up logging with a root level logger
        self._logger = logging.getLogger(self.__class__.__name__)
        # some startup messages
        self._logger.info('Starting FerryMon Data Controller')
        
        # get GPS broker
        self._get_gps_broker()        
    
    def _get_gps_broker(self):
        # get GPS broker
        self.gps = avp_broker.GpsBroker(config)
        self.gps.add_subscriptions(['lat','lon'],on_change=True,subscriber="avp_data_ctl")
        
    def _gps_checks(self):
        if hasattr(self, 'gps') is False:
            self._logger.debug('No GPS client yet, skipping _gps_checks')
        elif self.gps.initialized is False:
            self._logger.debug('GPS client not initialized, skipping _gps_checks')
        if self.gps.connected() is True:
            try:
                port_lat = self._config['data_ctl']['PORT_LAT']
                port_lon = self._config['data_ctl']['PORT_LON']
                port_radius = self._config['data_ctl']['PORT_RADIUS']  
                port_name = self._config['data_ctl']['PORT_NAME']
            except KeyError as e:
                self._logger.warning('Error finding configuration key '+str(e))
                return
            lat = None
            lon = None
            mode = None
            try:
                mode = self.gps.mode.value 
                if (mode == 3) or (mode == 2):   # only check gps for 3d fixes
                    lat = self.gps.lat.value
                    lon = self.gps.lon.value
            except Exception as e:
                print("Exception checking gps position: ", e)
            j = False
            if (mode == 3) or (mode == 2):   # only check gps for 3d fixes
                try:
                    if lat != 'NaN' and lon != 'NaN':
                        for i in range(len(port_lat)):
                            distance, bearing = gislib.get_distance_bearing((float(port_lat[i]),float(port_lon[i])), (lat, lon))
                            if distance < float(port_radius[i]): # add more parameters
                                self._logger.debug('Within Port: {0} at: {1:6.4f}, {2:6.4f} '.format(port_name[i], lat, lon) )
                                return False
                        
                        point = Point(lat, lon)
                        route = self.get_coordinates()
                        poly = Polygon(route)
                        #print(poly)
                        k = point.within(poly)
                        if k:
                            self._logger.debug('Within Sampling Range of expected route at: {0:6.4f}, {1:6.4f} '.format(lat, lon) )
                            return True
                        else:
                            self._logger.debug('Outside Sampling Range of expected route at: {0:6.4f}, {1:6.4f} '.format(lat, lon) )
                            return False
                           
                except Exception as e:
                    print("Failed to evaluate position from {0},{1} ({2})".format(lat, lon, e))
            else:
                self._logger.debug('GPS mode={0}.  Skipping gps checks.'.format(mode) )
            return j
                           
    def get_coordinates(self):
        route_lat = self._config['data_ctl']['ROUTE_LAT']
        route_lon = self._config['data_ctl']['ROUTE_LON']      
        route_width = self._config['data_ctl']['ROUTE_WIDTH']
        route1 = []
        route2 = []
        r_earth = 6378000
                
        for i in range(len(route_lat)):
            x1p = float(route_lat[i])*(2*np.pi/360)*r_earth
            y1p = float(route_lon[i])*(2*np.pi/360)*r_earth*np.cos(float(route_lat[0])*np.pi/180)
            route1.append((x1p,y1p))
            
        r = LineString(route1)
        poly = Polygon(r.buffer(float(route_width)))
        x = []
        y = []
        x,y = poly.exterior.coords.xy
                
        for i in range(len(x)):
            x2p = x[i]/((2*np.pi/360)*r_earth)
            y2p = y[i]/((2*np.pi/360)*r_earth*np.cos(float(route_lat[0])*np.pi/180))
            route2.append((x2p,y2p))
                    
        return route2
        
    def _stop_running(self, signal_number, *args):
        self._running = False
        self._logger.warning('Caught signal number {0}, shutting down.'.format(signal_number))
        
    def shutdown(self):
        self._logger.info("Unsubscribing from all broker data")
        self._logger.info("disconnecting brokers")
        try:
            self.gps.unsubscribe_all()
            self.gps.disconnect()
        except AttributeError:
            pass
        sleep(1)
        self._logger.info("shutting down logger")
        logging.shutdown()     # shutdown the logging system
        sleep(1)
        #sys.exit(0)
        
    def main_loop(self, **kwargs):
        transect_time = datetime.now(pytz.reference.LocalTimezone())
        transect = Transect(program_name='avp_data_ctl', debug_mode=False)
        transect.pre_config(transect_time=transect_time)
        transect_started = False
        gps_freq = self._config['data_ctl']['GPS_FREQ']
        while self._running:          
            if datetime.now(pytz.reference.LocalTimezone()).second % float(gps_freq) == 0:
                in_gps_range = self._gps_checks() #will be true or false depending on GPS check  
                if in_gps_range is True:
                    if transect_started is False:
                        self._logger.info('Transition from out to in of gps range - starting transect')
                        if transect.start_transect() is True:
                            transect_started = True
                    
                else:
                    #self._logger.debug('In Port, or Out of Sampling Range')
                    if transect_started is True:
                        self._logger.info('Transition from in to out of gps range - finishing transect')
                        transect.finish_transect()
                        transect_started = False
            
                if self.gps.socket_handler.connected is False:
                    self.GpsBroker.disconnect()
                    self._logger.warning('gps broker is not connected')
                    self._get_gps_broker()
            
            sleep(1)
        if transect_started is True:
            transect.finish_transect()
        transect.shutdown()
        self.shutdown()
                    

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
        
        dataCtl = DataControl(program_name='avp_data_ctl', debug_mode=False)
        dataCtl.main_loop()
    except KeyboardInterrupt:
        dataCtl.shutdown()           
    except Exception:
        print('Unhandled exception.  Shutting down.')    
        dataCtl.shutdown()
        sys.exit(1)
            
