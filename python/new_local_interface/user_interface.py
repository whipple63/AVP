#Built in Modules
import time
import datetime at dt
import logging
import Queue as queue
import subprocess
import sys
import threading

#Installed Modules
import pytz.reference 

#Custom Modules
import pertd2
import avp_winch

class ButtonHandler(threading.Thread):
    """
    Watches the up and down button. Calls one of:
    up_press        - Cald when held at least XXXX
    up_release      - Called when up_press is released
    up_click        - Called when held less than XXXX
    down_press      - Cald when held at least XXXX
    down_release    - Called when down_press is released
    down_click      - Called when held less than XXXX
    both_press      - Called when both are held at least XXXXX
    both_release    - Called when both are released
    both_click      - Called when both are pressed and released within XXXXX
    """
    _DOUBLE_PRESS_DELAY = dt.timedelta(seconds=0.1)  # window which defines double press
    def __init__(self, config, q, group=None, target=None, name=None,
                 args=(), kwargs=None, verbose=None):
        super(ButtonHandler,self).__init__()
        #subscribe to the aio values
        self.setDaemon = True
        self.config = config
        self.q = q
        # Set up AIO broker.
        #
        #
    def start(self):
        super(ButtonHandler,self).start()
    def run(self):
        # record initial values. These will be used to detect change.
        up_value = self.aio.up_button.value
        down_value = self.aio.down_button.value
        # These will be set to current time if both are None and set to None when acted upon
        up_time = None; down_time = None
        # These will be set to True when changed and False when acted upon.
        up_press = False; up_release = False
        down_press = False ; down_release = False
        while True:
            # look for changes in state for both buttons
            # Adapt logic from previous localInterface
            # if state changes, figure out what's happening
            if (up_press or up_release or down_press or down_release): # Has anything changed?
                if up_press and up_release and not down_press: # Simple up press and release (click)
                    up_press = False; up_release = False # Reset these
                    up_time = None
                    q.put('up_click')
                if down_press and down_release and not up_press: # Simple up press and release
                    down_press = False; down_release = False # Reset these
                    down_time = None
                    q.put('down_click')
                if (up_press and up_release and down_press and down_release): 
                    up_press = False; up_release = False # Reset these
                    down_press = False; down_release = False # Reset these
                    up_time = None; down_time = None
                    q.put('both_click')
                if dt.datetime.now() - self.max_time(up_time,down_time) > self._DOUBLE_PRESS_DELAY: # This will fail if both times are None, but that should never happen.
                    #At least one button has been pressed long enough to be a single or both long-press
                    if up_press and down_press:
                        up_press = False; down_press = False
                        up_time = None; down_time = None
                        q.put('both_press')
                        continue
                    if up_release and down_release:
                        up_release = False; down_release = False
                        up_time = None; down_time = None
                        q.put('both_release')
                        continue
                    if up_press or up_release:
                        up_time = None
                        if up_press:
                            up_press = False
                            q.put('up_press')
                        if up_release:
                            up_release = False
                            q.put('up_release')
                    if down_press or down_release:
                        down_time = None
                        if down_press:
                            down_press = False
                            q.put('down_press')
                        if down_release:
                            down_release = False
                            q.put('down_release')
                else:
                    # Still waiting to see if it is a long press
                    pass
            # Now look for value changes
            if self.aio.up_button.value ! = up_value:
                up_value = self.aio.up_button.value
                if down_time is None: # Don't reset time on both press
                    up_time = self.aio.up_button.sample_time
                if up_value == 1:
                    up_press = True
                elif up_value == 0:
                    up_release = True
            if self.aio.down_button.value != down_value:
                down_value = self.aio.down_button.value
                if up_time is None: # Don't reset time on both press
                    down_time = self.aio.down_button.sample_time
                if down_value == 1:
                    down_press = True
                elif down_value == 0:
                    down_value = True
            # Once figures out, call menus.METHOD()
            # Wait on change to either button's date_time.
    def max_time(self,up_time,down_time):
        """ returns lower of the two even if one is None """
        return min( t for t in [up_tiome,down_time] if t is not None )
            
class MenuHandler(threading.Thread,Menu):
    """ Manages menus
    """
    def __init__(self, config, q, group=None, target=None, name=None,
                 args=(), kwargs=None, verbose=None):
        super(MenuHandler,self).__init__()
        self.setDaemon = True
        self.config = config
        self.q = q
        # Instantiate menus
        self.MENUS = ('Sonde Swap','Operate Winch', 'Schedule', 'WiFi','Sonde Data','Wind Data',
                      'Depth Data', 'Power Data')
        self.selected_menu = 0 # Keep track of which menu we are in
        self.top_menu = 0 #Top menu when printing. != selected_menu when near the bottom.
        self.MENU_DATA = {'Sonde Swap':{'menu_class':SondeSwap,'obj':None},
                          'Operate Winch':{'menu_class':OperateWinch,'obj':None}, 
                          'Schedule':{'menu_class':AlterSchedule,'obj':None}, 
                          'WiFi':{'menu_class':AlterWifi,'obj':None},
                          'Sonde Data':{'menu_class':SondeData,'obj':None},
                          'Wind Data':{'menu_class':WindData,'obj':None},
                          'Depth Data':{'menu_class':DepthData,'obj':None}, 
                          'Power Data':{'menu_class':PowerData,'obj':None}}
        # Instantiate menus
        for menu in self.MENUS:
            this_class = self.MENU_DATA[menu]['menu_class']
            self.MENU_DATA[menu]['obj'] = this_class(config) 
        self.in_main_menu = False
        self.current_menu = None # This will be a Menu object when not in main menu
    def start(self):
        super(MenuHandler,self).start()
    def run(self):
        while True:
            task = self.q.get() #Waits for something on the queue
            if self.in_main_menu is True:
                getattr(self,task)() # Run the self method of the same name.
            else:
                getattr(self.current_menu,task)# Run the method of the same name for the current menu.
            self.q.task_done()
    def print_main_menu(self):
        """ Print cursor and main menu
        """
        i = 0
        for line in range(self.top_menu:self.top_menu + 4):
            if self.selected_menu = line:
                cursor = '> '
            else:
                cursor = '  '
            self.lines[i] = '{c:3} {l}'.format(c=cursor,l=self.MENUS[line])
            i += 1
    def up_press(self):
        if in_main_menu is False:
            self.current_menu.up_press()
        else:
            self.up_click() # Main menu treats down presses like clicks
    def up_release(self):
        if in_main_menu is False:
            self.current_menu.up_release()
        else:
            pass # Main menu acts on clicks or presses
    def up_click(self):
        if in_main_menu is False:
            self.current_menu.up_click()
        else:
            print_menu = False
            if self.selected_menu > 0:
                self.selected_menu -= 1
                print_menu = True
            if self.top_menu > 0 and self.top_menu == self.selected_menu:
                self.top_menu -= 1
                print_menu = True
            if print_menu is True:
                self.print_main_menu
    def down_press(self):
        if in_main_menu is False:
            self.current_menu.down_press()
        else:
            self.down_click() # Main menu treats down presses like clicks
    def down_release(self):
        if in_main_menu is False:
            self.current_menu.down_release()
        else:
            pass # Main menu acts on clicks or presses
    def down_click(self):
        if in_main_menu is False:
            self.current_menu.down_click()
        else:
            print_menu = False
            if self.selected_menu > 0:
                self.selected_menu -= 1
                print_menu = True
            if self.top_menu > 0 and self.top_menu == self.selected_menu:
                self.top_menu -= 1
                print_menu = True
            if print_menu is True:
                self.print_main_menu
    def both_press(self):
        if in_main_menu is False:
            self.current_menu.both_press()
        else:
            pass #main menu waits for release
    def both_release(self):
        if in_main_menu is False:
            self.current_menu.both_release()
        else:
            self.both_click() # Main menu treates a press and release like a click.
    def both_click(self):
        if in_main_menu is False:
            self.current_menu.both_click()
        else:
            # Go into currently selected menu
            self.in_main_menu = False
            self.current_menu = self.MENU_DATA[self.MENUS[self.selected_menu]]['obj']
            self.current_menu.start()
        
class Menu(object):
    """ methods and attributes common to all menus
    """
    def __init__(self):
        self.initialized = True
        self.active = False
        self.lines = [None,None,None,None] # Only non-None lines will be printed.
    def print_menu(self,clear=False):
        if clear is True:
            self._lcd.clear_screen()
        for i in range(1:4):
            line_contents = self.lines[i - 1]
                if line_contents != None
                self._lcd.write_line(i,line_contents)
    def enter(self):
        self.active = True
    def exit(self):
        self.active = False
        
    # These will probably be over-ridden
    def up_press(self):
        pass
    def up_release(self):
        pass
    def up_click(self):
       pass
    def down_press(self):
        pass
    def down_release(self):
        pass
    def down_click(self):
        pass
    def both_press(self):
        pass
    def both_release(self):
        pass
    def both_click(self):
        pass
class SondeSwap(Menu):
    """ Handles sonde swap menu """
    def __init__(self):
        super(SondeSwap,self).__init__()
class OperateWinch(Menu):
    """ Manual operation of winch
    """
    def __init__(self):
        super(OperateWinch,self).__init__()
class AlterSchedule(Menu):
    """ Change Schedule Status
    """
    def __init__(self):
        super(AlterSchedule,self).__init__()
class AlterWiFi(Menu):
    """ Change WiFi Status
    """
    def __init__(self):
        super(AlterWiFi,self).__init__()
class SondeData(Menu):
    """ Display Sonde Data
    """
    def __init__(self):
        super(SondeData,self).__init__()
class WindData(Menu):
    """ Display Wind Data
    """
    def __init__(self):
        super(WindData,self).__init__()
class DepthData(Menu):
    """ Display Depth Data
    """
    def __init__(self):
        super(DepthData,self).__init__()
class PowerData(Menu):
    """ Display Power Data
    """
    def __init__(self):
        super(PowerData,self).__init__()
class WelcomeScreen(Menu):
    """ Show some general status information and go to main menu on any key press.
    """
    def __init__(self):
        super(PowerData,self).__init__()
    def start(self):
        self.lines[0] = "Press either button for main menu"
        self.lines[1] = "Cast Status: XXXXXXXXXXXXX"
        self.lines[2] = "future"
        self.lines[3] = "Voltage XX.X Load/Charge Amps X.X/X.X"
        self.print_menu()
        self.run()
    def run(self):
        while self.q.empty() is True:
            # Print Diagnostic Info"
            self.lines[0] = None
            self.lines[1] = "Cast Status: XXXXXXXXXXXXX"
            self.lines[2] = "future"
            self.lines[3] = "Voltage XX.X Load/Charge Amps X.X/X.X"
            self.print_menu()
        # On any key press, this will exit return
        
            
            

        
def main():
    # Get config information
    q = queue.LifoQueue(maxsize=100)
    menu = MenuHandler(config,q)
    menu.start()
    buttons = ButtonHandler(config,q)
    buttons.start(menu)