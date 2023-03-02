#!/bin/bash
# initializes socat on various devices in /dev
#port=55231
#
#devices='ttyS1 ttyS2 ttyS3 ttyS4 ttyS5 ttyS6 ttyS7 ttyS8 ttyS9 tension teensy'
#for device in $devices
#do
#  /home/avp/bin/init_socat.sh $port $device
#  ((port++))
#done

/usr/bin/socat tcp-l:55232,reuseaddr,fork file:/dev/ttyUSB0,nonblock,echo=0,raw,icrnl=0,igncr=0,waitlock=/run/lock/socat.ttyUSB0.lockman &
