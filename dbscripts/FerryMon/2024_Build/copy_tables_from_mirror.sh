#!/bin/bash
set -x 

echo
echo This will copy the entire database called `hostname` from the mirror
echo by dropping it locally, re-creating, and then dumping the mirror data here.
echo

read -n 1 -p "Are you sure? [y,N] " toContinue
echo
toContinue=${toContinue:-"n"}
if [ "$toContinue" != "y" ]; then
    echo "Not copying the tables."
    exit 1
fi

# pgq and londiste cannot be running
dropdb --if-exists --host="localhost" --port=5432 --username=pi `hostname`

echo copying data from mirror site
pg_dump --host="wave.ims.unc.edu" --port=5432 --username=postgres `hostname` --table=`hostname`* > /home/pi/dbdump
echo populating tables from mirror site data
createdb --host="localhost" --port=5432 --username=pi `hostname`
psql -U pi  -h 127.0.0.1 -f /home/pi/dbdump `hostname`
# create the local tables
psql -U pi  -h 127.0.0.1 -d `hostname` -f avp_log

# now sequence values need to be updated
echo updating sequence values
psql -U pi -h 127.0.0.1 -c "select setval('`hostname`_cast_cast_no_seq', max(cast_no)) from `hostname`_cast;" `hostname` 
psql -U pi -h 127.0.0.1 -c "select setval('`hostname`_log_entry_no_seq', max(entry_no)) from `hostname`_log;" `hostname` 
psql -U pi -h 127.0.0.1 -c "select setval('`hostname`_schedule_entry_no_seq', max(entry_no)) from `hostname`_schedule;" `hostname` 
