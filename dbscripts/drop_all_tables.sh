#!/bin/bash
# This will drop all tables that begin with this hostname

echo
echo This will drop all tables that begin with `hostname`.
echo

read -n 1 -p "Are you REALLY REALLY sure? [y,N] " toContinue
echo
toContinue=${toContinue:-"n"}
if [ "$toContinue" != "y" ]; then
    echo "Not dropping tables"
    exit 1
fi

psql -c "drop table `hostname`_debug_log;" `hostname` postgres
psql -c "drop table `hostname`_depth;"     `hostname` postgres
psql -c "drop table `hostname`_gps;"       `hostname` postgres
psql -c "drop table `hostname`_isco;"      `hostname` postgres
psql -c "drop table `hostname`_lisst;"     `hostname` postgres
psql -c "drop table `hostname`_log;"       `hostname` postgres
psql -c "drop table `hostname`_power;"     `hostname` postgres
psql -c "drop table `hostname`_schedule;"  `hostname` postgres
psql -c "drop table `hostname`_sonde;"     `hostname` postgres
psql -c "drop table `hostname`_wind;"      `hostname` postgres
psql -c "drop table `hostname`_cast;"      `hostname` postgres
