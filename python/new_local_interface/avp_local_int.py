
#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        avp_local_int
# Purpose:     Provides operator interface to pertelian LCD readout
#
# Author:      Neve
#
# Created:     01/02/2012
#-------------------------------------------------------------------------------
#Built in Modules
import time
from datetime import datetime, timedelta
import logging
import subprocess
import sys
import threading
#Installed Modules
import pytz.reference 
#Custom Modules
import pertd2
#import avp_winch
'''
This is for a two button interface and displays data to the 4-line lcd.

Each button change of state starts a new thread beginning with the routine
upButtonCallback or downButtonCallback.  The callback routines decide whether
there was a button press or release, save the time and button value, then
call the appropriate routine.  Actions are also performed by the interface
based on a double press which is both buttons being pressed within a window of
time.  Long-press of the buttons also give different actions (motor control).
'''

class LocalInterface(threading.Thread):
    '''
    Provides local response to the up/down buttons including a menu system
    '''
    _DOUBLE_PRESS_DELAY = 0.1  # window which defines double press
    _LONG_PRESS_DELAY = timedelta(seconds=1)    # seconds
    _MENU_ITEMS = ['Sonde swap',
                  'Toggle schedule',
                  'Toggle WiFi',
                  'Show sonde data',
                  'Show wind data',
                  'Show depth data',
                  'Show power status',
                  'Exit interface']
    _AIO_DATA_ITEMS = ['up_button', 'down_button']
    _SONDE_DATA_ITEMS = ['depth_m', 'temp_C', 'sal_ppt', 'do_mgL', 'odo_mgL','chl_ugL', 'turbid_NTU','turbidPl_NTU']
    _WIND_DATA_ITEMS = ['wind_speed', 'wind_direction', 'average_wind_speed', 'compass_direction']
    _DEPTH_DATA_ITEMS = ['water_depth', 'water_depth_1minave', 'water_depth_working', 'water_temp_surface']

    def __init__(self, supervisor, **kwargs):
        self.supervisor = supervisor
        config = self.supervisor._config
        self._logger = logging.getLogger()
        super(LocalInterface,self).__init__()
        self.name = self.__class__.__name__
        self.program_name = self.supervisor.program_name
        self.running = False
        self._lcd = pertd2.Pertelian()
        self._lcd.delay_time(100000) # Set delay time to .1 a second
        self._lcd.clear_screen()
        self._lcd.write_line(3,' Welcome to AVP3  ',0)
        self._BUTTON_MOVE_SPEED = int(config.get(self.__class__.__name__,{}).get('BUTTON_MOVE_SPEED',20))
        SONDE_SWAP_DURATION = int(config.get(self.__class__.__name__,{}).get('SONDE_SWAP_DURATION',30))
        self.SONDE_SWAP_DURATION = timedelta(minutes=SONDE_SWAP_DURATION)
        WIFI_ON_INTERVAL = int(config.get(self.__class__.__name__,{}).get('WIFI_ON_INTERVAL',120))
        self.WIFI_ON_INTERVAL = timedelta(minutes=WIFI_ON_INTERVAL)
        # methods associated with each menu item
        self._menu_on = False
        self._menuFirstItem = 0
        self._menuSelectedItem = 0
        self._MENU_METHODS = (self._sondeSwap,
                             self._toggleSchedule,
                             self._toggleWiFi,
                             self._showSondeData,
                             self._showWindData, 
                             self._showDepthData,
                             self._showPowerStatus,
                             self._exitInterface)
        '''self.menu = {'Sonde swap':self._sondeSwap, # Future improvements..
                     'Toggle schedule':self._toggleSchedule,
                     'Toggle WiFi':self._toggleWiFi,
                     'Show sonde data':self._showSondeData,
                     'Show wind data':self._showWindData, 
                     'Show depth data'self._showDepthData,
                     'Show power status':self._showPowerStatus,
                     'Exit interface':self._exitInterface}'''
        self._upPressDT = datetime(2000,01,01).replace(tzinfo=pytz.reference.LocalTimezone())
        self._downPressDT = datetime(2000,01,01).replace(tzinfo=pytz.reference.LocalTimezone())
        self._isDoublePress = False
        self.wifi = WiFi(interface='wlan0')
        if self.wifi.status == 'on':
            self.wifi.off_time = datetime.now(pytz.reference.LocalTimezone()) + self.WIFI_ON_INTERVAL
        else:
            self.wifi.start()
        self._sondeSwap_time = datetime(2000,01,01).replace(tzinfo=pytz.reference.LocalTimezone())
        self._sondeSwap_inProgress = False
        
    def shutdown(self):
        self.running = False
        time.sleep(1)
        self._logger.debug("Shutting down {0:24} {1:2} threads left.".format(self.name,threading.active_count()))
        
    def start(self):
        """ By this time, the self.supervisor should have it's aio object set up, so we can now add callbacks.
        """
        self.aio = self.supervisor.context.aio
        self.sonde = self.supervisor.context.sonde
        self.wind = self.supervisor.context.wind
        self.sounder = self.supervisor.context.sounder
        self.mm3 = self.supervisor.context.mm3
        #self.winch = avp_winch.Winch(self.supervisor.context)
        self.voltage = self.supervisor.voltage
        self.loadCurrent = self.supervisor.load_current
        self.chargeCurrent = self.supervisor.charge_current
        self.schedule_status = self.supervisor.schedule_status
        self.aio.add_subscriptions(_AIO_DATA_ITEMS, on_change = True)
        self.aio.add_callback({self.aio.up_button.data_name:self.up_cb})
        self.aio.add_callback({self.aio.down_button.data_name:self.down_cb})
        self.running = True
        threading.Thread.start(self)

    def run(self):
        last_cast_status = None
        while(self.running):
            # Check WiFi timeout
            if self.wifi.off_time <= datetime.now(pytz.reference.LocalTimezone()) and self.wifi.get_status() == 'on':
                result = self.wifi.stop() # Turn off WiFi if our time has expired and it's on
                if self._menu_on is True:
                    self._print_menu()
            elif self.wifi.off_time > datetime.now(pytz.reference.LocalTimezone()) and self.wifi.get_status() == 'off':
                result = self.wifi.start() # Turn on WiFi if our time has NOT expired and it's off
                if self._menu_on is True:
                    self._print_menu()
            # if it's time to turn sonde broker and schedule back on
            if  self._sondeSwap_inProgress and (
                    datetime.now(pytz.reference.LocalTimezone()) > self._sondeSwap_time + self.SONDE_SWAP_DURATION ):
                self._menu_on = True    # this tells the sonde swap routine to finish up
            cast_status = self.schedule_status.cast_status
            if self._menu_on is False and last_cast_status != cast_status:
                # Put something about cast status
                self._lcd.write_line(4,'Cast Status: {0}'.format(cast_status),0)
                last_cast_status = cast_status
            time.sleep(1)

    def upButtonCallback(self, timestamp, callback_obj):
        ''' Called via callback on the up button. Determines if it was a press or release.
        '''
        self._upValue = abs(callback_obj.value -1)
        if callback_obj.value == 0: # It was a press
            self._upPressDT = timestamp
            self._upPress()
        elif callback_obj.value == 1:
            self._upReleaseDT = timestamp
            self._upRelease()
    def downButtonCallback(self, timestamp, callback_obj):
        ''' Called via callback on the down button. Determines if it was a press or release.
        '''
        self._downValue = abs(callback_obj.value - 1)
        if callback_obj.value == 0: # It was a press
            self._downPressDT = timestamp
            self._downPress()
        elif callback_obj.value == 1:
            self._downReleaseDT = timestamp
            self._downRelease()
    def _upPress(self):
#        print 'upPress', time.ctime(self._upReleaseDT), self._upReleaseDT
        tm = self._upPressDT  # record the press time that caused this entrance
        if self._downValue == 1:  # double click
            self._doublePress()
        else: # Single click
            time.sleep(self._DOUBLE_PRESS_DELAY)
            if self._downValue == 0:  # if it became a double press the other thread is handling it
                #self.motorStop() # No longer 
                rt = self._LONG_PRESS_DELAY - (datetime.now(pytz.reference.LocalTimezone()) - tm)    # calc remaining time
                rts = rt.seconds + (rt.days*24*3600)
                if rts > 0:
                    sleep(rts)
                # If the button is still down it is a long press
                if self._upValue == 1 and tm == self._upPressDT:    # still pressed and the same press?
                    self.motorUp()
        return
    def _downPress(self):
        tm = self._downPressDT  # record the press time that caused this entrance
        if self._upValue == 1:  # double click
            self._doublePress()
            return
        time.sleep(self._DOUBLE_PRESS_DELAY)
        if self._upValue == 1:  # if it became a double press the other thread is handling it
            return
        #self.motorStop()
        rt = self._LONG_PRESS_DELAY - (datetime.now(pytz.reference.LocalTimezone()) - tm)    # calc remaining time
        rts = rt.seconds + (rt.days*24*3600)
        if rts > 0:
            time.sleep(rts)
        # If the button is still down it is a long press
        if self._downValue == 1 and tm == self._downPressDT: # still pressed and the same press?
            self.motorDown()
    def _doublePress(self):
        # This can sometimes get called twice for a single double press event.
        # The following line causes the second call to do nothing.
        if self._isDoublePress is False:
            self._isDoublePress = True
            #print 'doublePress', self._isDoublePress
            if self._menu_on is False:
                self._menu_on = True
                self._menuFirstItem = 0
                self._menuSelectedItem = 0
                print "printing menu from double press"
                self._print_menu()
            else:
                self._menuSelect()
    def _upRelease(self):
        # check if its a release from a double press
        if self._downValue == 0: # down not pressed
            if self._isDoublePress is True:
                self._doubleRelease()
            else:
                # was it a short release or a long release?
                if self._upReleaseDT - self._upPressDT < self._LONG_PRESS_DELAY:
                    if self._menu_on is True:
                        self._menuUp()
                else:
                    self.motorStop()
        return
    def _downRelease(self):
        # check if its a release from a double press
        if self._upValue == 1: #pressed
            return
        else:
            if self._isDoublePress is True:
                self._doubleRelease()
                return
        # was it a short release or a long release?
        if self._downReleaseDT - self._downPressDT < self._LONG_PRESS_DELAY:
            if self._menu_on is True:
                self._menuDown()
        else:
            self.motorStop()
    def _doubleRelease(self):
        self._isDoublePress = False
    def _print_menu(self):
        # print the interface screen information
        for i in range( self._menuFirstItem, self._menuFirstItem+3 ):
            if i == self._menuSelectedItem:
                self._lcd.write_line(i - self._menuFirstItem + 1, "* {0}".format(self._MENU_ITEMS[i]))
            else:
                self._lcd.write_line(i - self._menuFirstItem + 1, "  {0}".format(self._MENU_ITEMS[i]))
        self._lcd.write_line(4, "Sched:{0:3s}, WiFi:{1:3s}".format(self.schedule_status.state,
                                                                   self.wifi.status))
    def _clear_menu(self):
        self._lcd.clear_screen(lines=(1,2,3,4))
    def _menuUp(self):
        if self._menuSelectedItem > 0:
            self._menuSelectedItem = self._menuSelectedItem - 1
        if self._menuSelectedItem < self._menuFirstItem:
            self._menuFirstItem = self._menuSelectedItem
        print "printing menu from menu up"
        self._print_menu()
    def _menuDown(self):
        if self._menuSelectedItem < len(self._MENU_ITEMS)-1:
            self._menuSelectedItem = self._menuSelectedItem + 1
        if self._menuSelectedItem > self._menuFirstItem+2:
            self._menuFirstItem = self._menuSelectedItem-2
        print "printing menu from menu down"
        self._print_menu()
    def _menuSelect(self):
#        print 'selected:', self._menuSelectedItem, self._MENU_ITEMS[self._menuSelectedItem]
        self._MENU_METHODS[self._menuSelectedItem]()        # call the associated method
    def _sondeSwap(self):
        self._sondeSwap_time = datetime.now(pytz.reference.LocalTimezone())
        self._sondeSwap_inProgress = True
        # pause the schedule, if necessary
        if self.schedule_status.state != 'off':
            self.schedule_status.state = 'paused'
        # suspend the sonde broker
        self.sonde.get_token(program_name=self.program_name,
                                          calling_obj=self.__class__.__name__,
                                          override=True)
        self.sonde.suspend_broker()
        self.sonde.tokenRelease()
        self._clear_menu()
        self._lcd.write_line(2, "Sonde Swap")
        self._menu_on = False
        while self._menu_on is False:
            self._lcd.write_line(3, "Time left: {0:3.0f} min ".format(
                       (self._sondeSwap_time+self.SONDE_SWAP_DURATION - datetime.now(pytz.reference.LocalTimezone())).seconds / 60) )
            time.sleep(1)
        self._sondeSwap_inProgress = False
        if self.schedule_status.state != 'off':
            self.schedule_status.state = 'on'
        # resume the sonde broker
        self.sonde.get_token(program_name=self.program_name,
                                          calling_obj=self.__class__.__name__,
                                          override=True)
        self.sonde.resume_broker()
        self.sonde.tokenRelease()
    def _toggleSchedule(self):
        if self.schedule_status.state == 'on':
            self.schedule_status.state = 'paused'
        elif self.schedule_status.state == 'paused':
            self.schedule_status.state = 'on'
        elif self.schedule_status.state == 'off':
            # Can not resume schedule from off state in local interface
            pass
        else:
            # Unknown schedule state!
            pass
        #print "printing menu from toggle schedule"
        self._print_menu()
    def _toggleWiFi(self):
        '''
        Sets self.wifi.off_time which should be acted upon by run() 
        '''
        self.wifi.get_status()
        if self.wifi.status == 'off':
            # turn on Wifi
            self.wifi.off_time = datetime.now(pytz.reference.LocalTimezone()) + self.WIFI_ON_INTERVAL
        elif self.wifi.status == 'on':
            # turn off Wifi
            self.wifi.off_time = datetime.now(pytz.reference.LocalTimezone())
        else:
            pass
        self._print_menu()
    def _showSondeData(self):
        self.sonde.get_token(program_name=self.program_name,
                        calling_obj=self.__class__.__name__,
                        override=False)
        self.sonde.start_sampling()
        self.sonde.tokenRelease()
        self._clear_menu()
        self._lcd.write_line(2, "Getting sonde data")
        time.sleep(2)   # give time for the sonde to deliver first data to broker
        # This would be much more efficient using add_subscriptions() instead of get_value()
        self._menu_on = False
        self.sonde.add_subscriptions(self._SONDE_DATA_ITEMS,subscriber='localInterface',on_change=True)
        # We never know exactly what probes we will have, so adapt...
        turbid_type = None
        do_type = None
        if hasattr(self.sonde,'turbid_NTU'):
            turbid_type = 'turbid_NTU'
        elif hasattr(self.sonde,'turbidPl_NTU'):
            turbid_type = 'turbidPl_NTU'
        if hasattr(self.sonde,'odo_mgL'):
            turbid_type = 'odo_mgL'
        elif hasattr(self.sonde,'do_mgL'):
            turbid_type = 'do_mgL'
        while self._menu_on is False:
            if turbid_type is not None:
                turbid = getattr(getattr(self.sonde,turbid_type),'value')
            else:
                turbid = -999
            if do_type is not None:
                d_o = getattr(getattr(self.sonde,do_type),'value')
            else:
                d_o = -999
            self._lcd.write_line(1, " Depth Temp  Sal")
            self._lcd.write_line(2, "  {0:4.1f} {1:4.1f}  {2:4.1f}".format(self.sonde.depth_m.value, self.sonde.temp_C.value, self.sonde.sal_ppt.value) )
            self._lcd.write_line(3, "  DO   Chl   Turb")
            self._lcd.write_line(4, "  {0:4.1f} {1:4.1f}  {2:6.1f}".format(d_o, self.sonde.chl_ugL.value, turbid))
            time.sleep(0.5)
        self.sonde.unsubscribe(self._SONDE_DATA_ITEMS)
    def _showWindData(self):
        self.wind.add_subscriptions(_WIND_DATA_ITEMS, on_change = True)
        self._clear_menu()
        self._lcd.write_line(2, "Getting wind data")
        time.sleep(2)   # give time for the instrument to deliver first data to broker
        self._menu_on = False
        while self._menu_on is False:
            try:
                self._lcd.write_line(1, "Wind Speed: {0:4.1f} {1}".format(self.wind.wind_speed.value,self.wind.wind_speed.units))
                self._lcd.write_line(2, "Wnd Dir: {0:3.0f} {1}".format(self.wind.wind_direction.value,self.wind.wind_direction.units))
                self._lcd.write_line(3, "Ave Speed: {0:4.1f} {1}".format(self.wind.average_wind_speed.value,self.wind.average_wind_speed.units))
                self._lcd.write_line(4, "Compass: {0:3.0f} {1}".format(self.wind.compass_direction.value,self.wind.compass_direction.units))
            except AttributeError,e:
                self._lcd.clear_screen([1,4])
                self._lcd.write_line(2,' Wind Broker Not responding')
                self._lcd.write_line(3,e)
            time.sleep(0.5)
        self.wind.unsubscribe_all()
    def _showDepthData(self):
        self.depth.add_subscriptions(_DEPTH_DATA_ITEMS, on_change = True)
        self._clear_menu()
        self._lcd.write_line(2, "Getting depth data")
        time.sleep(2)   # give time for the instrument to deliver first data to broker
        self._menu_on = False
        while self._menu_on is False:
            try:
                water_depth = self.sounder.water_depth.value
                temp_C = self.sounder.water_temp_surface.value
                self._lcd.write_line(1, "Depth: {0:3.1f}m {1:4.1f}ft".format(water_depth, water_depth*3.28083))
                self._lcd.write_line(2, "Working depth: {0:3.1f} m".format(self.sounder.water_depth_working.value))
                self._lcd.write_line(3, "One Min Ave: {0:3.1f} m".format(self.sounder.water_depth_1minave.value))
                self._lcd.write_line(4, "Temp: {0:4.1f} C, {1:4.1f} F".format(temp_C, temp_C*9/5 + 32))
            except AttributeError,e:
                self._lcd.clear_screen([1,4])
                self._lcd.write_line(2,' Depth Broker Not responding')
                self._lcd.write_line(3,e)
            time.sleep(0.5)
        self.depth.unsubscribe_all()
    def _showPowerStatus(self):
        self._menu_on = False
        while self._menu_on is False:
            self._lcd.write_line(1, "Voltage: {0:.2f} V".format(self.voltage.value))
            self._lcd.write_line(2, "Ld:{0:.1f}A  Chg:{1:.1f}A ".format(self.loadCurrent.value,
                                                                        self.chargeCurrent.value), )
            self._lcd.write_line(3, "Ld:{0:.1f}AH Chg:{1:.1f}AH".format(self.loadCurrent.amp_hours,
                                                                        self.chargeCurrent.amp_hours) )
            self._lcd.write_line(4, "Net: {0:.1f} AH".format(self.chargeCurrent.amp_hours - self.loadCurrent.amp_hours))
            time.sleep(0.5)
    def _exitInterface(self):
        self._clear_menu()
        self._menu_on = False
    def motorUp(self):
#        self._lcd.write_line(4, 'Moving up')
        #self.mm3.tokenForceAcquire("LocalInterface.motorUp")
        self.mm3.get_token(program_name='LocalInterface.motorUp',override=True)
        self.mm3.move_at_speed(self._BUTTON_MOVE_SPEED,enable_db=False,
                                              direction='up',debug_mode=False)
        self.mm3.tokenRelease()
    def motorDown(self):
#        self._lcd.write_line(4, 'Moving down')
        #self.mm3.tokenForceAcquire("LocalInterface.motorDown")
        self.mm3.get_token(program_name='LocalInterface.motorDown',override=True)
        self.mm3.move_at_speed(self._BUTTON_MOVE_SPEED,enable_db=False,
                                              direction='down',debug_mode=False)
        self.mm3.tokenRelease()
    def motorStop(self):
#        self._lcd.write_line(4, 'Motor stopped')
        #self.mm3.tokenForceAcquire("LocalInterface.motorStop")
        self.mm3.get_token(program_name='LocalInterface.motorStop',override=True)
        self.mm3.stop()
        self.mm3.tokenRelease()
    def up_cb(self, timestamp, callback_obj, pv={'lastval':1}):
        ''' change detector '''
        if callback_obj.value != pv['lastval']:
            pv['lastval'] = callback_obj.value
            self.upButtonCallback(timestamp, callback_obj)
    def down_cb(self, timestamp, callback_obj, pv={'lastval':1}):
        ''' change detector '''
        if callback_obj.value != pv['lastval']:
            pv['lastval'] = callback_obj.value
            self.downButtonCallback(timestamp, callback_obj)

class LocalMenu(object):
    def __init__(self,parent):
        """
        schedule_status
        sonde
        _clear_menu()
        _print_menu()
        _lcd
        _wifi_off
        """                             
        self.wifi = WiFi(interface='wlan0')
        if self.wifi.status == 'on':
            self.wifi.off_time = datetime.now(pytz.reference.LocalTimezone()) + self.WIFI_ON_INTERVAL
        else:
            self.wifi.start()
    def _sondeSwap(self):
        self._sondeSwap_time = datetime.now(pytz.reference.LocalTimezone())
        self._sondeSwap_inProgress = True
        # pause the schedule, if necessary
        if self.schedule_status.state != 'off':
            self.schedule_status.state = 'paused'
        # suspend the sonde broker
        self.sonde.get_token(program_name=self.program_name,
                                          calling_obj=self.__class__.__name__,
                                          override=True)
        self.sonde.suspend_broker()
        self.sonde.tokenRelease()
        self._clear_menu()
        self._lcd.write_line(2, "Sonde Swap")
        self._menu_on = False
        while self._menu_on is False:
            self._lcd.write_line(3, "Time left: {0:3.0f} min ".format(
                       (self._sondeSwap_time+self.SONDE_SWAP_DURATION - datetime.now(pytz.reference.LocalTimezone())).seconds / 60) )
            time.sleep(1)
        self._sondeSwap_inProgress = False
        if self.schedule_status.state != 'off':
            self.schedule_status.state = 'on'
        # resume the sonde broker
        self.sonde.get_token(program_name=self.program_name,
                                          calling_obj=self.__class__.__name__,
                                          override=True)
        self.sonde.resume_broker()
        self.sonde.tokenRelease()
    def _toggleSchedule(self):
        if self.schedule_status.state == 'on':
            self.schedule_status.state = 'paused'
        elif self.schedule_status.state == 'paused':
            self.schedule_status.state = 'on'
        elif self.schedule_status.state == 'off':
            # Can not resume schedule from off state in local interface
            pass
        else:
            # Unknown schedule state!
            pass
        #print "printing menu from toggle schedule"
        self._print_menu()
    def _toggleWiFi(self):
        '''
        Sets self.wifi.off_time which should be acted upon by run() 
        '''
        self.wifi.get_status()
        if self.wifi.status == 'off':
            # turn on Wifi
            self.wifi.off_time = datetime.now(pytz.reference.LocalTimezone()) + self.WIFI_ON_INTERVAL
        elif self.wifi.status == 'on':
            # turn off Wifi
            self.wifi.off_time = datetime.now(pytz.reference.LocalTimezone())
        else:
            pass
        self._print_menu()
    def _showSondeData(self):
        self.sonde.get_token(program_name=self.program_name,
                        calling_obj=self.__class__.__name__,
                        override=False)
        self.sonde.start_sampling()
        self.sonde.tokenRelease()
        self._clear_menu()
        self._lcd.write_line(2, "Getting sonde data")
        time.sleep(2)   # give time for the sonde to deliver first data to broker
        # This would be much more efficient using add_subscriptions() instead of get_value()
        self._menu_on = False
        self.sonde.add_subscriptions(self._SONDE_DATA_ITEMS,subscriber='localInterface',on_change=True)
        # We never know exactly what probes we will have, so adapt...
        turbid_type = None
        do_type = None
        if hasattr(self.sonde,'turbid_NTU'):
            turbid_type = 'turbid_NTU'
        elif hasattr(self.sonde,'turbidPl_NTU'):
            turbid_type = 'turbidPl_NTU'
        if hasattr(self.sonde,'odo_mgL'):
            turbid_type = 'odo_mgL'
        elif hasattr(self.sonde,'do_mgL'):
            turbid_type = 'do_mgL'
        while self._menu_on is False:
            if turbid_type is not None:
                turbid = getattr(getattr(self.sonde,turbid_type),'value')
            else:
                turbid = -999
            if do_type is not None:
                d_o = getattr(getattr(self.sonde,do_type),'value')
            else:
                d_o = -999
            self._lcd.write_line(1, " Depth Temp  Sal")
            self._lcd.write_line(2, "  {0:4.1f} {1:4.1f}  {2:4.1f}".format(self.sonde.depth_m.value, self.sonde.temp_C.value, self.sonde.sal_ppt.value) )
            self._lcd.write_line(3, "  DO   Chl   Turb")
            self._lcd.write_line(4, "  {0:4.1f} {1:4.1f}  {2:6.1f}".format(d_o, self.sonde.chl_ugL.value, turbid))
            time.sleep(0.5)
        self.sonde.unsubscribe(self._SONDE_DATA_ITEMS)
    def _showWindData(self):
        self.wind.add_subscriptions(_WIND_DATA_ITEMS, on_change = True)
        self._clear_menu()
        self._lcd.write_line(2, "Getting wind data")
        time.sleep(2)   # give time for the instrument to deliver first data to broker
        self._menu_on = False
        while self._menu_on is False:
            try:
                self._lcd.write_line(1, "Wind Speed: {0:4.1f} {1}".format(self.wind.wind_speed.value,self.wind.wind_speed.units))
                self._lcd.write_line(2, "Wnd Dir: {0:3.0f} {1}".format(self.wind.wind_direction.value,self.wind.wind_direction.units))
                self._lcd.write_line(3, "Ave Speed: {0:4.1f} {1}".format(self.wind.average_wind_speed.value,self.wind.average_wind_speed.units))
                self._lcd.write_line(4, "Compass: {0:3.0f} {1}".format(self.wind.compass_direction.value,self.wind.compass_direction.units))
            except AttributeError,e:
                self._lcd.clear_screen([1,4])
                self._lcd.write_line(2,' Wind Broker Not responding')
                self._lcd.write_line(3,e)
            time.sleep(0.5)
        self.wind.unsubscribe_all()
    def _showDepthData(self):
        self.depth.add_subscriptions(_DEPTH_DATA_ITEMS, on_change = True)
        self._clear_menu()
        self._lcd.write_line(2, "Getting depth data")
        time.sleep(2)   # give time for the instrument to deliver first data to broker
        self._menu_on = False
        while self._menu_on is False:
            try:
                water_depth = self.sounder.water_depth.value
                temp_C = self.sounder.water_temp_surface.value
                self._lcd.write_line(1, "Depth: {0:3.1f}m {1:4.1f}ft".format(water_depth, water_depth*3.28083))
                self._lcd.write_line(2, "Working depth: {0:3.1f} m".format(self.sounder.water_depth_working.value))
                self._lcd.write_line(3, "One Min Ave: {0:3.1f} m".format(self.sounder.water_depth_1minave.value))
                self._lcd.write_line(4, "Temp: {0:4.1f} C, {1:4.1f} F".format(temp_C, temp_C*9/5 + 32))
            except AttributeError,e:
                self._lcd.clear_screen([1,4])
                self._lcd.write_line(2,' Depth Broker Not responding')
                self._lcd.write_line(3,e)
            time.sleep(0.5)
        self.depth.unsubscribe_all()
    def _showPowerStatus(self):
        self._menu_on = False
        while self._menu_on is False:
            self._lcd.write_line(1, "Voltage: {0:.2f} V".format(self.voltage.value))
            self._lcd.write_line(2, "Ld:{0:.1f}A  Chg:{1:.1f}A ".format(self.loadCurrent.value,
                                                                        self.chargeCurrent.value), )
            self._lcd.write_line(3, "Ld:{0:.1f}AH Chg:{1:.1f}AH".format(self.loadCurrent.amp_hours,
                                                                        self.chargeCurrent.amp_hours) )
            self._lcd.write_line(4, "Net: {0:.1f} AH".format(self.chargeCurrent.amp_hours - self.loadCurrent.amp_hours))
            time.sleep(0.5)
    def _exitInterface(self):
        self._clear_menu()
        self._menu_on = False
        
        
class WiFi(object):
    def __init__(self,interface='wlan0'):
        WIFI_ON_INTERVAL = int(config.get(self.__class__.__name__,{}).get('WIFI_ON_INTERVAL',120))
        self.WIFI_ON_INTERVAL = timedelta(minutes=WIFI_ON_INTERVAL)
        self.off_time = datetime.now(pytz.reference.LocalTimezone())
        self._logger = logging.getLogger(self.__class__.__name__)
        self.interface=interface
        # Check WiFi status and try to set to 'on' or 'off'
        self.status = self.get_status()
        self._logger.debug("WiFi interface {0} status is {1}".format(interface,self.status))
    def get_status(self):
        try:
            ifconfig1 = subprocess.Popen(['/sbin/ifconfig',self.interface],shell=False,stdout=subprocess.PIPE)
            ifconfig2 = ifconfig1.communicate()
            ifconfig3 = ifconfig2[0]
            ifconfig4 = ifconfig3.split()
        except Exception,e:
            print e
            return 'unknown'
        if 'UP' in ifconfig4:
            self.status = 'on'
        else:
            self.status = 'off'
        return self.status
    def start(self):
        # Try to start WiFi
        success = subprocess.call(['sudo','/sbin/ifup',self.interface])
        if success:
            self._logger.info('Started WiFi interface')
            self.status = self.get_status()
        else:
            self._logger.info('Unable to start WiFi interface {0}'.format(success))
        return success # Return non-zero for success
    def stop(self):
        # Try to stop WiFi
        success = subprocess.call(['sudo','/sbin/ifdown',self.interface])
        if success:
            self._logger.info('Stopped WiFi interface')
            self.status = self.get_status()
        else:
            self._logger.info('Unable to stop WiFi interface {0}'.format(success))
        return success # Return non-zero for success

class Local_Interface(threading.Thread):
    START_STATE = 'WELCOME'
    AIO_DATA_ITEMS = ['up_button', 'down_button']
    SONDE_DATA_ITEMS = ['depth_m', 'temp_C', 'sal_ppt', 'do_mgL', 'odo_mgL','chl_ugL', 'turbid_NTU','turbidPl_NTU']
    WIND_DATA_ITEMS = ['wind_speed', 'wind_direction', 'average_wind_speed', 'compass_direction']
    DEPTH_DATA_ITEMS = ['water_depth', 'water_depth_1minave', 'water_depth_working', 'water_temp_surface']
    LONG_PRESS_DELAY = timedelta(seconds=1)    # seconds
    
    def __init__(self, supervisor, **kwargs):
        self.supervisor = supervisor
        config = self.supervisor._config
        self._logger = logging.getLogger()
        super(LocalInterface,self).__init__()
        self.name = self.__class__.__name__
        self.program_name = self.supervisor.program_name
        self.running = False
        self._lcd = pertd2.Pertelian()
        self._lcd.delay_time(100000) # Set delay time to .1 a second
        self._lcd.clear_screen()
        self.BUTTON_DELAY = 0.2 
        self.LOOP_DELAY = 0.2 # Lower = better perfomance, more CPU
        self._BUTTON_MOVE_SPEED = int(config.get(self.__class__.__name__,{}).get('BUTTON_MOVE_SPEED',20))
        SONDE_SWAP_DURATION = int(config.get(self.__class__.__name__,{}).get('SONDE_SWAP_DURATION',30))
        self.SONDE_SWAP_DURATION = timedelta(minutes=SONDE_SWAP_DURATION)
        WIFI_ON_INTERVAL = int(config.get(self.__class__.__name__,{}).get('WIFI_ON_INTERVAL',120))
        self.WIFI_ON_INTERVAL = timedelta(minutes=WIFI_ON_INTERVAL)
        handlers = {}
        handlers['WELCOME'] = self.welcome()
        handlers['MAIN_MENU'] = self.main_menu()
        handlers['OPTIONS_MENU'] = self.options_menu()
        handlers['SONDE_MENU'] = self.sonde_menu()
        handlers['WIND_MENU'] = self.wind_menu()
        handlers['DEPTH_MENU'] = self.depth_menu()
        handlers['POWER_MENU'] = self.power_menu()
    def start():
        pass
    def run():
        new_state = self.handlers[self.START_STATE]
        while True:
            new_state = self.handlers[upper(new_state)]
            
    # Now the states
    def welcome(self):
        self._lcd.clear_screen()
        self._lcd.write_line(1,' Welcome to AVP3  ')
        self._lcd.write_line(2,'Press any button to ')
        self._lcd.write_line(3,'enter menu.         ')
        time.sleep(self.BUTTON_DELAY)
        result = button_handler() # Will return on any button press
        return 'MAIN_MENU'
            
    def main_menu(self):
        main_menu = ['options_menu','sonde_menu','wind_menu','depth_menu','power_menu']
        headings = {'options_menu':'Options','sonde_menu':'Sonde menu','wind_menu':'Wind menu','depth_menu':'Depth menu','power_menu':'Power menu'}
        selected_menu = 0
        menu_top = 0
        lines = [2,3,4]
        new_state = ''
        while new_state = '':
            self.print_menu(headings,selected_menu,lines,menu_top)
            result = button_handler()
            if result = 'up_press':
                if selected_menu > 1:
                    selected_menu =- 1
                    if selected_menu < menu_top:
                        menu_top = selected_menu
            elif result = 'down_press':
                if selected_menu < len(main_menu):
                    selected_menu =+ 1
                    if selected_menu > menu_top:
                        menu_top = selected_menu - len(lines)
            elif result = 'double':
                new_state = main_menu[menu_state]
            elif result = 'up_long':
                pass
            elif result = 'down_long'
                pass
            else:
                # Unknown option
                pass
                
    def print_menu(self,headings,selected_menu=0,lines=[1,2,3,4],menu_top=0,):
        ''' Prints out menu
            selected_menu is the currently selected line
            headings is a list of menu headings
            lines is a list of lines on which menu should be printed
            menu_top is the top menu item to be printed
        '''
        
        line_qty = len(lines)
        first_line = max((selected_menu - line_qty + 1),0)
        for line in range(first_line,(first_line + line_qty - 1)):
            
    def options_menu(self):
        return 'MAIN_MENU'
    def sonde_menu(self):
        return 'MAIN_MENU'
    def wind_menu(self):
        return 'MAIN_MENU'
    def depth_menu(self):
        return 'MAIN_MENU'
    def power_menu(self):
        return 'MAIN_MENU'
    
    
    def button_handler(self,timeout=None):
        ''' Returns the button action. Valid actions are:
            up_press, down_press, up_long, down_long, double
            If an optional timeout is specified (timedelta), will return None when it times out.
        '''
        result = None
        start_time = datetime.now() # Sued if the timeout option is specified.
        up_pressDT = None
        down_pressDT = None
        seen_press = False
        while self.aio.up_button == 1 or self.aio.up_button == 1:
            # Wait for buttons to return to 0
            time.sleep(self.LOOP_DELAY)
        while result is None:
            if timeout is not None:
                if datetime.now() - start_time > timeout:
                    break
            if self.aio.up_button == 1:
                seen_press = True
                if up_pressDT is None:
                    up_pressDT = datetime.now()
                if self.aio.down_button == 1:
                    result = 'double'
                    break
                elif datetime.now() - up_pressDT >= self.LONG_PRESS_DELAY:
                    result = 'up_long'
                else:
                    # we don't know yet
                    pass
            elif up_pressDT is not None: # A release
                result = 'up_press'
            # Now look at down press
            if self.aio.down_button == 1:
                seen_press = True
                if down_pressDT is None:
                    down_pressDT = datetime.now()
                if self.aio.up_button == 1:
                    result = 'double'
                    break
                elif datetime.now() - down_pressDT >= self.LONG_PRESS_DELAY:
                    result = 'down_long'
                else:
                    # we don't know yet
                    pass
            elif down_pressDT is not None: # A release
                result = 'down_press'
            if seen_press is False:
                time.sleep(self.LOOP_DELAY)
        return result