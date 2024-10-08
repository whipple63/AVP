#!/bin/sh

# If a command line argument is given the databases will be named by the argument,
# otherwise it will be named by the hostname

DBNAME=`hostname`
if [ "$1" != "" ]; then
    DBNAME=$1
fi

SITE=localhost
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_cast     ${DBNAME}  # Has to be first

psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_gps      ${DBNAME} 
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_isco     ${DBNAME} 
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_log      ${DBNAME} 
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_power    ${DBNAME} 
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_sonde    ${DBNAME} 
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_wind     ${DBNAME} 

