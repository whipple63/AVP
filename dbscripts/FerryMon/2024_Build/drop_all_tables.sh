#!/bin/bash
# This will drop all tables that begin with this hostname

# If a command line argument is given the databases will be named by the argument,
# otherwise it will be named by the hostname

DBNAME=`hostname`
if [ "$1" != "" ]; then
    DBNAME=$1
fi

echo
echo This will drop all tables that begin with ${DBNAME}.
echo

read -n 1 -p "Are you REALLY REALLY sure? [y,N] " toContinue
echo
toContinue=${toContinue:-"n"}
if [ "$toContinue" != "y" ]; then
    echo "Not dropping tables"
    exit 1
fi

psql -c "drop table ${DBNAME}_debug_log;" ${DBNAME}
psql -c "drop table ${DBNAME}_gps;"       ${DBNAME}
psql -c "drop table ${DBNAME}_isco;"      ${DBNAME}
psql -c "drop table ${DBNAME}_log;"       ${DBNAME}
psql -c "drop table ${DBNAME}_power;"     ${DBNAME}
psql -c "drop table ${DBNAME}_sonde;"     ${DBNAME}
psql -c "drop table ${DBNAME}_wind;"      ${DBNAME}
psql -c "drop table ${DBNAME}_cast;"      ${DBNAME}
