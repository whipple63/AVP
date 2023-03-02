#!/bin/bash
# This script sets baud rates on startup

declare -a ports
declare -a bauds
declare -a desc

desc[0]="Motion Mind 3 (MM3)"
ports[0]="ttyS1"
bauds[0]=19200

desc[1]="Wind NMEA" # Airmar version includes GPS functionality
ports[1]="ttyS2"
bauds[1]=4800

desc[2]="Sonde"
ports[2]="ttyS3"
bauds[2]=9600

desc[3]="Future"
ports[3]="ttyS4"
bauds[3]=9600

desc[4]="Isco"
ports[4]="ttyS5"
bauds[4]=19200

desc[5]="LISST"
ports[5]="ttyS6"
bauds[5]=9600

desc[6]="Depth (NMEA)"
ports[6]="ttyS7"
bauds[6]=4800

desc[7]="ADCP"
ports[7]="ttyS8"
bauds[7]=9600

desc[8]="GPS (NMEA)"
ports[8]="ttyS9"
bauds[8]=4800

desc[9]="Tension Monitor"
ports[9]="tension"
bauds[9]=9600

desc[10]="Teensy current monitor"
ports[10]="teensy"
bauds[10]=57600

declare dev_cnt=10
for port in `seq 0 ${dev_cnt}`
do
   if [ -L /dev/${ports[port]} ]
   then 
        stty -F /dev/${ports[port]} ${bauds[port]} raw -echo
        echo "set ${desc[port]} on /dev/${ports[port]} to ${bauds[port]} baud"
   else
        echo "${desc[port]} does not exist on /dev/${ports[port]}"
   fi
done