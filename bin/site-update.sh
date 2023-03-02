#!/bin/bash 
#
# site-update.sh is a script that will change a system from one site to another (e.g. office to deployed).
# It is important that the database mirroring for the system being taken off-line be up to date since this
# script will rebuild the database from the mirrored copy.



echo 
echo Make certain that the mirrored copy of the database is up-to-date with the system being taken off-line.
echo This will go more smoothly if a .pgpass file is set up
echo

# This script must be run as root.  Check to see if we are.
iam=`whoami`
if [ "$iam" != "root" ]; then
    echo This script must be run as root.  Sorry $iam.
    exit 1
fi

read -n 1 -p "Continue? [y,N] " toContinue
toContinue=${toContinue:-"n"}
if [ "$toContinue" != "y" ]; then
    echo "Exiting script"
    exit 1
fi
echo

# change the site name
echo "OK, continuing."
echo
read -p "Enter the new site (host) name: " NEW_SITE_NAME
echo
echo This control box will be changed to \"$NEW_SITE_NAME\".

read -n 1 -p "Continue? [y,N] " toContinue
toContinue=${toContinue:-"n"}
if [ "$toContinue" != "y" ]; then
    echo "Exiting script"
    exit 1
fi
echo

OLD_SITE_NAME=`hostname`    # save the current name of this box
echo Changing hostname in files /etc/hostname and /etc/hosts from $OLD_SITE_NAME to $NEW_SITE_NAME

echo $NEW_SITE_NAME > /etc/hostname
hostname $NEW_SITE_NAME

# Put in temp file and display with y/n option in case of substitution errors
sed s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/hosts > /home/avp/bin/hosts.tmp
echo
echo Check that there were no substitution errors.
echo
cat /home/avp/bin/hosts.tmp
echo
read -n 1 -p "Does this look correct? [y,N] " isCorrect
echo
isCorrect=${isCorrect:-"n"}
if [ "$isCorrect" != "y" ]; then
    echo Leaving this version as /home/avp/bin/hosts.tmp - not modifying original
    echo Edit original correctly when this script finishes.
else
    cp /home/avp/bin/hosts.tmp /etc/hosts
    rm /home/avp/bin/hosts.tmp
fi


#update the .ini file
# echo
# echo Will now modify entries in .ini that point to database tables XXX_cast, XXX_log, XXX_debug_log, XXX_power,
# echo and XXX_schedule.
# echo

# suffix1="_cast"
# suffix2="_log"
# suffix3="_debug_log"
# suffix4="_power"
# suffix5="_schedule"
# sed -e s/$OLD_SITE_NAME$suffix1/$NEW_SITE_NAME$suffix1/g \
    # -e s/$OLD_SITE_NAME$suffix2/$NEW_SITE_NAME$suffix2/g \
    # -e s/$OLD_SITE_NAME$suffix3/$NEW_SITE_NAME$suffix3/g \
    # -e s/$OLD_SITE_NAME$suffix4/$NEW_SITE_NAME$suffix4/g \
    # -e s/$OLD_SITE_NAME$suffix5/$NEW_SITE_NAME$suffix5/g \
    # < /home/avp/python/${OLD_SITE_NAME}_avp.ini > /home/avp/bin/avp.tmp

# chown avp:avp /home/avp/bin/avp.tmp
# cp /home/avp/bin/avp.tmp /home/avp/python/${NEW_SITE_NAME}_avp.ini
# rm /home/avp/bin/avp.tmp


# Set appropriate depth range for this site
echo
echo We need to set appropriate depth values for this site.
echo
read -p "Enter the default initial working depth in meters: " defDepth
read -p "Enter the minimum acceptable depth sounder value: " minDepth
read -p "Enter the maximum acceptable depth sounder value: " maxDepth

if [ -f /home/avp/javp-*/bin/sounder.conf ]; then
	SOUNDER_CONF="/home/avp/javp-*/bin/sounder.conf"
fi
if [ -f /home/avp/javp/lib/$NEW_SITE_NAME/sounder.conf ]; then
	SOUNDER_CONF="/home/avp/javp/lib/$NEW_SITE_NAME/sounder.conf"
else
	if [ -f /home/avp/javp/lib/$OLD_SITE_NAME/sounder.conf ]; then
		mkdir /home/avp/javp/lib/$NEW_SITE_NAME
		cp /home/avp/javp/lib/$OLD_SITE_NAME/*.conf /home/avp/javp/lib/$NEW_SITE_NAME
		SOUNDER_CONF="/home/avp/javp/lib/$NEW_SITE_NAME/sounder.conf"
	fi
fi

sed -e s/DefaultDepthM.*/"DefaultDepthM     $defDepth"/ \
    -e s/MinDepthM.*/"MinDepthM     $minDepth"/ \
    -e s/MaxDepthM.*/"MaxDepthM     $maxDepth"/ \
    < $SOUNDER_CONF > /home/avp/bin/sounder.tmp
cp /home/avp/bin/sounder.tmp $SOUNDER_CONF
cp /home/avp/bin/sounder.tmp /home/avp/javp/lib/sounder.conf
rm /home/avp/bin/sounder.tmp

# Change the java code database ini file
echo
echo Changing the java db.ini file to point to correct database
echo

if [ -f /home/avp/javp-*/bin/db.conf ]; then
	DB_CONF="/home/avp/javp-*/bin/db.conf"
fi
if [ -f /home/avp/javp/lib/$NEW_SITE_NAME/db.conf ]; then
	DB_CONF="/home/avp/javp/lib/$NEW_SITE_NAME/db.conf"
fi

sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < $DB_CONF > /home/avp/bin/db.conf
cp /home/avp/bin/db.conf $DB_CONF
cp /home/avp/bin/db.conf /home/avp/javp/lib/db.conf
rm /home/avp/bin/db.conf

# Set up dynamic DNS if necessary
echo
echo If the dynamic DNS client ddclient is installed we will reconfigure the config for this site.
echo

if [ -f /etc/ddclient.conf ]; then
    echo Here is the current configuration file:
    echo
    cat /etc/ddclient.conf
    echo
    echo We can remove a line if necessary and add a line.  To remove a line enter a search string unique to that line.
    read -p "Line to remove contains (hit enter to not remove a line): " searchString
    if [ -z $searchString ]; then
        cp /etc/ddclient.conf /home/avp/bin/ddclient.tmp
    else
        sed -e "/$searchString/ d" < /etc/ddclient.conf > /home/avp/bin/ddclient.tmp
    fi
    read -p "dyndns hostname under which to register this ip address (must already exist in dyndns): " dnsHost
    echo $dnsHost >> /home/avp/bin/ddclient.tmp
    cp /home/avp/bin/ddclient.tmp /etc/ddclient.conf
    rm /home/avp/bin/ddclient.tmp
    systemctl restart ddclient
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
echo
echo Changing the londiste .ini files to point to the correct database
echo

sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/pgqd.ini > /home/avp/bin/pgqd.ini
cp /home/avp/bin/pgqd.ini /etc/pgqd.ini
rm /home/avp/bin/pgqd.ini
sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3.ini > /home/avp/bin/londiste3.ini
cp /home/avp/bin/londiste3.ini /etc/londiste3.ini
rm /home/avp/bin/londiste3.ini
sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3_storm.ini > /home/avp/bin/londiste3_storm.ini
cp /home/avp/bin/londiste3_storm.ini /etc/londiste3_storm.ini
rm /home/avp/bin/londiste3_storm.ini
sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3_wave.ini > /home/avp/bin/londiste3_wave.ini
cp /home/avp/bin/londiste3_wave.ini /etc/londiste3_wave.ini
rm /home/avp/bin/londiste3_wave.ini

# update the londiste schema script and then run it
sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < create_londiste_schema.sh > cls.tmp
cp cls.tmp create_londiste_schema.sh
rm cls.tmp
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


