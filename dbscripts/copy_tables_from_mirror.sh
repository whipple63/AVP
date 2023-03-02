#!/bin/bash

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
dropdb --if-exists --host="localhost" --port=5432 --username=postgres `hostname`

echo copying data from mirror site
pg_dump --host="storm.ims.unc.edu" --port=5432 --username=postgres `hostname` --table=`hostname`* > /data/dbdump
echo populating tables from mirror site data
createdb --host="localhost" --port=5432 --username=postgres `hostname`
psql -U postgres -f /data/dbdump `hostname`
# create the local tables
psql -U postgres -d `hostname` -f avp_ipc
psql -U postgres -d `hostname` -f avp_log

# now sequence values need to be updated
echo updating sequence values
psql -c "select setval('`hostname`_cast_cast_no_seq', max(cast_no)) from `hostname`_cast;" `hostname` postgres
psql -c "select setval('`hostname`_log_entry_no_seq', max(entry_no)) from `hostname`_log;" `hostname` postgres
psql -c "select setval('`hostname`_schedule_entry_no_seq', max(entry_no)) from `hostname`_schedule;" `hostname` postgres

