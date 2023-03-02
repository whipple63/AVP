#!/bin/bash 
#
# site-update.sh is a script that will change a system from one site to another (e.g. office to deployed).
# It is important that the database mirroring for the system being taken off-line be up to date since this
# script will rebuild the database from the mirrored copy.

# for debugging
#set -x


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
sed s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/hosts > /home/pi/bin/hosts.tmp
echo
echo Check that there were no substitution errors.
echo
cat /home/pi/bin/hosts.tmp
echo
read -n 1 -p "Does this look correct? [y,N] " isCorrect
echo
isCorrect=${isCorrect:-"n"}
if [ "$isCorrect" != "y" ]; then
    echo Leaving this version as /home/pi/bin/hosts.tmp - not modifying original
    echo Edit original correctly when this script finishes.
else
    cp /home/pi/bin/hosts.tmp /etc/hosts
    rm /home/pi/bin/hosts.tmp
fi

# if necessary, create the conf file folder for the java conf files
if [ ! -d /home/pi/javp/lib/$NEW_SITE_NAME ]; then
	mkdir /home/pi/javp/lib/$NEW_SITE_NAME
	cp /home/pi/javp/lib/$OLD_SITE_NAME/* /home/pi/javp/lib/$NEW_SITE_NAME
fi

# Change the java code database ini file
echo
echo Changing the java db.ini file to point to correct database
echo

if [ -f /home/pi/javp-*/bin/db.conf ]; then
	DB_CONF="/home/pi/javp-*/bin/db.conf"
fi
if [ -f /home/pi/javp/lib/$OLD_SITE_NAME/db.conf ]; then
	DB_CONF="/home/pi/javp/lib/$OLD_SITE_NAME/db.conf"
fi

sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < $DB_CONF > /home/pi/bin/db.conf
cp /home/pi/bin/db.conf /home/pi/javp/lib/$NEW_SITE_NAME/db.conf
rm /home/pi/bin/db.conf

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
        cp /etc/ddclient.conf /home/pi/bin/ddclient.tmp
    else
        sed -e "/$searchString/ d" < /etc/ddclient.conf > /home/pi/bin/ddclient.tmp
    fi
    read -p "dyndns hostname under which to register this ip address (must already exist in dyndns): " dnsHost
    echo $dnsHost >> /home/pi/bin/ddclient.tmp
    cp /home/pi/bin/ddclient.tmp /etc/ddclient.conf
    rm /home/pi/bin/ddclient.tmp
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

# Ask if we are copying existing tables from the mirror or creating new tables.
# Because of replication, if they exist on the mirror we should copy them.  Only
# if they don't already exist do we set up new one.
pushd .
cd /home/pi/dbscripts
if psql --host="wave.ims.unc.edu" --port=5432 --username=postgres -lqt | cut -d \| -f 1 | grep -qw `hostname`; then
    echo Database `hostname` exists on wave.ims.unc.edu - copying
	./copy_tables_from_mirror.sh
else
    echo Database `hostname` does not exist on wave.ims.unc.edu
    read -n 1 -p "Would you like to set up new databases (on local and replication sites)? [y,N]: " addDB

    addDB=${addDB:-"n"}
    if [ "$addDB" == "y" ]; then
		./create_db_storm.sh `hostname`
		./create_db_wave.sh `hostname`
		./copy_tables_from_mirror.sh
	fi
fi
popd


#edit the .ini files to point to the correct database
echo
echo Changing the londiste .ini files to point to the correct database
echo

sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3.ini > /home/pi/bin/londiste3.ini
cp /home/pi/bin/londiste3.ini /etc/londiste3.ini
rm /home/pi/bin/londiste3.ini
sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3_storm.ini > /home/pi/bin/londiste3_storm.ini
cp /home/pi/bin/londiste3_storm.ini /etc/londiste3_storm.ini
rm /home/pi/bin/londiste3_storm.ini
sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/londiste3_wave.ini > /home/pi/bin/londiste3_wave.ini
cp /home/pi/bin/londiste3_wave.ini /etc/londiste3_wave.ini
rm /home/pi/bin/londiste3_wave.ini
sed -e s/$OLD_SITE_NAME/$NEW_SITE_NAME/g < /etc/pgqd.ini > /home/pi/bin/pgqd.ini
cp /home/pi/bin/pgqd.ini /etc/pgqd.ini
rm /home/pi/bin/pgqd.ini

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
        echo "$NEW_SITE_NAME"{_cast,_log,_power,_wind,_gps,_sonde,_isco}
        londiste3 /etc/londiste3.ini add-table "$NEW_SITE_NAME"{_cast,_log,_power,_wind,_gps,_sonde,_isco}
    fi
    echo
    read -n 1 -p "Does the subscriber(s) need to add these tables as well? [y,N]: " addTables

    addTables=${addTables:-"n"}
    if [ "$addTables" == "y" ]; then
        echo
        echo "Adding Tables"
        echo "$NEW_SITE_NAME"{_cast,_log,_power,_wind,_gps,_sonde,_isco}
        londiste3 /etc/londiste3_storm.ini add-table "$NEW_SITE_NAME"{_cast,_log,_power,_wind,_gps,_sonde,_isco}
        londiste3 /etc/londiste3_wave.ini add-table "$NEW_SITE_NAME"{_cast,_log,_power,_wind,_gps,_sonde,_isco}
    fi
	echo
	echo Just about finished.  Do you have a correctly named ini file in the python folder?
	echo If so, it would probably be a good idea to reboot now.
	echo
fi


