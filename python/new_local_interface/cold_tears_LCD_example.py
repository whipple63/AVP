#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import pylcdsysinfo as LCD
# BackgroundColours, COL2LEFT, TextColours, TextAlignment, TextLines, LCDSysInfo, large_image_imdexes
import math
from time import sleep,time
import datetime

d = LCD.LCDSysInfo()
d.clear_lines(LCD.TextLines.ALL, LCD.BackgroundColours.BLACK)
d.dim_when_idle(False)
d.set_brightness(255)
d.save_brightness(127, 255)

# System Info
d.set_text_background_colour(LCD.BackgroundColours.BLACK)
d.display_icon(0, LCD.large_image_indexes[7])
d.display_text_on_line(1, "{0}".format('Welcome to AVP4'), False, LCD.TextAlignment.CENTRE, LCD.TextColours.WHITE)

update_display_period = 1  # number of seconds to wait before updating display
floor = math.floor  # minor optimization

line_num = 6

d.dim_when_idle(False)
d.set_brightness(127)
d.save_brightness(127, 255)
d.set_text_background_colour(LCD.BackgroundColours.BLACK)

while 1:
    clock_str = str(datetime.datetime.now()).split('.')[0]
    d.display_text_on_line(line_num, clock_str, False, None, LCD.TextColours.GREEN)

    # Work out when to wake up for the next round/whole (non-fractional) time
    start_time = time()
    future_time = floor(start_time) + update_display_period  # pure float math
    sleep_time = future_time - start_time
    sleep(sleep_time)


