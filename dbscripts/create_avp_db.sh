#!/bin/sh
SITE=`hostname`
createdb --username=postgres --tablespace=avp `hostname`
psql -h ${SITE} -f avp_ipc      `hostname` postgres
./update_avp_db.sh
