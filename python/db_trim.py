#!/usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        db_trim.py
# Purpose:     Deletes old records from <hostname>_debug_log table
#
# Author:      neve
#
# Created:     06/13/2012
#-------------------------------------------------------------------------------

from datetime import datetime, timedelta
import logging
import socket
import sys
#Installed Modules

import psycopg2 # connect
#from psycopg2.extensions import adapt, register_adapter, AsIs
#import psycopg2.extras
import pytz.reference

import avp_db
from  avp_util import get_config

def main(config):
    DEBUG_TABLE_DAYS = int(config.get('db',{}).get('DEBUG_TABLE_DAYS',90))
    logger = logging.getLogger('db_trim')
    hostname = socket.gethostname()
    DEBUG_TABLE = config.get('db',{}).get('DEBUG_TABLE','{0}_debug_log'.format(hostname))
    debug_log = avp_db.AvpDB(config,table=DEBUG_TABLE)
    trim_before = datetime.now(pytz.reference.LocalTimezone()) - timedelta(days=DEBUG_TABLE_DAYS)
    where_condition = {'time':trim_before}
    where_oper = '<'
    result = debug_log.delete(where_condition=where_condition,where_oper=where_oper,debug_mode=True)
    print(result)


if __name__ == '__main__':
    cloptions,config = get_config(option_set=None) # parse command Line options
    logger = logging.getLogger('')
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    dbh = avp_db.DB_LogHandler(config)
    dbh.setLevel(logging.DEBUG)
    logger.addHandler(dbh)
    main(config)
    

