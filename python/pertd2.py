#!/usr/bin/python2.6
'''
This module provides a class for accessing the Pertelian USB LCD through the pertd2 daemon.

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
class Pertelian(object):
    ''' Allows access to and extends functionality of Pertelian LCD pertd2 daemon
    '''
    VALID_LINES = [1,2,3,4]
    VALID_MODES = ['on','off']
    def __init__(self,fifo_file = '/tmp/pertd2.fifo'):
        import os
        if not os.path.exists(fifo_file):
            print(fifo_file,"does not exist")
        self.fifo_file = fifo_file
        self.lcd_dict = {}
        for line in self.VALID_LINES: # Iniitalize the dictionary with blanks, even though it may not be blank.
            self.lcd_dict[line] = ' '
    def get_display(self):
        ''' Returns current contents of lcd screen as a dictionary.'''
        return self.lcd_dict
    def _open_pipe(self):
        ''' Opens the pipe (file) for writing.'''
        self.fifo = open(self.fifo_file,'w')
    def _close_pipe(self):
        ''' Closes the fifo pipe.'''
        self.fifo.close()
    def _flush_pipe(self):
        ''' flushes the fifo pipe without closing it.'''
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
    def write_line(self,line,display_string,delay=0,hold_open=0):
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
    def clear_screen(self,lines=0):
        ''' Clears all the lines in passed list.'''
        if lines == 0 : lines = self.VALID_LINES
        for line in lines:
            if line in self.VALID_LINES:
                self.lcd_dict[line] = " " # Clear line from dictionary
                self.write_line(line," ",0)
        return 1
    def _shift_up(self, scroll_lines = (2,3,4), delay=0):
        ''' Shifts requested lines up one position.'''
        for line in scroll_lines:
            self.write_line(line - 1,self.lcd_dict[line],delay,hold_open=1)
    def _shift_down(self, scroll_lines = (3,2,1),delay=0):
        ''' Shifts requested lines down one position'''
        for line in scroll_lines:
            self.write_line(line + 1,self.lcd_dict[line],delay,hold_open=1)
        self._close_pipe()
    def insert(self,line,display_string,direction,delay=0):
        ''' Shifts lines and inserts new line.'''
        if line in self.VALID_LINES:
            if direction == 'up':
                scroll_lines = list(range(2,line + 1))
                self._shift_up(scroll_lines,delay)
            elif direction == 'down':
                scroll_lines = list(range(3,line - 1,-1))
                self._shift_down(scroll_lines,delay)
            else:
                print("Valid directions are 'up' and 'down'")
                return 0
            return (self.write_line(line,display_string,0))
        else:
            print("Valid lines are {0}".format(self.VALID_LINES))
            return 0
        
def restore_defaults():
    lcd.delay_time(500000) # Set delay time to .5 a second
    lcd.backlight_mgt('off') # Turn off backlight mgmt
    lcd.char_time(0)

def example():
    import time
    lcd = Pertelian()
    time.sleep(5)
    print("Turning on light and writing to the screen")
    lcd.light('on') # LCD light on
    lcd.delay_time(100000) # Set delay time to .1 a second
    # Write something to each of the four lines
    lcd.write_line(1,' Welcome to AVP3  ',0)  # The last 0 indicates no timeout and is optional.
    time.sleep(1)
    # This should scroll line 2 horizontally. If you are over 20 characters, add trailing speaces for clarity.
    lcd.write_line(2,'Press both buttons for 5 seconds to enter manual mode    ') 
    time.sleep(1)
    lcd.write_line(3,'       WAITING     ')
    time.sleep(1)
    lcd.write_line(4,'   [Raise] [Lower]  ')
    time.sleep(8)
    lcd.insert(2,'  v  v  v  v  v','down') #moves 3 to 4, 2 to 3, and inserts this at the second line
    time.sleep(1)
    lcd.insert(2,'  |  |  |  |  |','down')
    time.sleep(1)
    lcd.insert(3,'  |  |  |  |  |','down')
    time.sleep(1)
    lcd.write_line(1,'      THE END',4) # Times out after 4 seconds
    time.sleep(5)
    lcd.clear_screen() # Could have said lcd.clear_screen(1,2,3,4)
    lcd.light('off') # Don't forget to turn off light
    restore_defaults(lcd)

def restore_defaults(lcd):
    lcd.delay_time(500000) # Set delay time to .5 a second
    lcd.backlight_mgt('off') # Turn off backlight mgmt
    lcd.char_time(0)
       
if __name__ == "__main__":
    example()
