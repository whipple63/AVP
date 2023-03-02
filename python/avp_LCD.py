#!/usr/bin/python2.6
'''
FORKED ON 20131002
This module provides classes for accessing the Pertelian or ColdTears USB LCD.

Author: neve (at) email.unc.edu

The pertd2 daemon is available at:
    http://www.pertelian.com/pertelian/downloads/community/linux-pertd2006111800.tgz

This module includes all the built in  functionality of pertd2. It also adds
new methods including:
    clear_screen() which can clear one or more lines
    insert() which inserts a string after shifting existing strings up or down.
    
'''

 #Let's use the new print function
from os import fsync
import os
import thread
import time

import pylcdsysinfo as LCD #For the ColdTears

class _LCDUserInterface(object):
    '''
    Contains methods and attributes common to all LCD interfaces
    '''
    VALID_MODES = ['on','off']
    def __init__(self,LINES_LCD,lcd_dict):
        self.VALID_LINES = list(range(1,LINES_LCD + 1)) # This will be [1,2,3,...,n]
        self.lcd_dict = lcd_dict
        for line_num in self.VALID_LINES: # Initialize the dictionary with blanks, even though it may not be blank.
            self.lcd_dict[line_num] = ''
    def get_display(self):
        ''' Returns current contents of lcd screen as a dictionary.'''
        return self.lcd_dict
    def clear_screen(self,lines=0,clear_str=' '):
        ''' Clears all the lines in passed list.'''
        if lines == 0 : lines = self.VALID_LINES
        for line_num in lines:
            self.clear_line(line_num,clear_str)
        return 1
    def clear_line(self,line_num,clear_str=''):
        if line_num in self.VALID_LINES:
            self.write_line(line_num,clear_str,0,clear_line=False)
    def _shift_up(self, scroll_lines = None, delay=0):
        ''' Shifts requested lines up one position.'''
        if scroll_lines is None:
            scroll_lines = self.VALID_LINES[1:]
        for line_num in scroll_lines:
            self.write_line(line_num - 1,self.lcd_dict[line_num],delay,hold_open=1)
            print("Wrote {0} to {1}".format(self.lcd_dict[line_num + 1],line_num + 1))
    def _shift_down(self, scroll_lines = None,delay=0):
        ''' Shifts requested lines down one position'''
        print("Shifting Down {0}".format(scroll_lines))
        if scroll_lines is None:
            scroll_lines = self.VALID_LINES[:-1]
            scroll_lines.reverse()
        for line_num in scroll_lines:
            self.write_line(line_num + 1,self.lcd_dict[line_num],delay,hold_open=1)
            print("Wrote {0} to {1}".format(self.lcd_dict[line_num + 1],line_num + 1))
        try:
            self._close_pipe()
        except AttributeError:
            pass
    def insert(self,line_num,display_string,direction,delay=0):
        ''' Shifts lines and inserts new line.'''
        if line_num in self.VALID_LINES:
            if direction == 'up':
                scroll_lines = list(range(2,line_num + 1))
                self._shift_up(scroll_lines,delay)
            elif direction == 'down':
                scroll_lines = list(range(len(self.VALID_LINES) -1,line_num - 1,-1))
                self._shift_down(scroll_lines,delay)
            else:
                print("Valid directions are 'up' and 'down'")
                return 0
            result = self.write_line(line_num,display_string,0)
            return result
        else:
            print("Valid lines are {0}".format(self.VALID_LINES))
            return 0
            
            
class Pertelian(_LCDUserInterface):
    ''' Allows access to and extends functionality of Pertelian LCD pertd2 daemon
    '''
    LINES_LCD = 4
    COLUMNS_LCD = 20
    def __init__(self,fifo_file = '/tmp/pertd2.fifo'):
        self.lcd_dict = {}
        super(Pertelian,self).__init__(self.LINES_LCD,self.lcd_dict)
        if not os.path.exists(fifo_file):
            print(fifo_file,"does not exist")
        self.fifo_file = fifo_file
    def _open_pipe(self):
        ''' Opens the pipe (file) for writing.'''
        self.fifo = open(self.fifo_file,'w')
    def _close_pipe(self):
        ''' Closes the FIFO pipe.'''
        self.fifo.close()
    def _flush_pipe(self):
        ''' flushes the FIFO pipe without closing it.'''
        self.fifo.flush()
    def _write_pipe(self,command_str,hold_open=0):
        ''' Opens the pipe, writes to it, then closes the pipe.'''
        self._open_pipe()
        if command_str[-1] != '\n': command_str += '\n' # Add a trailing CR?
        #print(command_str,end='')
        try:
            self.fifo.write(command_str)
        finally:
            # If we've been told to keep the pipe open , don't close it.
            if not hold_open:
                self._close_pipe()
            else:
                self._flush_pipe()
                fsync(self.fifo.fileno()) # make sure we commit this to disk
    def light(self,mode):
        ''' Turns backlight on or off.
        
        Built in functionality.'''
        if mode in self.VALID_MODES:
            self._write_pipe('backlight {0}'.format(mode))
            return 1
        else:
            print('Error: {0} is not valid. Valid modes are {1}'.format(mode, self.VALID_MODES))
            return 0
    def delay_time(self,delay):
        ''' Sets the interval between screen refreshes in ms.
        
        This will basically control how fast the Pertelian scrolls the data 
        across the screen.
        Built in functionality.'''
        self._write_pipe('delay time\n{0}'.format(delay))
        return 1
    def char_time(self,delay):
        ''' Sets  delay between each character sent to the Pertelian.
        
        This delay
        prevents the program from sending data too fast and causing garbled 
        output on the display. Newer systems may not need any delay, so
        this is configurable. The delay is in ms.     
        1 ms is usually needed for old systems. If your display is very slow,
        reduce this to 0. If the output is garbled, put it to 1.
        Built in functionality.'''
        self._write_pipe('char delay\n{0}'.format(delay))
        return 1
    def backlight_mgt(self,mode):
        ''' Sets whether you want pertd2 to manage the backlight or not.
        
        If enabled, backlight is turned on when there is data to display and
        off when there is no data. 
        Built in functionality.'''
        if mode in self.VALID_MODES:
            self._write_pipe('backlight mgt {0}'.format(mode))
            return 1
        else:
            print('Valid modes are:',self.VALID_MODES)
            return 0
    def stop_pertd2(self):
        ''' Tells pertd2 daemon to exit.
        
        If pertd2 is starting automatically, this probably isn't needed.
        Built in functionality.'''
        self._write_pipe('stop')
        return 1
    def write_line(self,line,display_string,delay=0,hold_open=0,color=None,**kwargs):
        ''' Writes a single line to the LCD.
        
        Takes a line number (1-4), a string and an optional delay in seconds as arguments.'''
        if line in self.VALID_LINES:
            self.lcd_dict[line] = display_string # Put the line in a dictionary
            write_str = "line{0}\n{1}\n==EOD==\n{2}\n==EOD==".format(line,delay,display_string)
            self._write_pipe(write_str,hold_open=hold_open)
            return 1
        else:
            print("{0} is not a valid line number: {1}".format(line, str(self.VALID_LINES)))
            return 0
    def restore_defaults(self):
        self.delay_time(500000) # Set delay time to .5 a second
        self.backlight_mgt('off') # Turn off backlight mgmt
        self.char_time(0)
        
class ColdTears(_LCDUserInterface):
    ''' Interface to ColdTears four line color LCD
    '''
    LINES_LCD = 6
    COLUMNS_LCD = 20
    BRIGHTNESS_ON = 200 # 0 -> 255
    BRIGHTNESS_OFF = 50 # 0 -> 255
    def __init__(self,brightness=255):
        self.lcd_dict = {}
        super(ColdTears,self).__init__(self.LINES_LCD,self.lcd_dict)
        self.lcd = LCD.LCDSysInfo()
        self.lcd.clear_lines(LCD.TextLines.ALL,LCD.BackgroundColours.BLACK)
        self.lcd.dim_when_idle(True)
        self.lcd.set_brightness(brightness)
        self.lcd.save_brightness(127,brightness)
        self.lcd.set_text_background_colour(LCD.BackgroundColours.BLACK)
    def write_line(self,line_num,display_string,delay=.4,hold_open=0,color=LCD.TextColours.GREEN,clear_line=True):
        ''' Writes a single line to the LCD.
           delay and hold_open have no functionality but are included to maintain compatibility with Pertelian.
        Takes a line number (1-4), a string and an optional delay in seconds as arguments.'''
        if line_num in self.VALID_LINES:
            if clear_line is True:
                self.clear_line(line_num)
            print("    writing {1}:{0}".format(display_string,line_num))
            self.lcd_dict[line_num] = display_string
            if len(display_string) > self.COLUMNS_LCD:
                thread.start_new_thread(self.scroll,(line_num,delay,color))
            else:
                self.lcd.display_text_on_line(line_num, display_string, False, None, color)
        else:
            print("{0} is not a valid line number: {1}".format(line_num, str(self.VALID_LINES)))
            return 0
    def scroll(self,line_num,delay=.1,color=LCD.TextColours.GREEN):
        print('{1} Scrolling {0}'.format(self.lcd_dict[line_num],line_num))
        line_to_scroll = self.lcd_dict[line_num]
        line_length = len(line_to_scroll)
        n = 0
        while ( line_to_scroll == self.lcd_dict[line_num]):
            n+=1
            if n > line_length:
                n = 0
            display_string = line_to_scroll[n:line_length] + line_to_scroll[0:n]
            self.lcd.display_text_on_line(line_num, display_string, False, None, color)
            time.sleep(delay)
        print("{0} Scroll done".format(line_num))
    def light(self,mode):
        ''' Turns backlight on or off.
        
        Built in functionality.'''
        if mode is 'on':
            self.lcd.set_brightness(self.BRIGHTNESS_ON)
            return 1
        elif mode is 'off':
            self.lcd.set_brightness(self.BRIGHTNESS_OFF)
            return 1
        else:
            print('Error: {0} is not valid. Valid modes are {1}'.format(mode, self.VALID_MODES))
            return 0
    def clear_screen(self,lines=0,clear_str='',colour=LCD.BackgroundColours.BLACK):
        self.lcd.clear_lines(LCD.TextLines.ALL,colour)
        for line_num in self.lcd_dict:
            self.lcd_dict[line_num] = clear_str
    def clear_line(self,line_num,colour=LCD.BackgroundColours.BLACK):
        lines = 1 << line_num - 1
        print("    clearing {0} ({1},{2})".format(line_num,lines,colour))
        self.lcd.clear_lines(lines,colour)
        self.lcd_dict[line_num] = ''
    def delay_time(self,delay):
        pass
    def restore_defaults(self):
        pass

def example():
    lcd = ColdTears()
    time.sleep(5)
    print("Turning on light and writing to the screen")
    lcd.light('on') # LCD light on
    lcd.delay_time(100000) # Set delay time to .1 a second
    # Write something to each of the four lines
    lcd.write_line(1,' Welcome to AVP3  ',0)  # The last 0 indicates no timeout and is optional.
    # This should scroll line 2 horizontally. If you are over 20 characters, add trailing spaces for clarity.
    lcd.write_line(2,'Press both buttons for 5 seconds to enter manual mode    ') 
    lcd.write_line(3,'       WAITING     ')
    lcd.write_line(4,'   [Raise] [Lower]  ')
    time.sleep(8)
    lcd.insert(2,'  v  v  v  v  v','down') #moves 3 to 4, 2 to 3, and inserts this at the second line
    time.sleep(1)
    print("\n\n\n")
    lcd.insert(2,'  a  a  |  |  |','down')
    time.sleep(1)
    print("\n\n\n")
    lcd.insert(2,'  a  a  |  |  |','down')
    time.sleep(1)
    print( "\n\n\n" )
    lcd.write_line(1,'      THE END',4) # Times out after 4 seconds
    time.sleep(5)
    print("\n\n\n")
    lcd.clear_screen() # Could have said lcd.clear_screen(1,2,3,4)
    lcd.light('off') # Don't forget to turn off light
    lcd.restore_defaults()

       
if __name__ == "__main__":
    example()
