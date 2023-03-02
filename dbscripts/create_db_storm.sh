#!/bin/sh

# If a command line argument is given the databases will be named by the argument,
# otherwise it will be named by the hostname

DBNAME=`hostname`
if [ "$1" != "" ]; then
    DBNAME=$1
fi

SITE=storm.ims.unc.edu
createdb -h ${SITE} --username=postgres --tablespace=avp ${DBNAME}
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_cast     ${DBNAME} postgres # Has to be first

psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_depth    ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_gps      ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_isco     ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_lisst    ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_log      ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_power    ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_schedule ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_sonde    ${DBNAME} postgres
psql -h ${SITE} -v dbprefix=${DBNAME} -f avp_wind     ${DBNAME} postgres

