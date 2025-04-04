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

# steps for internal postgres replication
#   - drop slots that use OLD_SITE_NAME
echo
echo Removing subscriptions, publications, and replication slots with $OLD_SITE_NAME
echo
cmd="DROP SUBSCRIPTION IF EXISTS "$OLD_SITE_NAME"_wave_sub;"
psql --host="wave.ims.unc.edu" --port=5432 --username=postgres -d $OLD_SITE_NAME -c "$cmd"
cmd="DROP SUBSCRIPTION IF EXISTS "$OLD_SITE_NAME"_storm_sub;"
psql --host="storm.ims.unc.edu" --port=5432 --username=postgres -d $OLD_SITE_NAME -c "$cmd"
cmd="DROP PUBLICATION IF EXISTS "$OLD_SITE_NAME"_pub;"
su pi -c "psql -d $OLD_SITE_NAME -c \"$cmd\""

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


#
# create publication with $NEW_SITE_NAME
# create subscriptions
#
cmd="CREATE PUBLICATION "$NEW_SITE_NAME"_pub FOR ALL TABLES;"
su pi -c "psql -d $NEW_SITE_NAME -c \"$cmd\""
cmd="CREATE SUBSCRIPTION "$NEW_SITE_NAME"_wave_sub CONNECTION 'host="$NEW_SITE_NAME".dyndns.org port=5432 user=pi password=ims6841 dbname="$NEW_SITE_NAME"' PUBLICATION "$NEW_SITE_NAME"_pub;"
psql --host="wave.ims.unc.edu" --port=5432 --username=postgres -d $NEW_SITE_NAME -c "$cmd"
cmd="CREATE SUBSCRIPTION "$NEW_SITE_NAME"_storm_sub CONNECTION 'host="$NEW_SITE_NAME".dyndns.org port=5432 user=pi password=ims6841 dbname="$NEW_SITE_NAME"' PUBLICATION "$NEW_SITE_NAME"_pub;"
psql --host="storm.ims.unc.edu" --port=5432 --username=postgres -d $NEW_SITE_NAME -c "$cmd"


