#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        Local_Interface
# Purpose:     Provides operator interface to LCD readout
#
# Author:      whipple, neve
#
# Created:     01/02/2012
# Updated:     09/12/2017
#-------------------------------------------------------------------------------
#Built in Modules
import time
from datetime import datetime, timedelta
import logging
import os
import socket
import subprocess
import sys
import threading
#Installed Modules
import pytz.reference 
from configobj import ConfigObj
#Custom Modules
import avp_db # For logging
import avp_LCD
import avp_power
import avp_sched
import avp_util
import avp_winch
'''
This is for a two button interface and displays data to the 4-line lcd.

Each button change of state starts a new thread beginning with the routine
upButtonCallback or downButtonCallback.  The callback routines decide whether
there was a button press or release, save the time and button value, then
call the appropriate routine.  Actions are also performed by the interface
based on a double press which is both buttons being pressed within a window of
time.  Long-press of the buttons also give different actions (motor control).
'''

class Local_Interface(threading.Thread):
    '''
    Provides local response to the up/down buttons including a menu system
    '''
    _DOUBLE_PRESS_DELAY = 0.1  # window which defines double press
    _LONG_PRESS_DELAY = timedelta(seconds=1)    # seconds
    _AIO_DATA_ITEMS = ['up_button', 'down_button']
    _SONDE_DATA_ITEMS = ['depth_m', 'temp_C', 'sal_ppt', 'do_mgL', 'odo_mgL','chl_ugL', 'turbid_NTU','turbidPl_NTU']
    _WIND_DATA_ITEMS = ['wind_speed', 'wind_direction', 'average_wind_speed', 'compass_direction']
    _DEPTH_DATA_ITEMS = ['water_depth', 'water_depth_1minave', 'water_depth_working', 'water_temp_surface']
    
    
    def __init__(self, config, debug_mode=False,**kwargs):
        self.config = config
        enabled =  avp_util.t_or_f(self.config.get('localInterface',{}).get('ENABLED','NOT FOUND'))
        self.logger = logging.getLogger()
        if enabled != True:
            self.logger.warning("LCD disabled in config file [localInterface][ENABLED] = False")
            exit(1)
        self.debug_mode = debug_mode
        #super(Local_Interface,self).__init__("Local_Interface")
        super(Local_Interface,self).__init__()
        self.logger.debug("Initializing Local Interface")
        self.name = self.__class__.__name__
        self.program_name = "Local Interface"
        self.running = False
        LCD_type = self.config.get('localInterface',{}).get('TYPE','NOT FOUND')
        if LCD_type == 'Pertelian':
            self._lcd = avp_LCD.Pertelian()
        elif LCD_type == 'ColdTears':
            self._lcd = avp_LCD.ColdTears()
        else:
            self.logger.warning("Unrecognised key localInterface.LCD_type in {hostname}_avp.ini {LCD}.".format(hostname=socket.gethostname(),LCD=LCD_type))
            exit(0)
        self._lcd.delay_time(100000) # Set delay time to .1 a second
        self._BUTTON_MOVE_SPEED = int(config.get(self.__class__.__name__,{}).get('BUTTON_MOVE_SPEED',20))
        SONDE_SWAP_DURATION = int(config.get(self.__class__.__name__,{}).get('SONDE_SWAP_DURATION',30))
        self.SONDE_SWAP_DURATION = timedelta(minutes=SONDE_SWAP_DURATION)
        self._sondeSwap_time = datetime(2000,0o1,0o1).replace(tzinfo=pytz.reference.LocalTimezone())
        self._sondeSwap_inProgress = False
        WIFI_ON_INTERVAL = int(config.get(self.__class__.__name__,{}).get('WIFI_ON_INTERVAL',120))
        self.WIFI_ON_INTERVAL = timedelta(minutes=WIFI_ON_INTERVAL)
        self._wifi_off_time = datetime.now(pytz.reference.LocalTimezone()) + self.WIFI_ON_INTERVAL
        try:
            self.wifi = WiFi(interface='wlan0')
            if self.wifi.status == 'off':
                self.wifi.start()
        except:
            print("Disabling WiFi functionality")
        # Set up menus
        self._menu_on = False
        self._menuFirstItem = 0
        self._menuSelectedItem = 0
        self._MENU_ITEMS = ['Sonde swap',
                      'Toggle schedule',
                      'Toggle WiFi',
                      'Show sonde data',
                      'Show wind data',
                      'Show depth data',
                      'Show power status',
					  'Shutdown system',
                      'Exit interface']
        self._MENU_METHODS = [self._sondeSwap,
                             self._toggleSchedule,
                             self._toggleWiFi,
                             self._showSondeData,
                             self._showWindData, 
                             self._showDepthData,
                             self._showPowerStatus,
							 self._shutdownSystem,
                             self._exitInterface]
        #Initialize some variables
        self._upReleaseDT = datetime(2000,0o1,0o1).replace(tzinfo=pytz.reference.LocalTimezone())
        self._upReleaseDT = datetime(2000,0o1,0o1).replace(tzinfo=pytz.reference.LocalTimezone())
        self._upValue = 1   # 1 when not pressed
        self._downPressDT = datetime(2000,0o1,0o1).replace(tzinfo=pytz.reference.LocalTimezone())
        self._downReleaseDT = datetime(2000,0o1,0o1).replace(tzinfo=pytz.reference.LocalTimezone())
        self._downValue = 1 # 1 when not pressed
        self._isDoublePress = False
        self._doWelcome = True
        self._lcd.clear_screen()  # Show the startup screen
        string = 'Welcome to {host}'.format(host=socket.gethostname())
        self._lcd.write_line(1,'{s:^{l}}'.format(s=string,l=self._lcd.COLUMNS_LCD),0)
        self._lcd.write_line(2,'{s:^{l}}'.format(s="Please Wait...",l=self._lcd.COLUMNS_LCD),0)
    def welcome(self):
        self._lcd.clear_screen()
        string = 'Welcome to {host}'.format(host=socket.gethostname())
        self._lcd.write_line(1,'{s:^{l}}'.format(s=string,l=self._lcd.COLUMNS_LCD),0)
        self._lcd.write_line(2,'{s:^{l}}'.format(s="Press both for menu",l=self._lcd.COLUMNS_LCD),0)
    def shutdown(self):
        self.running = False
        time.sleep(1)
        self.logger.debug("Shutting down {0:24} {1:2} threads left.".format(self.name,threading.active_count()))
    def start(self):
        """ 
        """
        if ( self.debug_mode): print("Starting Local_Interface")
        self.broker_list = ['aio','wind','mm3','sonde']
        self.context = avp_util.AVPContext(self.config,startup=self.broker_list,program_name=self.program_name, debug_mode=False) # Set up console context
        try:
            self.aio = self.context.aio
        except AttributeError as e:
            self.logger.critical('Unable to instantiate AIO broker: {0}'.format(e))
        # To monitor schedule status
        self.schedule_status = avp_sched.AVPScheduleStatus(self.config,debug_mode=False)
        #self.power = avp_power.AVP_Power(self.aio,self.config)
        #self.wind = self.context.wind
        #self.sounder = self.context.sounder
        self.mm3 = self.context.mm3
        self.winch = avp_winch.Winch(self.context)
        self.aio.add_subscriptions(self._AIO_DATA_ITEMS, on_change = False, min_interval=100, max_interval=100)
        self.aio.add_callback({self.aio.up_button.data_name:self.up_cd})
        self.aio.add_callback({self.aio.down_button.data_name:self.down_cd})
        self.running = True
        super(Local_Interface,self).start()
        #threading.Thread.start(self)

    def run(self):
        last_cast_status = None
        if ( self.debug_mode): print("Running Local_Interface")
        while(self.running):
            # Check WiFi timeout
            # if not (os.uname()[4][:3] == 'arm'):
                # self.wifi.get_status()
                # if self._wifi_off_time <= datetime.now(pytz.reference.LocalTimezone()) and self.wifi.status == 'on':
                    # result = self.wifi.stop() # Turn off WiFi if our time has expired and it's on
                    # if self._menu_on is True:
                        # time.sleep(1)
                        # self._print_menu()
                # elif self._wifi_off_time > datetime.now(pytz.reference.LocalTimezone()) and self.wifi.status == 'off':
                    # result = self.wifi.start() # Turn on WiFi if our time has NOT expired and it's off
                    # if self._menu_on is True:
                        # time.sleep(1)
                        # self._print_menu()
            # if it's time to turn sonde broker and schedule back on
            if  self._sondeSwap_inProgress and (
                    datetime.now(pytz.reference.LocalTimezone()) > self._sondeSwap_time + self.SONDE_SWAP_DURATION ):
                print("sonde swap timed out")
                self._menu_on = True    # this tells the sonde swap routine to finish up
            if self._doWelcome is True:
                self.welcome() # Welcome screen
                self._doWelcome = False
            cast_status = self.schedule_status.cast_status
            if self._menu_on is False and last_cast_status != cast_status:
                # Put something about cast status
                string = cast_status
                if len(string) > self._lcd.COLUMNS_LCD: # If it is going to scroll, put some spaces in there
                    string += "     "
                self._lcd.write_line(self._lcd.LINES_LCD,string,0) #Write this to the last line
                last_cast_status = cast_status
            #print "There are {0} threads".format(threading.active_count())
            time.sleep(1)

    def upButtonCallback(self, timestamp, callback_obj):
        ''' Called via callback on the up button. Determines if it was a press or release.
        '''
        if ( self.debug_mode): print("    upButtonCallback")
        self._upValue = callback_obj.value
        if callback_obj.value == 0: # It was a press
            self._upPressDT = timestamp
            self._upPress()
        elif callback_obj.value == 1:
            self._upReleaseDT = timestamp
            self._upRelease()
    def downButtonCallback(self, timestamp, callback_obj):
        ''' Called via callback on the down button. Determines if it was a press or release.
        '''
        if ( self.debug_mode): print("    downButtonCallback")
        #print "dBC {0} at {1}".format(callback_obj.value,timestamp),
        self._downValue = callback_obj.value
        if callback_obj.value == 0: # It was a press
            self._downPressDT = timestamp
            #print " down"
            self._downPress()
        elif callback_obj.value == 1:
            self._downReleaseDT = timestamp
            #print " up"
            self._downRelease()

    def _upPress(self):
        tm = self._upPressDT  # record the press time that caused this entrance
        if self._downValue == 0:  # double click
            self._doublePress()
            return
        time.sleep(self._DOUBLE_PRESS_DELAY)
        if self._downValue == 0:  # if it became a double press the other thread is handling it
            return
        #self.motorStop() # No longer
        rts = self._LONG_PRESS_DELAY.seconds + (self._LONG_PRESS_DELAY.days*24*3600) - self._DOUBLE_PRESS_DELAY # Compensate for double press delay and convert timedelta to float.
        if rts > 0:
            time.sleep(rts)
        # If the button is still down it is a long press
        if self._upValue == 0 and tm == self._upPressDT:    # still pressed and the same press?
            self.move_motor('up')

    def _downPress(self):
        #print 'downPress at {0}'.format(self._downPressDT),
        tm = self._downPressDT  # record the press time that caused this entrance
        if self._upValue == 0:  # double click
            #print " doublePress"
            self._doublePress()
            return
        time.sleep(self._DOUBLE_PRESS_DELAY)
        if self._upValue == 0:  # if it became a double press the other thread is handling it
            #print " un-handled"
            return
        rts = self._LONG_PRESS_DELAY.seconds + (self._LONG_PRESS_DELAY.days*24*3600) - self._DOUBLE_PRESS_DELAY # Compensate for double press delay and convert timedelta to float.
        #print "sleeping for {0} sec".format(rts)
        if rts > 0:
            time.sleep(rts)
        # If the button is still down it is a long press
        if self._downValue == 0 and tm == self._downPressDT: # still pressed and the same press?
            #print " long_press {0} {1} {2}".format(self._downValue,self._downPressDT,tm)
            self.move_motor('down')

    def _doublePress(self):
        # This can sometimes get called twice for a single double press event.
        # The following line causes the second call to do nothing.
        if self._isDoublePress is False:
            self._isDoublePress = True
            if ( self.debug_mode): print("    _doublePress")
            if self._menu_on is False:
                self._menu_on = True
                self._menuFirstItem = 0
                self._menuSelectedItem = 0
                #print "printing menu from double press"
                self._print_menu()
            else:
                self._menuSelect()

    def _upRelease(self):
        # check if its a release from a double press
        if self._downValue == 0: #pressed
            return
        else:
            if self._isDoublePress is True:
                self._doubleRelease()
                return
        # was it a short release or a long release?
        if self._upReleaseDT - self._upPressDT < self._LONG_PRESS_DELAY:
            if self._menu_on is True:
                self._menuUp()
        else:
            self.motorStop()

    def _downRelease(self):
        # check if its a release from a double press
        #print "Down release",
        if self._upValue == 0: #pressed
            #print " pressed, no action"
            return
        else:
            if self._isDoublePress is True:
                #print " double_release"
                self._doubleRelease()
                return
        # was it a short release or a long release?
        if self._downReleaseDT - self._downPressDT < self._LONG_PRESS_DELAY:
            if self._menu_on is True:
                #print " menu down"
                self._menuDown()
            else:
                pass#print " menu off"
        else:
            #print "motor stop"
            self.motorStop()

    def _doubleRelease(self):
        if ( self.debug_mode): print("    _doublePress")
        self._isDoublePress = False

    def _print_menu(self):
        # print the interface screen information
        last_menu_item = self._menuFirstItem + self._lcd.LINES_LCD - 1
        if ( self.debug_mode ): print("Menu from {0} to {1}".format(self._menuFirstItem,last_menu_item  ));
        for menu_line in range(self._menuFirstItem, last_menu_item):
            line_to_be_written = menu_line - self._menuFirstItem + 1
            menu_string = self._MENU_ITEMS[menu_line]
            if menu_line == self._menuSelectedItem:
                menu_string = '{0} {1}'.format(menu_line,menu_string)
            else:
                # ColdTears requires | for leading spaces
                if self._lcd.__class__.__name__ == 'ColdTears':
                    menu_string = '||' + menu_string
                else:
                    menu_string = '  ' + menu_string
            if self._lcd.lcd_dict.get(line_to_be_written,'BLANK') != menu_string:
                print("{0} != {1} [{2}]".format(self._lcd.lcd_dict.get(line_to_be_written,'BLANK') ,menu_string,line_to_be_written))
                self._lcd.write_line(line_to_be_written, menu_string)
        # Write schedule and WiFi status on last line
        last_line = "Sched:{0:3s}, WiFi:{1:3s}".format(self.schedule_status.state, self.wifi.status)
        self._lcd.write_line(self._lcd.VALID_LINES[-1], last_line)

    def _clear_menu(self):
        self._lcd.clear_screen() #lines=(1,2,3,4))

    def _menuUp(self):
        if self._menuSelectedItem > 0:
            self._menuSelectedItem = self._menuSelectedItem - 1
            # Now see if we need to scroll menu
            if self._menuSelectedItem < self._menuFirstItem:
                self._menuFirstItem = self._menuSelectedItem
            self._print_menu()

    def _menuDown(self):
        if self._menuSelectedItem < len(self._MENU_ITEMS) - 1: # If we haven't reached the end of the menu.
            self._menuSelectedItem = self._menuSelectedItem + 1
            # Now see if we need to scroll menu
            if self._menuSelectedItem > self._menuFirstItem + self._lcd.LINES_LCD - 2:
                self._menuFirstItem = self._menuFirstItem + 1
            self._print_menu()

    def _menuSelect(self):
#        print 'selected:', self._menuSelectedItem, self._MENU_ITEMS[self._menuSelectedItem]
        self._MENU_METHODS[self._menuSelectedItem]()        # call the associated method
        self._print_menu()

    def _sondeSwap(self):
        if hasattr(self,'sonde') is False:
            self.context.startup('sonde')
            self.sonde = self.context.sonde
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
        self._lcd.write_line(1, "Sonde Swap")
        self._lcd.write_line(3, "Press both when done")
        self._menu_on = False
        while self._menu_on is False:
            self._lcd.write_line(2, "Time left: {0:3.0f} min ".format(
                       (self._sondeSwap_time+self.SONDE_SWAP_DURATION - datetime.now(pytz.reference.LocalTimezone())).seconds / 60) )
            time.sleep(1)
        print("sonde swap over")
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
            self._clear_menu()
            self._lcd.write_line(1, "WARNING: Schedule is")
            self._lcd.write_line(2, "off and may not be")
            self._lcd.write_line(3, "resumed from here.")
            time.sleep(5)
        else:
            self._clear_menu()
            self._lcd.write_line(1, "WARNING: Unknown")
            self._lcd.write_line(2, "schedule state")
            self._lcd.write_line(3, self.schedule_status.state)
            time.sleep(5)
        self._print_menu()

    def _toggleWiFi(self):
        """
        Sets self._wifi_off_time which should be acted upon by run() 
        """
        self.wifi.get_status()
        if self.wifi.status == 'off':
            # turn on Wifi
            self._wifi_off_time = datetime.now(pytz.reference.LocalTimezone()) + self.WIFI_ON_INTERVAL
        elif self.wifi.status == 'on':
            # turn off Wifi
            self._wifi_off_time = datetime.now(pytz.reference.LocalTimezone())
        else:
            pass # Probably disabled.
        self._print_menu()

    def _showSondeData(self):
        self._clear_menu()
        self._lcd.write_line(2, "Getting sonde data")
        if hasattr(self,'sonde') is False:
            self.context.startup('sonde')
            self.sonde = self.context.sonde
        self.sonde.get_token(program_name=self.program_name,
                        calling_obj=self.__class__.__name__,
                        override=False)
        self.sonde.start_sampling()
        self.sonde.tokenRelease()
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
        elif hasattr(self.sonde,'turbidity_FNU'):
            turbid_type = 'turbidity_FNU'
        if hasattr(self.sonde,'odo_mgL'):
            do_type = 'odo_mgL'
        elif hasattr(self.sonde,'do_mgL'):
            do_type = 'do_mgL'
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
        self._lcd.clear_screen([1,2,3,4])

    def _showWindData(self):
        self._clear_menu()
        self._lcd.write_line(2, "Getting wind data")
        if hasattr(self,'wind') is False:
            self.context.startup('wind')
            self.wind = self.context.wind
        time.sleep(2)   # give time for the instrument to deliver first data to broker
        self._menu_on = False
        while self._menu_on is False:
            windResult = self.wind.get_value( ['wind_speed', 'wind_direction', 'average_wind_speed', 'compass_direction'] )
            if not 'error' in windResult:
                self._lcd.write_line(1, "Wind Speed: {0:4.1f} {1}".format(self.wind.wind_speed.value,self.wind.wind_speed.units))
                self._lcd.write_line(2, "Wnd Dir: {0:3.0f} {1}".format(self.wind.wind_direction.value,self.wind.wind_direction.units))
                self._lcd.write_line(3, "Ave Speed: {0:4.1f} {1}".format(self.wind.average_wind_speed.value,self.wind.average_wind_speed.units))
                self._lcd.write_line(4, "Compass: {0:3.0f} {1}".format(self.wind.compass_direction.value,self.wind.compass_direction.units))
            time.sleep(0.5)
        self._lcd.clear_screen([1,2,3,4])

    def _showDepthData(self):
        self._clear_menu()
        self._lcd.write_line(2, "Getting depth data")
        if hasattr(self,'sounder') is False:
            self.context.startup('sounder')
            self.sounder = self.context.sounder
        time.sleep(2)   # give time for the instrument to deliver first data to broker
        self._menu_on = False
        while self._menu_on is False:
            depthResult = self.sounder.get_value( ['water_depth', 'water_depth_1minave', 'water_depth_working', 'water_temp_surface'] )
            if not 'error' in depthResult:
                water_depth = self.sounder.water_depth.value
                water_depth_F = water_depth*3.28083
                temp_C = self.sounder.water_temp_surface.value
                temp_F = (temp_C*9)/5 + 32
                self._lcd.write_line(1, "Depth: {0:3.1f}m {1:4.1f}ft".format(water_depth, water_depth_F))
                self._lcd.write_line(2, "Working depth: {0:3.1f} m".format(self.sounder.water_depth_working.value))
                self._lcd.write_line(3, "One Min Ave: {0:3.1f} m".format(self.sounder.water_depth_1minave.value))
                self._lcd.write_line(4, "Temp: {0:4.1f} C, {1:4.1f} F".format(temp_C, temp_F))
            time.sleep(0.5)
        self._lcd.clear_screen([1,2,3,4])

    def _showPowerStatus(self):
        self._clear_menu()
        if hasattr(self,'power') is False:
            self.power = avp_power.AVP_Power(self.aio,self.config)
            self.voltage = self.power.voltage
            self.loadCurrent = self.power.load_current
            self.chargeCurrent = self.power.charge_current
        self._menu_on = False
        while self._menu_on is False:
            self._lcd.write_line(1, "Voltage: {0:.2f} V".format(self.voltage.value))
            self._lcd.write_line(2, "Ld:{0:.1f}A  Chg:{1:.1f}A ".format(self.loadCurrent.value,
                                                                        self.chargeCurrent.value), )
            self._lcd.write_line(3, "Ld:{0:.1f}AH Chg:{1:.1f}AH".format(self.loadCurrent.amp_hours,
                                                                        self.chargeCurrent.amp_hours) )
            self._lcd.write_line(4, "Net: {0:.1f} AH".format(self.chargeCurrent.amp_hours - self.loadCurrent.amp_hours))
            time.sleep(0.5)
        self._lcd.clear_screen([1,2,3,4])

    def _shutdownSystem(self):
        iCount = 10;	# count down to shutdown
        self._menu_on = False
        self._clear_menu()
        self._lcd.write_line(2, "Shutting down in {0}".format(iCount))
        self._lcd.write_line(3, "Double press cancels")
        while self._menu_on is False and iCount > 0:
            time.sleep(1.0)
            iCount = iCount - 1
            self._lcd.write_line(2, "Shutting down in {0}".format(iCount))
        if self._menu_on is False:
            command = "/usr/bin/sudo /sbin/shutdown -h now"
            process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
            output = process.communicate()[0]
            print output

    def _exitInterface(self):
        self._menu_on = False
        self._doWelcome = True

    def move_motor(self,direction):
        self.mm3.get_token(program_name='LocalInterface.move_motor({0})'.format(direction),override=True)
        #self.mm3.move_at_speed(self._BUTTON_MOVE_SPEED,enable_db=False,
        #                                      direction='up',debug_mode=False)
        self.winch.move_at_speed(self._BUTTON_MOVE_SPEED,enable_db=False,
                                              direction=direction,debug_mode=False)
        self.mm3.tokenRelease()

    def motorDown(self): # NO LONGER USED
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

    def up_cd(self, timestamp, callback_obj, pv={'lastval':1}):
        ''' change detector '''
        if callback_obj.value != pv['lastval']:
            pv['lastval'] = callback_obj.value
            self.upButtonCallback(timestamp, callback_obj)

    def down_cd(self, timestamp, callback_obj, pv={'lastval':1}):
        ''' change detector '''
        if callback_obj.value != pv['lastval']:
            pv['lastval'] = callback_obj.value
            self.downButtonCallback(timestamp, callback_obj)
        else:
            pass
            #print "no change on CB" # This gets printed a lot.
            
class WiFi(object):
    def __init__(self,interface='wlan0'):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.interface=interface
        # Check WiFi status and try to set to 'on', 'off', or 'disabled'
        self.status = self.get_status()
        self.logger.debug("WiFi interface {0} status is {1}".format(interface,self.status))
    def get_status(self):
        try:
            ifconfig1 = subprocess.Popen(['/sbin/ifconfig',self.interface],shell=False,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            ifconfig2 = ifconfig1.communicate()
            ifconfig3 = ifconfig2[0]
            ifconfig4 = ifconfig3.split()
        except Exception as e:
            print(e)
            return 'unknown'
        if 'UP' in ifconfig4:
            self.status = 'on'
        elif len(ifconfig4) > 0:
            self.status = 'off'
        else:
            self.status = 'disabled'
        return self.status
    def start(self):
        # Try to start WiFi
        success = subprocess.call(['sudo','-n','/sbin/ifup',self.interface])
        if success:
            self.logger.info('Started WiFi interface')
            self.status = self.get_status()
        else:
            self.logger.info('Unable to start WiFi interface {0}'.format(success))
        return success # Return non-zero for success
    def stop(self):
        # Try to stop WiFi
        success = subprocess.call(['sudo','-n','/sbin/ifdown',self.interface])
        if success:
            self.logger.info('Stopped WiFi interface')
            self.status = self.get_status()
        else:
            self.logger.info('Unable to stop WiFi interface {0}'.format(success))
        return success # Return non-zero for success

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Usage: ', sys.argv[0], ' ini-file')
        sys.exit(1)
    if os.path.exists(sys.argv[1]) is False:
        print(sys.argv[1], "does not exist")
        sys.exit(1)
    try:
        logger = logging.getLogger('Local_Interface')
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        config = ConfigObj(sys.argv[1])  # Read the config file
        dbh = avp_db.DB_LogHandler(config)
        dbh.setLevel(logging.DEBUG)
        logger.addHandler(dbh)
        li = Local_Interface(config=config, debug_mode=True)
        li.start()
    except KeyboardInterrupt:
        try:
            li.shutdown()
        except:
            pass
