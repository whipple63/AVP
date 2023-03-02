#!/bin/sh

# call shutdown to go into maintenance mode
echo " "
echo "SUICIDE shutdown triggered - hardware power relay will be OFF!"
echo "SUICIDE shutdown triggered - hardware power relay will be OFF!"
echo "SUICIDE shutdown triggered - hardware power relay will be OFF!"
echo " "
killall python

# wait a while for it to happen
echo "Waiting for 30 seconds"
sleep 30

killall -9 python
killall java
# Since the database is running as postgres user, we need to use a special mechanism
/var/lib/postgresql/bin/avp_setuid


sync
echo "Powering off"

# turn off the power
if [ -d /home/pi ]; then
    sudo shutdown -h now
else
    /home/avp/bin/suicide.sh
fi


