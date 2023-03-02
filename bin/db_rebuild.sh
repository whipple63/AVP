#!/bin/bash 
#
# This is a modification of the existing scripts to only rebuild the database from one of the mirrors
# on an existing system.  (For example if the SD card got corrupted and we are replacing it with one that 
# has an older database on it.)


# This script must be run as root.  Check to see if we are.
iam=`whoami`
if [ "$iam" != "root" ]; then
    echo This script must be run as root.  Sorry $iam.
    exit 1
fi

# Now the database needs to be rebuilt.  We will need to drop any old tables with the names we want,
# create new tables with those names, and copy them from the remote mirror site.
echo
echo Removing Londiste processes if running
echo
pgqd /etc/pgqd.ini -s
londiste3 -s /etc/londiste3.ini
londiste3 -s /etc/londiste3_wave.ini
londiste3 -s /etc/londiste3_storm.ini
killall londiste3
killall pgqd
pushd .
cd /home/avp/dbscripts
./copy_tables_from_mirror.sh
popd

#edit the .ini files to point to the correct database
# echo
# echo Changing the londiste .ini files to point to the correct database
# echo

# sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/pgqd.ini > /home/avp/bin/pgqd.ini
# cp /home/avp/bin/pgqd.ini /etc/pgqd.ini
# rm /home/avp/bin/pgqd.ini
# sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3.ini > /home/avp/bin/londiste3.ini
# cp /home/avp/bin/londiste3.ini /etc/londiste3.ini
# rm /home/avp/bin/londiste3.ini
# sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3_storm.ini > /home/avp/bin/londiste3_storm.ini
# cp /home/avp/bin/londiste3_storm.ini /etc/londiste3_storm.ini
# rm /home/avp/bin/londiste3_storm.ini
# sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3_wave.ini > /home/avp/bin/londiste3_wave.ini
# cp /home/avp/bin/londiste3_wave.ini /etc/londiste3_wave.ini
# rm /home/avp/bin/londiste3_wave.ini

# update the londiste schema script and then run it
#sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < create_londiste_schema.sh > cls.tmp
#cp cls.tmp create_londiste_schema.sh
#rm cls.tmp
./create_londiste_schema.sh

# Try to start londiste3 daemons
pgqd /etc/pgqd.ini -d 
londiste3 -d /etc/londiste3.ini worker
londiste3 -d /etc/londiste3_wave.ini worker
londiste3 -d /etc/londiste3_storm.ini worker

# Add the tables to Londiste for database replication if desired
tickerPID=`pgrep -f pgqd`
if [ -z "$tickerPID" ]; then
    echo
    echo Ticker not found.  Replication is not running.
	echo This will need to be set up manually.
    echo
else
    echo
    read -n 1 -p "Would you like to add the tables to londiste for replication? [y,N]: " addTables

    addTables=${addTables:-"n"}
    if [ "$addTables" == "y" ]; then
        echo
        echo "Adding Tables"
        echo "$NEW_SITE_NAME"{_cast,_depth,_log,_power,_schedule,_wind,_gps,_sonde,_isco,_lisst}
        londiste3 /etc/londiste3.ini add-table "$NEW_SITE_NAME"{_cast,_depth,_log,_power,_schedule,_wind,_gps,_sonde,_isco,_lisst}
    fi
    echo
    read -n 1 -p "Does the subscriber(s) need to add these tables as well? [y,N]: " addTables

    addTables=${addTables:-"n"}
    if [ "$addTables" == "y" ]; then
        echo
        echo "Adding Tables"
        echo "$NEW_SITE_NAME"{_cast,_depth,_log,_power,_schedule,_wind,_gps,_sonde,_isco,_lisst}
        londiste3 /etc/londiste3_storm.ini add-table "$NEW_SITE_NAME"{_cast,_depth,_log,_power,_schedule,_wind,_gps,_sonde,_isco,_lisst}
        londiste3 /etc/londiste3_wave.ini add-table "$NEW_SITE_NAME"{_cast,_depth,_log,_power,_schedule,_wind,_gps,_sonde,_isco,_lisst}
    fi
	echo
	echo The subscriber londiste3 worker process may need to be restarted in order to re-connect with this new provider.
	echo
fi


