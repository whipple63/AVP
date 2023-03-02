#!/bin/bash
#
# Starts AVP Supervisor 
#
python /home/avp/python/supervisor.py /home/avp/python/`hostname`_avp.ini 2>&1 | tee -a /data/log/supervisor.log