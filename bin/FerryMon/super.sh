#!/bin/bash
#
# Starts AVP Supervisor 
#
python /home/pi/python/supervisor.py /home/pi/python/`hostname`_avp.ini 2>&1 | tee -a ~pi/log/supervisor.log

