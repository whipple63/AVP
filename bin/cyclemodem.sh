#!/bin/bash

# Try to detect if we are running on a raspberry pi or not
if [ -d /home/pi ]; then

	python /home/avp/bin/cyclemodem.py
else
		
	echo "Power cycle the modem in 10 seconds"
	sleep 10
	
	# if dio dir for port b is output (0) don't set it (it will turn things off)
	portDir=`/usr/local/bin/aio get_dio_dir 0x220 | awk '{ print $6 }'`
	compTo='0,'
	
	if [ $portDir != $compTo ];
	then
	    # This line might interfere with aio if it was configured differently
	    /usr/local/bin/aio set_dio_dir 0x220 0 0 1 1
	fi
	
	
	# set the pin to the modem power to turn it off
	echo "powering modem down now"
	# this line is for high relay logic
	#/usr/local/bin/aio put_dio_pin 0x220 b 0 1
	# this line is for low relay logic
	/usr/local/bin/aio put_dio_pin 0x220 b 0 0
	
	sleep 15
	
	# reset the pin to turn it back on
	echo "turning modem back on now"
	# this line is for high relay logic
	#/usr/local/bin/aio put_dio_pin 0x220 b 0 0
	# this line is for low relay logic
	/usr/local/bin/aio put_dio_pin 0x220 b 0 1
fi
