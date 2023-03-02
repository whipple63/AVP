'''Handles communication with the AVP database'''

#Built in Modules
from collections import deque
from datetime import datetime
import logging
import socket 
import sys
import traceback

#Installed Modules
import psycopg2 # connect
from psycopg2.extensions import adapt, register_adapter, AsIs
import psycopg2.extras
import pytz.reference

#Custom Modules
import avp_util

class DB_LogHandler(logging.Handler):
    '''
    A handler class which sends log strings to the database
    '''
    def __init__(self, config):
        '''
        Initialize the handler
        @param config: config info from config file
        '''
        logging.Handler.__init__(self)
        self.hostname = socket.gethostname()
        try:
            DEBUG_TABLE = config.get('db',{}).get('DEBUG_TABLE','{0}_debug_log'.format(self.hostname))
            LOG_TABLE = config.get('db',{}).get('LOG_TABLE','{0}_log'.format(self.hostname))
        except KeyError as e:
            logger = logging.getLogger(self.__class__.__name__)
            logger.critical('Error in DB_LogHandler.emit() finding configuration key {0} in {1}'.format(e,config))
            sys.exit(1)
        self.debug_db = AvpDB(config, DEBUG_TABLE)
        self.log_db = AvpDB(config, LOG_TABLE)
    def flush(self):
        '''
        does nothing for this handler
        '''
        pass
    def emit(self, record):
        '''
        Emit a record.
        '''
        log_items = {}
        log_items['source'] = record.module + '.' + record.funcName
        log_items['time'] = datetime.now(pytz.reference.LocalTimezone())
        log_items['message'] = record.message
        log_items['comment'] = 'Line ' + str(record.lineno)
        log_items['save'] = True
        if record.levelno == 10: # select debug table
            self.ldb = self.debug_db
        else:
            log_items['level'] = (record.levelno / 10) - 1
            self.ldb = self.log_db
        self.ldb.buffered_insert(log_items)
    def close(self):
        #self.debug_db.close()
        #self.log_db.close()
        logging.Handler.close(self)

class AvpDB(object):
    '''
    Database object for log database
    '''
    def __init__(self, config, table,polling=False,**kwargs):
        '''
        If polling is set to True, connection will be setup for polling and connections will not be closed after commits.
        '''
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.table = table
        self.polling = polling
        self.hostname = socket.gethostname()
        try:
            enabled = config['db'].get('enabled',False)
            db_host = config['db'].get('host',self.hostname)
            self.PORT = config['db']['PORT']
            self.DB_NAME = config.get('db',{}).get('DB_NAME',self.hostname)
            #self.DB_NAME = config['db']['DB_NAME']
            self.DB_USER = config['db']['DB_USER']
            self.DB_PASS = config['db']['DB_PASS']
        except KeyError as e:
            self.logger.critical('Error in AvpDB.__init__() finding configuration key '+str(e))
            sys.exit(1)
        except Exception as e:
            self.logger.critical('Error in AvpDB.__init__():{0}'.format(e))
            sys.exit(1)
        self.db_host = avp_util.check_hostname(hostname=db_host,**kwargs) # See if this is localhost
        self.enabled = avp_util.t_or_f(enabled)
        self.connected = False
        self.ins_que = deque([])
        self.log_items = {}  # This will hold the fields and values to be inserted or updated.
        self.columns = self._get_column_names(**kwargs)
        #self.logger.debug("Table {0} has columns {1}".format(self.table,self.columns))
        if self.polling:
            self._connect(**kwargs)
    def _get_column_names(self,**kwargs):
        '''
        Conects to table and gets column name. Returns None if table has no records.
        '''
        columns = []
        try:
            self._connect(**kwargs) 
            self.cursor.execute("SELECT * FROM {0} WHERE 1=0;".format(self.table))
            for column_name in  self.cursor.description: # See python PEP 249
                columns.append(column_name[0])
        except Exception as e:
            self.logger.error("in _get_column_names connecting to table {0}:{1}".format(self.table,e))
            print(dir(self))
        finally:
            self.close()
        return columns
    def buffered_insert(self,log_items):
        self.ins_que.append(log_items)
        try:
            self._connect()
            while (len(self.ins_que) > 0):
                self.insert(self.ins_que[0])
                #self.commit()
                self.ins_que.popleft()
            #self.close()
        except Exception as e:        
            print("Couldn't complete buffered insert.  Will try later. - "+str(e))
            traceback.print_exc()
    def connect(self,**kwargs):
        print("No need to call AvpDB.connect() No action taken")
    def _connect(self,DC=False,RDC=False,**kwargs):


        '''
        '''
        debug_mode = kwargs.get('debug_mode',False) 
        self.cursor = self.conn = None
        if self.enabled:
            try:
                self.conn = psycopg2.connect(host=self.db_host,
                                port=self.PORT,
                                user=self.DB_USER,
                                password=self.DB_PASS,
                                database=self.DB_NAME)
            except Exception as e:
                print("Unable to connect to database:{0}".format(e))
            try:
                if DC:
                    if debug_mode: print("Getting DictCursor")
                    self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                elif RDC:
                    if debug_mode: print("Getting RealDictCursor")
                    self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                else:
                    self.cursor = self.conn.cursor()
            except Exception as e:
                print("Unable to get cursor for database:{0}".format(e))
            if self.cursor and self.conn:
                # Everything has worked so far.
                self.connected = True
                if debug_mode: print("Connected to",self.DB_NAME)
                if self.polling:
                    self.conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                    self.cursor.execute("LISTEN {0};".format(self.table))
            else:
                print("Problem with conn,cursor:",self.conn,self.cursor)
            return self.conn,self.cursor
    def close(self,**kwargs):
        debug_mode = kwargs.get('debug_mode',False)  
        if self.enabled:
            if self.connected:
                try:
                    self.conn.close()
                except Exception as e:
                    print("Unable to close database:{0}".format(e))
                self.connected = False
            elif debug_mode:
                print("Connection to {0} already closed".format(self.table))
    def commit(self,**kwargs):
        print(" No need to call commit, no action taken.")
    def _commit(self,**kwargs):
        if self.enabled:
            try:
                self.conn.commit()
            except Exception as e:
                print("Unable to commit to database:{0}".format(e))
    def insert(self,log_items,**kwargs):
        '''
        
        '''
        debug_mode = kwargs.get('debug_mode',False) 
        result = None
        if self.enabled:
            if 'loc_code' in self.columns:
                log_items['loc_code'] = log_items.pop('loc_code',self.hostname) #If no loc_code is specified, use self.hostname
            insert_command = self._gen_string('INSERT INTO',log_items,**kwargs)
            if debug_mode: print('about to execute db command: ' + insert_command)
            if not self.connected:
                self._connect(**kwargs)
            try:
                self.cursor.execute(insert_command,log_items)
                self._commit(**kwargs)
                result = True
            except psycopg2.IntegrityError as e:
                self.conn.rollback()
                # if we catch an identical timestamp error, bump it up a bit and try again
                # if the integrity error is something other than the timestamp, the exception will get raised again below
                if 'time' in log_items:
                    t=log_items['time']
                    log_items['time'] = datetime(t.year,t.month,t.day,t.hour,t.minute,t.second, t.microsecond + 100, t.tzinfo)
                    insert_command = self._gen_string('INSERT INTO',log_items,**kwargs)
            except psycopg2.DataError as e:
                print(("couldn't insert: {e}".format(e=e)))
            except Exception as e:
                print('Error writing to database: '+str(e))
                print('string: {0}\r\nvalues: {1}'.format(insert_command,log_items))
                traceback.print_exc()
                result = False
            finally:
                if not self.polling:
                    self.close(**kwargs)
        else:
            print("Database not enabled")
        return result
    def delete(self,where_condition=None,where_join='AND',where_oper='=',**kwargs):
        '''
        '''
        debug_mode = kwargs.get('debug_mode',False)
        if where_condition is None:
            where_condition = {}
        if self.table != 'baypt_debug_log':
            print('can onlt DELETE FROM *_debug_log')
            return False
        result = None
        if self.enabled:
            try:
                delete_command = self._gen_string('DELETE',
                                                   set_values='',
                                                   where_condition=where_condition,
                                                   where_join=where_join,
                                                   where_oper=where_oper,
                                                   returning=False,
                                                   **kwargs)
                print("Executing: {0},{1}".format(delete_command,where_condition))
                if not self.connected:
                    self._connect(**kwargs)
                try:
                    self.cursor.execute(delete_command,where_condition)
                    rows_affected = self.cursor.rowcount
                    self._commit(**kwargs)
                    self.logger.info('Deleted {0} records from {1}'.format(rows_affected,self.table))
                    result = True
                except psycopg2.IntegrityError as e:
                    self.conn.rollback()
                    # if we catch an identical timestamp error, bump it up a bit and try again
                    # if the integrity error is something other than the timestamp, the exception will get raised again below
                    if 'time' in log_items:
                        t=log_items['time']
                        log_items['time'] = datetime(t.year,t.month,t.day,t.hour,t.minute,t.second, t.microsecond + 100, t.tzinfo)
                        delete_command = self._gen_string('INSERT INTO',log_items,**kwargs)    
            except Exception as e:
                print('Error deleteing records from database: '+str(e))
                traceback.print_exc()
                result = False
            finally:
                if not self.polling:
                    self.close(**kwargs)
        return result
    def select(self,columns,where_condition=None,where_join='AND',where_oper='=',fetch_type='all',**kwargs):
        '''
        '''
        debug_mode = kwargs.get('debug_mode',False) 
        if where_condition is None:
            where_condition = {}
        result = []
        if self.enabled:
            try:
                if not self.connected:
                    if debug_mode: print("connecting to database")
                    self._connect(**kwargs)
                columns = tuple(columns)
                select_command = self._gen_string('SELECT',
                                                  columns,
                                                  where_condition=where_condition,
                                                  where_join=where_join,
                                                  where_oper=where_oper,
                                                  **kwargs)
                if debug_mode: print("Executing: {0},{1}".format(select_command,where_condition))
                self.cursor.execute(select_command,where_condition)
                if 'all' in fetch_type:
                    result =  self.cursor.fetchall()
                elif 'one' in fetch_type:
                    result =  self.cursor.fetchone()
                else:
                    print("Error, did not recognize fetch_type: {0}".format(fetch_type))
                    result = None
            except Exception as e:
                print("Error in AvpDB.select b: {0}".format(e))
            finally:
                if not self.polling:
                    self.close(**kwargs)
        else:
            print("Database not enabled")
        return result
    def update(self,set_values,where_condition=None,where_join='AND',where_oper='=',**kwargs):
        '''
        '''
        debug_mode = kwargs.get('debug_mode',False)
        update_command = None
        if where_condition is None:
            where_condition = {}
        if self.enabled:
            if debug_mode: print("Updating with {0} and {1}".format(set_values,where_condition))
            try:
                if not self.connected:
                    self._connect(**kwargs)
                try:
                    update_command = self._gen_string('UPDATE',
                                                      set_values,
                                                      where_condition=where_condition,
                                                      where_join=where_join,
                                                      where_oper=where_oper,
                                                      **kwargs)
                    if debug_mode: print("Using commands ({0},{1})".format(update_command,set_values))
                    self.cursor.execute(update_command,set_values) # returns None
                    result = {'result':'ok'}
                    self._commit(**kwargs)
                except psycopg2.IntegrityError as e:
                    result = {'error':{'message':e,'code':0}}
                    self.conn.rollback()
                    # if we catch an identical timestamp error, bump it up a bit and try again
                    # if the integrity error is something other than the timestamp, the exception will get raised again below
                    if 'time' in set_values:
                        t=set_values['time']
                        set_values['time'] = datetime(t.year,t.month,t.day,t.hour,t.minute,t.second, t.microsecond + 100, t.tzinfo)
                        update_command = self._gen_string('UPDATE',
                                                          set_values,
                                                          where_condition=where_condition,
                                                          **kwargs)
                        if debug_mode: print("Using commands ({0},{1})".format(update_command,set_values))
                        self.cursor.execute(update_command,set_values)
            except Exception as e:
                message =  'Error writing to database: '+str(e)
                print(message)
                print('string: {0}\r\nvalues: {1}'.format(update_command,set_values))
                traceback.print_exc()
                result = {'error':{'message':message,'code':0}}
            finally:
                if not self.polling:
                    self.close(**kwargs)
        else:
            result = {'error':{'message':'database not enabled.','code':0}}
        if debug_mode: print("result['avp_db.AvpDB.update'] = {0}".format(result))
        return result
    def _gen_string(self,exec_type,set_values,where_condition=None,where_join='AND',where_oper='=',returning=False,**kwargs):
        '''
        exec_type = <'UPDATE'>|                 -- Type of command to build
        set_values = {field_N:value_N,...} or (field_N,...) dict or tuple. Not list.
        where_condition = {field_N:value_N,...} -- Optional WHERE condition
        usage:
        self.cursor.execute(<return string from this function>,<set_values|where_condition for SELECT>)
        '''
        debug_mode = kwargs.get('debug_mode',False) 
        if where_condition is None:
            where_condition = {}
        valid_types = ('INSERT INTO','UPDATE','SELECT','DELETE')
        if exec_type in valid_types:
            set_vals = ''
            join = ' '
            exec_command = exec_type
            if exec_type == 'SELECT':
                for key in set_values:
                    set_vals += "{0}{1}".format(join,key)
                    join = ", "
                exec_command += "{0} FROM {1} ".format(set_vals, self.table)
            elif exec_type == 'UPDATE':
                exec_command += " {0} SET ".format(self.table)
                for key,value in list(set_values.items()):
                    set_vals += '''{0}{1} = %({1})s'''.format(join,key,value)
                    join = ", "
                exec_command += "{0} ".format(set_vals)
            elif exec_type == 'INSERT INTO':
                exec_command += " {0}".format(self.table)
                set_fields = ''
                for key,value in list(set_values.items()):
                    set_fields += "{0}{1}".format(join,key)
                    set_vals += '''{0}%({1})s'''.format(join,key)
                    join = ', '
                exec_command += ' ({0}) VALUES ({1})'.format(set_fields, set_vals)
            elif exec_type == 'DELETE':
                if len(where_condition) == 0:
                    # This will delete the entire table!
                    return ''
                else:
                    exec_command += ' FROM {0}'.format(self.table)
            else:
                print("Unknown query type: {0}".format(exec_type))
                return None
            if where_condition: 
                exec_command += ' WHERE '
                where_str = ''
                join = ' '
                for key in where_condition: # Build string with _w_ mangling
                    if key[:3] == "_w_": #If it has been previously mangled...
                        key = key[3:] #Un-mangle it
                    where_str += '''{0}{1} {2} %(_w_{1})s'''.format(join,key,where_oper)
                    join = " {0} ".format(where_join)
                exec_command += ' {0}'.format(where_str)
                # Need to mangle the where dictionary just in case there is a conflict with the set_values
                list_of_old_keys = []
                for key,value in list(where_condition.items()): # Make mangled copies of all the dictionary keys
                    if key[:3] == '_w_': #Don't double-mangle anything
                        pass
                    else:
                        new_key = "_w_{0}".format(key)
                        where_condition[new_key] = value
                        list_of_old_keys += [key]
                for old_key in list_of_old_keys: # delete un-mangled keys
                    where_condition.pop(old_key)
                try:
                    set_values.update(where_condition) # Now that we've mangled where_condition, we can join them without fear of a conflict
                except:
                    pass #This will fail for SELECT, but that is ok.
            if returning:
                exec_command += ' RETURNING {0}'.format(returning)
            exec_command += ";"
        else:
            print("Error: {0} not in {1}".format(exec_type,valid_types))
            exec_command = None
        return exec_command
    def poll(self,**kwargs):
        debug_mode = kwargs.get('debug_mode',False)
        result = ()
        if self.polling:
            try:
                self.conn.poll()
                while self.conn.notifies: 
                    result = self.conn.notifies.pop()
                    if debug_mode: print("Got NOTIFY:", result)
            except psycopg2.OperationalError as e:
                # If this happens we should close and re-open the table.
                self.logger.warning('Polling error {0} closing  and re-connecting polled database connection.'.format(e))
                self.close()
                self._connect()
        else:
            self.logger.warning("Table {0} was not initialized as polled table".format(self.table))
        return result

class TransectDB(AvpDB):
    '''
    Extends db Class with methods specific to a ferry transect
    '''
    def __init__(self, config):
        self.logger = logging.getLogger(self.__class__.__name__)
        try:
            self.table = config['db'].get('CAST_TABLE',"{0}_cast".format(socket.gethostname()))
        except KeyError as e:
            self.logger.critical('Error in TransectDB.__init__() finding configuration key '+str(e))
            sys.exit(1)
        AvpDB.__init__(self,config,self.table) # Run superclass _init__ 
        self.transect_items = {}  # This will hold the fields and values to be inserted or updated.
    def transect_number(self,**kwargs):
        debug_mode = kwargs.get('debug_mode',False) 
        result = self.select(('max(cast_no)',),fetch_type='one',**kwargs)[0]
        if debug_mode: print("transect_number result:{0}".format(result))
        return  {'result':result}
    def start(self,transect_number,**kwargs):
        '''
        Called at start of sonde lowering, Updates record (transect time)
        '''
        debug_mode = kwargs.get('debug_mode',False) 
        set_values = {'cast_time':datetime.now(pytz.reference.LocalTimezone())}
        where_condition = {'cast_no':transect_number}
        self.update(set_values,
                    where_condition=where_condition,
                    **kwargs) #returns transect_number
        #self.commit()
        return
    def finish(self):
        '''
        Called at end of sonde lowering
        final update of record.
        '''
        #self.commit()
        self.close()
