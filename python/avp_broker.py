#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        avp_broker
# Purpose:     Contains classes for various instruments.
#              Every broker client extends _BrokerClient. The most important data structure
#              within each broker is the _Data_Item. The _Data_Item contains various 
#              information, including the value of a single broker parameter. A _Data_Item 
#              can be interrogated or subscribed to via the broker.
#              Examples:
#                 If a broker named sonde had a parameter depth_m, to print the value and 
#                  units we would do:
#                  print sonde.depth_m.value,sonde.depth_m.units
#                  If we are subscribed to depth_m, it would give us the most recent recieved 
#                  value, otherwise it would request the value of the broker server.
#                  To set a value (if settable) we would just do something like this:
#                  mm3.position = 0
#
# Author:      neve
#
# Created:     01/02/2012
#-------------------------------------------------------------------------------
#Built in Modules
from datetime import datetime,timedelta
import json
import logging
from random import random
from select import select as sselect
import socket
import sys
import threading
import time
#Installed Modules
import pytz.reference
#Custom Modules
import avp_util
import avp_db


if sys.version_info < (3,):
    def b(x):
        return x
else:
    import codecs
    def b(x):
        return codecs.latin_1_encode(x)[0]

'''
TODO: check for errors on _status, set, subscribe calls
might implement send / recv, error checking as separate function

Better define what is returned from all method calls.
'''


class SocketHandler(threading.Thread):
    '''
    Handles sending jSON strings and awaiting replys via the public send_rpc() method.
    
    Arguments:
        host        -- Host to connect to
        PORT        -- Port to connect to
        rx_r        -- Shared dict of replies
        rx_n        -- Shared list of notifications
        so_timeout  -- Default socket timeout.
        broker_name -- Used for naming thread
    Instance attributes:
        connected   -- Are we connected to broker server
        
    '''
    def __init__(self, host, PORT, rx_r, rx_n, so_timeout, broker_name,debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = logging.getLogger('{0}.{1}'.format(broker_name,self.__class__.__name__))
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        self.address = (host,PORT)
        self._rx_r = rx_r
        self._rx_n = rx_n
        self.so_timeout = so_timeout
        super(SocketHandler,self).__init__()
        self.name = "{0}.{1}".format(broker_name,self.__class__.__name__)
        self.running = False
        self.connected = False
        self.connect_tries = 0
    def send_rpc(self, method, json_id,timeout=None,params=None,**kwargs):
        ''' 
        Formats and sends JSON-RPC message to broker server.
        
        Arguments:
            method  -- Method of broker server called 
            json_id -- Integer used to uniquely identify JSON-RPC call and response.
            timeout -- Number of seconds to wait for reply. if nothing is specified, default is used.
            params  -- Optional parameters for method called
        Keyword Arguments:
            debug_mode  -- Enables additional debugging messages.
        Returns:
            A JSON-RPC formatted dictionary. See the JSON-RPC specification for
            full details. A typical non-error response would be:
                {"result":{<result>},"id":json_id}
            An error response would look like:
                {"error":{"code":<error code>,"message":<error message>},"id":json_id}
        '''
        debug_mode = kwargs.pop('debug_mode',None)
        if not debug_mode:
            debug_mode = self.debug_mode
        if not self.connected:
            error_msg = 'Not connected to broker.'
            self.logger.error(error_msg)
            return {'error':{'message':error_msg,'code':0}}
        self.msg = {'method':method, 'id':json_id}
        if timeout is None:
            timeout=self.so_timeout
        if params:
            self.msg['params'] = params
        if debug_mode: print(("JSON-RPC Request:{0}".format(json.dumps(self.msg))))
        self._send(json.dumps(self.msg))
        # We may want to do something else if send_result is 0
        reply_result = self._get_reply(json_id,timeout)
        return reply_result
    def _send(self, data):
        if not self.running:
            self.logger.debug("Socket not connected.")
            return 0
        try:
            self.socket.send(b(data))
            return 1
        except Exception as e:
            self.running = False
            self.logger.debug('{0}.send broker failed ({1}).'.format(self.name,e))
            return 0
    def _get_reply(self,json_id,timeout):
        endtime = time.time() + int(timeout)
        tries = 0
        while time.time() < endtime:
            if json_id in self._rx_r:
                return self._rx_r.pop(json_id)
            try:
                # This is a straightforward interface to the Unix select() system call. The first three arguments are
                # sequences of 'waitable objects': either integers representing file descriptors or objects with a
                # parameterless method named fileno() returning such an integer
                [read_list, write_list, exception_list] = sselect([self.sf],[],[], 0.1)
            except (AttributeError,) as e:
                # This can happen if a broker is killed while awaiting a response
                break
            tries += 1
            time.sleep(0.1)
        error_msg = 'Response from {a} timed out after {t} tries in {to}s ({n},{j}). Request was {m}. Response was:{r}'.format(
                        a=self.address,to=timeout,n=self.name,j=json_id,m=self.msg,t=tries,r=self._rx_r)
        self.logger.error(error_msg)
        return {'error':{'message':error_msg,'code':0}}
    def shutdown(self):
        if self.running is True:
            self.running = False
            time.sleep(1) # Give main thread time to stop
            self.logger.debug("Shutting down {0:2} threads left.".format(threading.active_count()))
            try:
                self.sf.close()
            except AttributeError as e:
                # If there were problems starting up, sf may not exist.
                pass
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except (socket.error, Exception) as e:
                pass # It may already be shut down.
            self.socket.close()
    def start(self):
        self.running = True
        super(SocketHandler,self).start() #threading.Thread.start(self)
        self.logger.debug("Started up {0:24} {1:2} active threads.".format(self.name,threading.active_count()))
    def run(self):
        while self.running:
            if self.connected:
                try:
                    [read_list, write_list, exception_list] = sselect([self.sf],[],[], 1)
                    if(len(read_list) > 0):
                        try:
                            jrx = self.sf.readline()[:-1]
                        except AttributeError:
                            pass # Rarely we get this from socket.py
                                 # data = self._sock.recv(self._rbufsize)
                                 # AttributeError: 'NoneType' object has no attribute 'recv'
                        rx = json.loads(jrx)
                        rxid = rx.get("id",None)
                        if rxid is not None:
                            self._rx_r[rxid] = rx # It's a reply
                            if self.debug_mode: print(("RPC Resp:{0}".format(json.dumps(rx,sort_keys=True))))
                        else:
                            self._rx_n.append(rx) # It's a notification
                            if self.debug_mode: print(("RPC Noti:{0}".format(json.dumps(rx,sort_keys=True))))
                except ValueError as e:
                    self.logger.info("In SocketHandler.run: {0}".format(e))
                    self.connected = False
                    self.sf.close()
                    self.socket.shutdown(socket.SHUT_RDWR)
                    self.socket.close()
            else:
                # Connect or re-connect
                self.start_connection()
    def start_connection(self):
        # This should be in a try, so if we get "socket.error: [Errno 111] Connection refused" or some other error it is handled.
        try:
            self.connect_tries += 1
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect(self.address)
            self.sf = self.socket.makefile('r') # returns a readable file object
            self.connected = True
            if self.connect_tries > 1:
                self.logger.debug("{0}.start_connection re-connected to {1}.".format(self.name,self.address))
            else:
                self.logger.debug("{0}.start_connection connected to {1}.".format(self.name,self.address))
            self.connect_tries = 0
        except Exception as e:
            print(("ERROR",e))
            if self.connect_tries == 1 or self.connect_tries % 60 == 0:
                self.logger.info("in start_connection(), connection to (host,port):{0}, failed ({1}).".format(self.address,e))
            time.sleep(1)
    def is_connected(self):
        return self.connected

class _SubscriptionHandler(threading.Thread):
    '''
    Manages subscribed parameters.
    
    This class monitors rx_n for subscription replies, and when they match with items in the
    subscriptions dictionary, the associated _data_item is updated.
    If there is a key match in callbacks, the associated callback function is spawned as a thread.
    Parameters:
        rx_n          -- Shared(?) list of notifications from _socket_handler
        subscriptions -- Shared(?) dictionary of _Data_Item objects which are subscribed
        callbacks     -- Shared(?) dictionary of {<callback_name>:<callback function>}
        broker_name   -- Used for naming thread    
    '''
    SLEEP_TIME = 0.1 # How long to sleep between notification checks
    def __init__(self, rx_n, subscriptions, callbacks, broker_name,debug_mode=False):
        self.debug_mode = debug_mode
        self.logger = logging.getLogger('{0}.{1}'.format(broker_name,self.__class__.__name__))
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        self._rx_n = rx_n
        self.subscriptions = subscriptions
        self.callbacks = callbacks
        self.broker_name = broker_name
        self.running = False
        self.subscription_error = False
        super(_SubscriptionHandler,self).__init__()
        self.name = "{0}.{1}".format(self.broker_name,self.__class__.__name__)
    def shutdown(self):
        self.running = False
        time.sleep(1)
        self.logger.debug("Shutting down {0:2} threads left..".format(threading.active_count()))
    def start(self):
        self.running = True
        super(_SubscriptionHandler,self).__init__() # This allows us to re-start the thread after a shutdown.
        self.name = "{0}.{1}".format(self.broker_name,self.__class__.__name__) # We loose our name when we call __init__
        super(_SubscriptionHandler,self).start()
        self.logger.debug("Started up {0:24} {1:2} active threads.".format(self.name,threading.active_count()))
    def run(self):
        del self._rx_n[:] # This clears out anything in the rx_n list
        while (self.running):
            if (len(self._rx_n) == 0):
                time.sleep(self.SLEEP_TIME)
            else:
                self.n = self._rx_n.pop(0) # This 0 is important to make this a FIFO not a LIFO
                try:
                    if (self.n.get('method') == 'subscription'): #This is a subscription message
                        params = self.n.get('params',{})
                        timedict = params.pop('message_time',{}) # message_time is special, take it out and handle it later if we are subscribed
                        message_time_long = timedict.get('value',datetime.strftime(datetime.now(),'%y%m%d%H%M%S000'))
                        tz = timedict.get('units',None) # Only in verbose mode.
                        for key_name in list(params.keys()): # process each data_item (key)
                            if key_name in self.subscriptions: #This gets rid of an error when we unsubscribe
                                if 'value' in params[key_name]:
                                    self.subscription_error = False
                                    # Some brokers (lisst,isco) return 'true'|'false' instead of True|False
                                    if self.subscriptions[key_name]._units.lower() == 'boolean':
                                        params[key_name]['value'] = avp_util.t_or_f(params[key_name]['value'],debug_mode=self.debug_mode) 
                                    self.subscriptions[key_name]._value = params[key_name]['value'] # Use _value, NOT value
                                    # We now might get sample_time_long associated with a value and not a response
                                    self.subscriptions[key_name]._sample_time_long = params[key_name].pop('sample_time',message_time_long)
                                    self.subscriptions[key_name]._sample_time = get_date_time(self.subscriptions[key_name]._sample_time_long)
                                    if tz is not None:
                                        self.subscriptions[key_name]._tz = tz # This should never change once set
                                    if key_name in self.callbacks:
                                        # check this key_name for a callback, and if so call it
                                        # arguments will be the sample_time and the subscription value
                                        cbt = threading.Thread(target=self.callbacks[key_name],
                                            args=(self.subscriptions[key_name]._sample_time,
                                            self.subscriptions[key_name]))
                                        cbt.setName("callback.{0}".format(key_name))
                                        cbt.start()
                                elif ('message' in params[key_name]):
                                    if ( self.subscription_error is False ):
                                        self.logger.error('{0}.{1}: {2} {3}'.format(
                                            broker_name,self.__class__.__name__,
                                            params.get(key_name,{}).get('message',None),
                                            params.get(key_name,{}).get(code,None)))
                                    self.subscription_error = True
                                else:
                                    # We occasionally get something with no 'value', so ignore it
                                    if ( self.subscription_error is False ):
                                        self.logger.debug("JSON string {pk} has no item 'value'({k})".format(
                                                            pk=params[key_name],k=key_name))
                                    self.subscription_error = True
                            else:
                                self.logger.debug("Parameter {k} subscribed but not in {bn}.subscriptions dictionary.".format(
                                                    k=key_name, bn=self.broker_name))
                        if 'message_time' in self.subscriptions: # This is for keeping track of the last subscription update's time
                            try:
                                self.subscriptions['message_time']._value = message_time_long
                                self.subscriptions['message_time']._sample_time = get_date_time(message_time_long)
                                if tz:
                                    self.subscriptions['message_time']._tz = tz # This should never change once set
                            except Exception as e:
                                self.logger.error("{0}, unable to parse message_time from {1}".format(e,self.subscriptions))
                except Exception as e:
                    print("_SubscriptionHandler exception: {0} on {1}".format(e,self.n))

class _BrokerClient(object):
    '''
    Implements all the generic broker methods. Extended for specific brokers

    Public Methods: connect_to_broker       - Connect to broker socket
                    disconnect              - Disconnect from broker
                    get_value               - 
                    list_data               - 
                    subscribe               - 
                    add_subscription        - 
                    unsubscribe             - 
                    unsubscribe_all         - 
                    add_callback            - 
                    remove_callback         - 
                    set                     - 
                    power                   - 
                    tokenRelease            - 
                    tokenOwner              - 
                    get_token               - 
                    shutdown_broker         - 
                    suspend_broker          - 
                    resume_broker           - 
                    broker_status           - 
                    connected               - Are we connected to the broker's socket?
    Instance Variables: host,               - Broker host
                        PORT,               - Broker port
                        SOCKET_TIMEOUT,     - Broker socket timeout
                        RESUME_TIMEOUT,     - Broker socket timeout when resuming (which typically takes longer than most actions)
                        subscriptions,      - Dictionary of subscribed values where each entry is a data_name:object pair
                        new_subscriptions,
                        callbacks,          - Dictionary of callbacks in subscription name - callback:function pairs
                        data_points,        - Dictionary of attribute names and objects
                        initialized         - Have we communicated with the broker and set up data structures
                        token_acquired      - Do we think we have the token
    '''
    MINIMUM_VALUE = 1e-300
    def __init__(self,config,broker_name,program_name=__name__,**kwargs):
        '''
        Initialize Generic Broker Class
        Args:
            config(ConfigObj):  Configuration dictionary-like object
            broker_name(str):   Name of this broker
        Kwargs:
            program_name(str):  name to use for token aquisition defaults to 'unknown._BrokerClient'
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
        Raises:
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if debug_mode: print("{0} broker in debug_mode".format(broker_name))
        result = {}
        self.config = config
        self.BROKER_NAME = broker_name
        self.program_name = program_name
        #self.load_config(reload_config=False,debug_mode=debug_mode)
        # perhaps self.config = self.config[self.BROKER_NAME] so each broker only sees its own part of the config.
        self.subscriptions = {}
        self.new_subscriptions = {} #new version, to be implemented {name:{'object':object,'subscribers':[list of subscribers]}}
        self.callbacks = {} 
        self.data_points = {} 
        self._rx_r = {} # rx replies
        self._rx_n = [] # rx notifications
        self._json_id = int(random() * 10000)
        self.connected = null # null is a function which accepts any arguments and returns False
        self.initialized = False 
        self.token_acquired = False
        # These come from the generic broker_status() method. They are updated whenever broker_status() is called.
        self.power_on = False
        self.last_db_time = None
        self.db_connected = False
        self.instr_connected = False
        self.suspended = False
        self.last_data_time = None
        self.start_time = None
        if hasattr(self,'logger') is False:
            self.logger = logging.getLogger(self.__class__.__name__)
            self.logger.error("Instantiated logger when it should have been done by child")
        if debug_mode is False:
            self.logger.setLevel(logging.INFO)
        result['connect_to_broker'] = self.connect_to_broker(debug_mode=debug_mode)
        iter = 0
        # May take a short while to connect
        while self.connected() is False:
            time.sleep(.1)
            if iter > 20:
                self.logger.error("Could not connect to broker and may not recover.")
                break
            iter += 1
        else:
            self.logger.debug("Connected to broker")
            # Very Important, this creates all the parameter child objects which can only be done if we are connected.
            result['_structure_data'] = self._structure_data(debug_mode=debug_mode,**kwargs)
            # Now aliases if there are any
            if result['_structure_data'] > 0:
                #This allows us to alias parameters with their functions.
                self.logger.debug("Added {0} parameters to data structure.".format(result['_structure_data']))
                self.param_aliases = self.config.get(self.BROKER_NAME,{}).get('aliases',{})
                for key,value in list(self.param_aliases.items()):
                    this_data_item = getattr(self,value)
                    setattr(self,key,this_data_item)
                    self.data_points[key] = getattr(self,key)
                    if debug_mode: print("Aliasing {0} to {1}".format(key,value))
                if len(self.param_aliases) > 0:
                    self.logger.debug("Added {0} parameter aliases.".format(len(self.param_aliases)))
            elif result['_structure_data'] == 0:
                self.logger.debug("Added no parameters to data structure.")
            else:
                pass # Error condition
        return result
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        host = self.config.get(self.BROKER_NAME,{}).get('host',socket.gethostname())
        self.PORT = int(self.config.get(self.BROKER_NAME,{}).get('PORT',0))
        # First try to get broker specific value, then global

        self.SOCKET_TIMEOUT = int(self.config.get(self.BROKER_NAME, {}).get('SOCKET_TIMEOUT',self.config.get('broker',{}).get('SOCKET_TIMEOUT',5)))
        self.RESUME_TIMEOUT = int(self.config.get('broker',{}).get('RESUME_TIMEOUT',self.config.get('RESUME_TIMEOUT',50)))
        self.STALE_TIME = int(self.config.get('broker',{}).get('STALE_TIME',self.config.get('STALE_TIME',10)))
        #self.RESUME_TIMEOUT = int(self.config.get('broker',{}).get('RESUME_TIMEOUT',50))
        #self.STALE_TIME = int(self.config.get('broker',{}).get('STALE_TIME',10))
        self.host = avp_util.check_hostname(host,broker_name=self.BROKER_NAME,debug_mode=debug_mode)
        if reload_config is True:
            self.logger.debug('Re-loaded {0} for {1} broker'.format(self.config.filename,self.BROKER_NAME))
        # Set up broker constants
        try:
            self.constants = self.config.get(self.BROKER_NAME,{}).get('constants',{})
            if debug_mode is True:
                print(("{b} constants are {c}".format(b=self.BROKER_NAME,c=self.constants)))
            for constant,value in list(self.constants.items()):
                try:
                    if '.' in value: # Crude way of checking if it is a float
                        setattr(self,constant,float(value))
                    else:
                        setattr(self,constant,int(value))
                except ValueError:
                    # It is probably a string
                    setattr(self,constant,value)
        except KeyError as e:
            if debug_mode is True:
                print(("{b} doesn't have [[{e}]]".format(b=self.BROKER_NAME,e=e)))
            pass
        return
    def connect_to_broker(self,**kwargs):
        '''
        Creates SocketHandler and _SubscriptionHandler objects.
        Starts SocketHandler thread
        Calls initialize_data which creates objects based on list_data reply from broker.
        Args: None
        Kwargs: None
        Returns:
            bool.   If all actions were successful.
        Raises:
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self.connected():
            try:
                self.socket_handler = SocketHandler(self.host, self.PORT, self._rx_r, self._rx_n,
                    self.SOCKET_TIMEOUT,broker_name=self.BROKER_NAME,debug_mode=debug_mode)
                self.connected = self.socket_handler.is_connected
            except Exception as e:
                self.logger.error("Could not create SocketHandler: {0}".format(e))
            try:
                self.sub_handler = _SubscriptionHandler(self._rx_n, self.subscriptions, 
                                                        self.callbacks,broker_name=self.BROKER_NAME,
                                                        debug_mode=debug_mode)
            except Exception as e:
                self.logger.error("Could not create _SubscriptionHandler: {0}".format(e))
            try:
                self.socket_handler.start()
            except Exception as e:
                self.logger.error("Could not start SocketHandler: {0}".format(e))
            '''
            try:
                self.sub_handler.start()
            except Exception,e:
                self.logger.error("Could not start _SubscriptionHandler: {0}".format(e))
            '''
        
        return self.connected()
    def disconnect(self,**kwargs):
        '''
        Releases token and shuts down SocketHandler and _SubscriptionHandler
        Args: None
        Kwargs:
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
        Raises:
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if self.token_acquired is True:
            self.tokenRelease(debug_mode=debug_mode,**kwargs)
        # Should we unsubscribe to everything?
        self.sub_handler.shutdown()
        self.socket_handler.shutdown()
        self.connected = null
    def _is_initialized(self,method_name='unknown',**kwargs):
        '''
        Releases token and shuts down SocketHandler and _SubscriptionHandler
        Args: None
        Kwargs:
            debug_mode(bool):   Print extra debugging messages defaults to False
            method_name(str):   Method calling this function. defaults to 'unknown'
        Returns:
            bool. Are we initialized
        Raises:
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if self.initialized:
            return True
        else:
            self.logger.warning(
                "Can not call {bn}.{mn}() when broker structure has not been initialized".format(
                bn=self.BROKER_NAME,mn=method_name))
            return False
    def re_structure_data(self,connect_tries=8,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        result = self._structure_data(restructure=True,connect_tries=connect_tries,debug_mode=debug_mode)
        return result
    def _structure_data(self,restructure=False,connect_tries=8,connect_pause=2,**kwargs):
        ''' Queries the broker as to what parameters are available. For each 
        value a _DataItem object is added to the parent object with that 
        data_point's name.
        Args:
        Keyword Arguments:
            restructure -- If True, assumes that the object needs to be re-initialized.
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
            int. 
                <0  error occured
                0   No parameters added
                >0  Number of parameters added
        Raises:
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        # See if we are connected to the instrument. If not, we can't go much further.
        self.broker_status(timeout=None,debug_mode=debug_mode)
        if self.connected() is False: # This is our socket connection to the broker.
            self.logger.warning("Can not initialize broker while socket not connected.")
            self.initialized = False
            return -1
        # During startup the java broker may not have connected to the instrument yet.  This
        # happens when the supervisor connects to the sonde.  (When this happens, the local
        # interface fails.)  We need to be willing to wait a while and check again.
        while self.instr_connected == False and connect_tries > 0:
            connect_tries -= 1
            self.broker_status(timeout=None,debug_mode=debug_mode)
            time.sleep(connect_pause)
        if not self.instr_connected:    # This is the broker to instrument connection
            self.logger.info("Can not initialize {0} broker structure while instrument not connected.".format(self.BROKER_NAME))
            self.initialized = False
            return -1
        data_list = self.list_data(params=['units','type'],timeout=None,debug_mode=debug_mode)
        if 'error' in data_list:
            self.logger.warning("list_data() failed, {dlem} - code:{dlec}".format(
                dlem=data_list['error'].get('message'),
                dlec=data_list['error'].get('code'))) # Not an error, just an odd occurance.)
            self.initialized = False
            return -1
        if debug_mode:
            print(("Structuring data: parameters for {0} are:\n\t{1}".format(self.BROKER_NAME,data_list)))
        added_parameters = 0
        try:
            for data_name in data_list:
                data_type = data_units = ''
                try:
                    data_dict = data_list.get(data_name)
                    data_type = data_dict.get('type') #Can be ('RW', 'RO', 'WO', or 'NI' (Not Implemented))
                    data_units = data_dict.get('units')
                except Exception as e:
                    self.logger.error("In _structure_data. Extracting {dn} from {dl} data_list {e}".format(
                                       e=e,dl=data_list,dn=data_name))
                if data_type in ('RO','RW','WO','NI'):
                    thisDI = getattr(self,data_name,None) # Ignore attributes initialized to None
                    if thisDI is not None:
                        self.logger.debug("{0} already has data object {1}".format(self.BROKER_NAME,data_name))
                    else:
                        setattr(self,data_name,_DataItem(self.BROKER_NAME,data_name,data_type,
                                data_units,self.logger,self.set,self._status,self.STALE_TIME))
                        self.data_points[data_name] = getattr(self,data_name)
                        added_parameters += 1
                else:
                    # Not an error, just an odd occurance.
                    self.logger.info("Not adding {0} parameter {1} of unknown type {2}".format(self.BROKER_NAME,data_name,data_type)) 
            self.initialized = True
        except Exception as e:
            self.logger.error("Error in _structure_data:{0}".format(e))
        return added_parameters
    def _result_checker(self,raw_result,**kwargs): 
        ''' Strips out un-needed information from a given dictionary.
        Args:
            raw_result(dict.)   Response from JSON-RPC call
        Kwargs:
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
            dict. 
        Raises:
        
        raw_result can come in the following formats:
           {'result':{<results>}}
           {'error{'message':<message string>,'code':<error code>}}
        We want to return one of the following:
            {<results>} e.g {<parameter1>:<value1>,<parameter2>:<value2>}
            {'result':'ok'}
            {'result':'message'}
            {'error':{'message':<message>,'code':<code>}}
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if (debug_mode): print("power in debug_mode")
        result = {'result':'unknown'}
        bad_results = ('java.lang.NullPointerException',
            'java.lang.ClassCastException: java.sql.Timestamp cannot be cast to java.lang.String',
            'java.lang.NullPointerException')
        # make sure it's a dictionary!
        if not raw_result:
            if debug_mode: print("raw_result=None")
            raw_result = {'error':{'message':'empty string','code':0}}
        if raw_result.__class__ != {}.__class__:
            if debug_mode: print("{0} not a dictionary, it is a {1}".format(raw_result,raw_result.__class__))
            self.logger.debug("Error in _result_checker, result {0} is not a dictionary".format(raw_result))
            raw_result = {'error':{'message':'Returned object {0} not a dictionary'.format(raw_result),'code':0}}
        # remove some things we don't need
        raw_result.pop('id',None)
        raw_result.pop('jsonrpc',None)
        # Now process what we have
        raw_result_error = raw_result.get('error',None)
        if raw_result_error:
            if debug_mode: print("error result: {0}".format(raw_result_error))
            result = raw_result
        elif raw_result.get('result') in bad_results:
            if debug_mode: print("Result was some sort of JAVA error")
            result = {'error':{'message':raw_result.get('result'),'code':0}}
        elif raw_result.get('result') == 'ok':
            if debug_mode: print("ok result")
            result = {'result':'ok'}
        else:
            #At this point we may have:
            #    {'result':<message>}    --> no change
            #    {'result':{<results}}   --> {results}
            try:
                temp_result = raw_result.get('result')
                if temp_result.__class__ == {}.__class__:
                    if debug_mode: print("result is a dictionary")
                    result = temp_result
                else:
                    if debug_mode:
                        print(("result '{tr}' is NOT a dictionary, it is a {trc}".format(
                                tr=temp_result,trc=temp_result.__class__)))
                    result = raw_result
            except Exception as e:
                result = {'error':{'message':'unknown error on:{0}'.format(raw_result),'code':0}}
            if debug_mode: print("final result={0}".format(result))
        return result
    def _status(self, data_items,verbose=False,timeout=None,**kwargs):
        '''
        Requests values from Broker. If successful, updates _DataItem object's attributes otherwise returns error
        Returns the JSON-RPC dictionary of values or an error result
        get_value() should be used by external methods.
        Args:
            data_items()   
        Kwargs:
            verbose(bool):      Do we make verbose request
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
            dict.
            {'error':...} -- Error occured
            {result} -- Results of status request
            
        Once called, the values will be available as <broker>.<parameter>.value
        so the returned dictionary should not be needed. 
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        sample_time = message_time_long = message_time = sample_tz = None
        if verbose: style = 'verbose'
        else: style = 'terse'
        try: # We never ask for message_time, and we always get it anyways.
            data_items.remove('message_time')
        except:
            pass
        status_params = {'data':data_items,'style':style}
        status_dict = {}
        status_result = {}
        self._json_id += 1
        if debug_mode:
            print(("send_rpc 'status' {0} {1}".format(status_params,str(datetime.now(pytz.reference.LocalTimezone())))))
        status_dict = self.socket_handler.send_rpc(method='status',
                                                   json_id=self._json_id,
                                                   timeout=timeout,
                                                   params=status_params,
                                                   debug_mode=debug_mode)
        if debug_mode:
            print(("     send_rpc result: {sd} @ {now}".format(
                    sd=status_dict,now=str(datetime.now(pytz.reference.LocalTimezone())))))
        if not status_dict.__class__ == {}.__class__: #if it looks like the correct sort of thing, update the _DataItems
            self.logger.error("Error in {bn}._status, 'status' request of {sp} returned {sd}".format(
                                bn=self.BROKER_NAME,sp=status_params,sd=status_dict))
            status_dict = {'error':{'message':'type error in _BrokerObject._status','code':0}}
        if 'error' in status_dict:
            return status_dict
        try:
            status_result = status_dict.get('result')
        except Exception as e:
            self.logger.error("Error in _status get('result') {e}\r\n status_dict={sd}\r\n status_params={sp}".format(
                                e=e,sd=status_dict,sp=status_params) )
        try:
            if isinstance(status_result,dict): # message had a dictionary result
                timedict = status_result.get('message_time',None)
                if timedict != None:
                    message_time_long = timedict.get('value',None)
                    message_time = get_date_time(message_time_long)
                    sample_tz = timedict.get('units',None) # Only in verbose mode.
                    data_items.append('message_time') # Put it back so we can process it.
                for requested_item in data_items:
                    this_object = getattr(self,requested_item)
                    this_param  = status_result.get(requested_item)
                    this_units = this_param.get('units',None)
                    this_value = this_param.get('value',None)
                    this_sample_time_long = this_param.get('sample_time',None)
                    if this_value != None: # Do some error checking and post-processing
                        # Brokers will return double precision float minimum value when they don't have a real value
                        if this_value <= self.MINIMUM_VALUE and this_value > 0: 
                            this_value = None # So set it to None
                        if this_object._units == 'boolean': # We also need to make sure booleans are formatted correctly
                            this_value = avp_util.t_or_f(this_value,debug_mode=debug_mode,**kwargs)
                        setattr(this_object,"_value",this_value)
                        if this_units != None:
                            setattr(this_object,"_units",this_units)
                        if this_sample_time_long != None:
                            setattr(this_object,"_sample_time_long",this_sample_time_long)
                            setattr(this_object,"_sample_time",get_date_time(this_sample_time_long))
                        else: # Use the message's time rather if there is no sample_time for this parameter.
                            setattr(this_object,"_sample_time_long",message_time_long)
                            setattr(this_object,"_sample_time",message_time)
                        if sample_tz != None:
                            setattr(this_object,"_tz",sample_tz)
            else:
                # We didn't get a dictionary, sometimes we get a {'result':'java.lang.NullPointerException'}
                return {'error':{'message':status_result,'code':0}}
        except Exception as e:
            self.logger.error("Error in _status:{e}\r\n received status_dict={sd} for \r\n status_params={sp}".format(
                                e=e,sd=status_dict,sp=status_params))
        return status_result # Since this is an internal method, don't use status_checker.
    def get_value(self,data_item_names,verbose=False,timeout=None,**kwargs):
        '''
        Takes a list of parameter names and returns a dictionary of parameter:value pairs or an error.
        Usually used for values which are not subscribed.
        example:
        MM3broker.get_value(['position', 'temperature']) # Returns a list of two values
        print "position={0}, temperature={1}{2}".format(MM3broker.position.value,MM3broker.temperature.value,MM3broker.temperature.units)
        
        Args:
            data_item_names(list or tuple)
        Kwargs:
            verbose(bool):      Do we make verbose request
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
            dict.
            {'error':...} -- Error occured
            {result} -- Results of status request
            
        Once called, the values will be available in <broker>.<parameter>.value
        so the returned dictionary should not be needed. If subscribed 'on change'
        the most recent values will already be in <broker>.<parameter>.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        return_values = {}
        if debug_mode: print("Looking up values for {0}".format(data_item_names))
        # Check if data_item_names is a list
        if not isinstance(data_item_names,(list,tuple)):
            error_str = "Error in get_value. Method takes a list or tuple as an argument, not {din} of {tdin}".format(
                            din=data_item_names,tdin=type(data_item_names))
            self.logger.error(error_str)
            return {'error':{'message':error_str,'code':0}}
        data_item_names = list(data_item_names) # Need to change to list so we can change values in place.
        # Check names_to_get for existance and aliases
        for i in range(0,len(data_item_names)):
            if hasattr(self,data_item_names[i]):
                this_data_item = getattr(self,data_item_names[i])
                if 'R' in this_data_item.data_type: # This is why data_item_names must be a list not a tuple.
                    data_item_names[i] = this_data_item.data_name # Ask for it by its real data_name. This takes care of aliases
                else:
                    self.logger.warning("Error in _BrokerClient.get_value(): {0}.{1} is not readable".format(self.BROKER_NAME,data_item_names[i]))
            else:
                error_str =  "No parameter {1} from {2} wants {3}".format(self.BROKER_NAME,data_item_names[i], data_item_names,dir(self))
                self.logger.error(error_str)
                return {'error':{'message':error_str,'code':0}}
                # Rather than just return, we may want to just exclude the bad parameters.
        # Now communicate with broker...
        status_return = self._status(data_item_names,
                                     verbose=verbose,
                                     timeout=timeout, # Use default
                                     debug_mode=debug_mode)
        if 'error' in status_return:
            return status_return
        elif status_return.__class__ != {}.__class__:
            error_str =  "_status did not return dict, instead returned {0}".format(status_return)
            self.logger.error(error_str)
            return_values['error'] =  {'message':error_str,'code':0}
        else:
            for item_name in data_item_names:
                try:
                    item_obj = status_return.get(item_name)
                    item_value = item_obj.get('value')
                    return_values[item_name] = item_value
                except Exception as e:
                    self.logger.error(
                        "Exception in {0}.get_value: {1}. data_item_names = {2}. status_return = {3}, item_obj = ".format(
                        item_name,e,data_item_names,status_return))
        return return_values
    def value(self,param,request='value',**kwargs):
        ''' 
        THIS MAY BE DEPRICATED SINCE WE CAN JUST AS FOR <broker>.<parameter>.<value> e.g:
        depth_in_meters = sonde.depth_m.value
        Returns the requested _DataItem attribute in memory of the given param if it exists
            Does not check to see how current the value is. Does not request new value from broker.
        Args:
            param(str)          Parameter we want
        Kwargs:
            request(str):       Attribute of parameter we want returned(default = 'value')
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
            None -- Error occured
            value of requested <parameter>.<attribute>
            
        In almost every case, it is easier to just use <broker>.<parameter>.<attribute>
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not hasattr(self,param):
            self.logger.warning("Broker {0} has no parameter {1}".format(self.BROKER_NAME,param))
        else:
            this_attr = getattr(self,param)
            if request in dir(this_attr):
                return getattr(this_attr,request)
            else:
                self.logger.warning("Parameter {0}.{1} has no attribute {2}".format(self.BROKER_NAME,param,request))
        return None
    def list_data(self,params=None,timeout=None,**kwargs):
        '''
        Return list of available data from broker
        Args: None
        Kwargs:
            params(list):       Parameters we want passed to broker. Usually none.+
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
            dict.
            Result of list_data call to broker.
        '''
        if params is None:
            params = []
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        list_data_result = self.socket_handler.send_rpc('list_data',
                                                        self._json_id,
                                                        timeout=timeout,
                                                        params=params,
                                                        debug_mode=debug_mode)
        return self._result_checker(list_data_result)
    def _subscribe(self,params_list,on_change=True,min_interval=None,max_interval=None,verbose=False,timeout=None,ignore_missing=False,**kwargs):
        '''
        Takes a list or tuple of parameters to subscribe to.
        Checks to make sure they are valid if ignore_missing is False.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='_subscribe'): return {}
        # Check if params_list is a list
        if not isinstance(params_list,(list,tuple)):
            self.logger.error("Error, _BrokerClient._subscribe(params_list) method takes a list or tuple as an argument, not {0}".format(type(data_item_names)) )
            return 0
        if len(params_list) == 0:
            self.logger.debug("Subscription list is empty")
            return 0
        params_list.append('message_time')
        checked_data_item_names = []
        for parameter in params_list:
            if hasattr(self,parameter):
                this_data_item = getattr(self,parameter)    # This is to take care of aliases
                data_name = this_data_item.data_name        # data_name is what the broker recognizes
                if (parameter or data_name) not in self.subscriptions:
                    if self.sub_handler.running is False:
                        try:
                            self.sub_handler.start()
                        except Exception as e:
                            self.logger.error("Could not start _SubscriptionHandler: {0}".format(e))
                    checked_data_item_names.append(data_name)
                    self.subscriptions[parameter] = this_data_item # Might be an alias, or just doing the same thing twice
                    self.subscriptions[data_name] = this_data_item
                    setattr(this_data_item,'_subscribed',True)
                    if debug_mode: print("Subscribing to {0}".format(data_name))
                else:
                    if debug_mode: self.logger.debug( "Already subscribed to {0}.{1}".format(self.BROKER_NAME,parameter) )
            else:
                if ignore_missing is False: self.logger.error( "Broker object {0} has no parameter '{1}'".format(self.BROKER_NAME,parameter) )
        try:
            checked_data_item_names.remove('message_time')
        except:
            pass
        if len(checked_data_item_names) == 0:
            self.logger.debug("No new subscriptions to add from {0}".format(params_list))
            return {}
        if verbose: style = 'verbose'
        else: style='terse'
        params = {'data':checked_data_item_names,'style':style,'updates':'on_new'}# Puts parameters in a dictionary
        if on_change:
            params['updates'] = 'on_change'
        if min_interval > 0:
            params['min_update_ms'] = min_interval
        if max_interval > 0:
            params['max_update_ms'] = max_interval
        self._json_id += 1
        subscribe_result = self.socket_handler.send_rpc('subscribe',
                                                        self._json_id,
                                                        timeout=timeout,
                                                        params=params,
                                                        debug_mode=debug_mode)
        # If there is a problem here, we could end up in an odd state
        return self._result_checker(subscribe_result)
    def subscribe(self,params_list,**kwargs):
        '''
        This method is depricated. Please use add_subscriptions() instead.
        '''
        self.logger.warning("{0}.subscribe() is depricated, use {0}.add_subscriptions()".format(self.BROKER_NAME))
        return self._subscribe(params_list,**kwargs)
    def add_subscriptions(self,params_list,subscriber='unknown',on_change=True,min_interval=None,max_interval=None,verbose=False,timeout=None,ignore_missing=False,**kwargs):
        '''
        This will abstract the subscription process and may add more functionality later.
        May want to keep a list of who has subscribed, so if two subscribe and one unsubscribes, the subscription will remain.
        '''
        params_list = list(params_list) # Convert tuples to list...
        debug_mode = kwargs.pop('debug_mode',False)
        return self._subscribe(params_list,on_change=on_change,min_interval=min_interval,
                                max_interval=max_interval,verbose=verbose,timeout=timeout,
                                ignore_missing=ignore_missing,debug_mode=debug_mode)
    def unsubscribe(self,params_list,timeout=None,**kwargs):
        '''
        Unsubscribes to one or more params_list values. this is done indirectly by changing their status in the subscriptions dictionary
        Expects a list of one or more params_list points
        ''' 
        debug_mode = kwargs.pop('debug_mode',False)
        # Check if params_list is a list
        if not isinstance(params_list,(list,tuple)):
            self.logger.error( "Error, -BrokerClient.unsubscribe([parameters]) method takes a list or tuple as an argument, not {0}".format(type(params_list)) )
            return 0
        result = {}
        checked_params = []
        for parameter in params_list:
            if hasattr(self,parameter):
                this_data_item = getattr(self,parameter)    # This is to take care of aliases
                data_name = this_data_item.data_name        # data_name is what the broker recognizes
                if data_name not in self.subscriptions: # If data_name isn't in there, neither will parameter
                    self.logger.debug( "Not subscribed to {0}.{1}".format(self.BROKER_NAME,parameter))
                elif data_name != parameter: # Alias, no need to bother broker.
                    self.subscriptions.pop(parameter,None)
                else:
                    checked_params.append(data_name)
        try: # If we have a request to unsubscribe from sample_time, handle it locally
            checked_params.remove('message_time')
            self.subscriptions.pop(parameter,None)
            self.message_time._subscribed = False
        except:
            pass
        if len(checked_params) >= 1: # We may not have anything to send to broker.
            self._json_id += 1   
            result['send_rpc'] = self.socket_handler.send_rpc('unsubscribe',
                                                              self._json_id,
                                                              timeout=timeout,
                                                              params={'data':checked_params},
                                                              debug_mode=debug_mode)
            result['unsubscribe'] = self._result_checker(result['send_rpc'])
            if debug_mode: print(("Unsubscribe from {0} result: {1}".format(checked_params,result['send_rpc'])))
            for parameter in checked_params: # Now remove them from local subscription dictionary.
                this_data_item = getattr(self,parameter)
                self.subscriptions.pop(parameter,None)
                this_data_item._subscribed = False
            if 'error' in result['unsubscribe']:
                try:
                    error_code = result['unsubscribe']['error']['code']
                except Exception as e:
                    error_code = 0
                error_message = "Unsubscribe error: {0}".format(result['unsubscribe'])
                if error_code == -31917: # Can't unsubscribe when suspended
                    self.logger.debug(error_message)
                else:
                    self.logger.error(error_message)
        if len(self.subscriptions) == 0:
            self.sub_handler.shutdown()
        elif list(self.subscriptions.keys()) == ['message_time']:
            result['unsubscribe'] = self.unsubscribe(list(self.subscriptions.keys())) # A little recursive
        elif debug_mode:
            print("Remaining subscriptions {0}".format(list(self.subscriptions.keys())))
        return result
    def unsubscribe_all(self,**kwargs):
        ''' Unsubscribe to all keys in subscription dictionary and remove all callbacks
        '''
        if len(list(self.subscriptions.keys())) > 0:
            self.logger.debug( "{0} UNSUBSCRIBING {1}".format(self.BROKER_NAME,list(self.subscriptions.keys())) )
            result =  self.unsubscribe(list(self.subscriptions.keys()),**kwargs) # This may include aliases, but no matter.
        self.callbacks.clear() # Clear callbacks dictionary 
        self.subscriptions.clear() # Clear subscriptions dictionary 
        return 0
    def add_callback(self,cb_dict):
        '''
        Callbacks are added as name:callbackroutine pairs.
        There is no requirement that the subscription exists.  The subscription handler will
        check for a name match to incoming data and make the call in its own thread if it gets one.
        Arguments to the callback routine will be the timestamp and the subscription value.
        Call back routine must run faster than the subscription time.
        Aliases not supported
        '''
        # Check if cb_dict is a dictionary
        if not isinstance(cb_dict,dict):
            self.logger.debug("Error, _BrokerClient.add_callback({item:callback}) takes a dictionary as an argument, not {0} ".format(type(cb_dict)))
            return 0
        # Probably need some more checking to see if the
        self.callbacks.update(cb_dict)
        return 1
    def remove_callback(self,callback_list):
        '''
        Removes keys from callback dictionary
        '''
        if not isinstance(callback_list,(list,tuple)):
            self.logger.debug("Error, _BrokerClient.remove_callback([callback_list]) method takes a list or tuple as an argument, not {0}".format(type(callback_list)))
            return 0
        for key in callback_list:
            if key in self.callbacks:
                self.callbacks.pop(key)
            else:
                self.logger.debug("%s is not in callback dictionary." % key)
        return 1
    def set(self, params, write_store=False,timeout=None,**kwargs):
        '''
        Expects a dictionary of command value pairs where the command is to be set to the given value.
        self.valid_commands set by child
        Should check data_type to make sure it is writable
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        command = 'write_store' if write_store else 'set'
        result = {}
        # Check if params is a dictionary
        checked_params = {}
        if not isinstance(params,dict):
            message = "Error,{1}() takes a dictionary of item:function pairs as an argument, not {0} ".format(type(params),command) 
            self.logger.error(message)
            result = {'error':{'message':message,'code':0}}
            return result
        for (data_item_name,desired_value) in list(params.items()):
            if hasattr(self,data_item_name): # See if we have this as a DataItem oject
                this_data_item = getattr(self,data_item_name)
                if 'W' in this_data_item.data_type:
                    setattr(this_data_item,'set_to',params[data_item_name])
                    setattr(this_data_item,'set_at',datetime.now(pytz.reference.LocalTimezone()))
                    checked_params[this_data_item.data_name] = desired_value # We don't use data_item_name in case it has been aliased
                else:
                    self.logger.warning("Error in _BrokerClient.{2}(): {0}.{1} is not writable".format(self.BROKER_NAME,data_item_name,command))
            else:
                self.logger.warning("Error in broker.{2}: {0} has no parameter {1}".format(self.BROKER_NAME,data_item_name,command) )
        if len(checked_params) > 0:
            if debug_mode:
                print(("     {now} {bn}.{c}.send_rpc() starting".format(
                    now=str(datetime.now(pytz.reference.LocalTimezone())),
                    bn=self.BROKER_NAME, c=command)))
            if write_store: checked_params['write_store'] = True
            try:
                self._json_id += 1
                set_result = self.socket_handler.send_rpc('set',
                                                          self._json_id,
                                                          timeout=timeout,
                                                          params=checked_params,
                                                          debug_mode=debug_mode)
                if debug_mode: 
                    print(("     {now} send_rpc {c} {cp} Result:{sr}".format(sr=set_result,
                            now=str(datetime.now(pytz.reference.LocalTimezone())),
                            cp=checked_params,c=command)))
                result =  self._result_checker(set_result)
            except Exception as e:
                message = "Error {e} in _BrokerObject.socket_handler send_rpc({c},{ji},{cp})) failed".format(
                            ji=self._json_id,cp=checked_params,e=e,c=command)
                result = {'error':{'message':message,'code':0}}
        else:
            if debug_mode: print(("No valid parameters in {0}".format(list(params.items()))))
        return result
    def power(self,command='check',timeout=None,**kwargs):
        '''
        Used to turn Broker related hardware on and off
        '''
        valid_commands = ('on','off','check')
        if command in valid_commands:
            param = {'status':command}
            self._json_id += 1
            result =  self.socket_handler.send_rpc('power',
                                                   self._json_id,
                                                   timeout=timeout,
                                                   params=param,
                                                   **kwargs)
        else:
            message = "Error in _BrokerClient.power: valid arguments to power() are: {vc}, not {c}".format(
                        vc=valid_commands,v=command) 
            self.logger.warning(message)
            result = {'error':{'message':message,'code':0}}
        return self._result_checker(result,**kwargs)
    def _token_acquire(self,name,timeout=None,**kwargs):
        '''Attempt to acquire the control token. If the result is 'ok' we were successfull.
        The name argument should be a string which indicates who is requesting the token.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        result = self.socket_handler.send_rpc('tokenAcquire',
                                              self._json_id,
                                              timeout=timeout,
                                              params = {"name":name},
                                              debug_mode=debug_mode,
                                              **kwargs)
        if debug_mode: print(("{0}._token_acquire for {1} result: {2}".format(self.BROKER_NAME,name,result)))
        acquire_result = self._result_checker(result,debug_mode=debug_mode,**kwargs)
        if acquire_result.get('result') == 'ok':
            self.token_acquired = True
        else:
            if 'error' in acquire_result:
                error_msg = acquire_result.get('error',{}).get('message','bad msg')
                error_data = acquire_result.get('error',{}).get('data','')
                error_code = acquire_result.get('error',{}).get('code',0)
                if error_code == -31929: # Another listener currently has the control token.
                    self.logger.warning("{0} {1}[{2}]".format(error_msg,error_data,error_code))
                else:
                    self.logger.error("{0} {1}[{2}]".format(error_msg,error_data,error_code))
                self.token_acquired = False
            else:
                self.logger.error("Unknown response in {bn}._token_acquire: {ar}",format(
                                    bn=self.BROKER_NAME,ar=acquire_result))
        return acquire_result
    def _token_force_acquire(self,name,timeout=None,**kwargs):
        '''Acquires the control token.
        The name argument should be a string which indicates who is requesting the token.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        _token_force_acquire_result = self.socket_handler.send_rpc('tokenForceAcquire',
                                                                   self._json_id,
                                                                   timeout=timeout,
                                                                   params = {"name":name},
                                                                   debug_mode=debug_mode)
        if debug_mode: print("_token_force_acquire for {0} result: {1}".format(name,_token_force_acquire_result))
        force_acquire_result = self._result_checker(_token_force_acquire_result)
        if force_acquire_result.get('result','error') == 'ok':
            self.token_acquired = True
        else:
            self.logger.error(force_acquire_result)
            self.token_acquired = False
        return force_acquire_result
    def tokenRelease(self,timeout=None,**kwargs):
        '''Releases the control token'''
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        tokenRelease_result = self.socket_handler.send_rpc('tokenRelease',
                                                           self._json_id,
                                                           timeout=timeout,
                                                           params=None,
                                                           debug_mode=debug_mode)
        if debug_mode: print("tokenRelease result: {0}".format(tokenRelease_result))
        release_result = self._result_checker(tokenRelease_result)
        if release_result.get('result') == 'ok':
            self.token_acquired = False
        return release_result
    def tokenOwner(self,timeout=None,**kwargs):
        '''Returns the name of the current token holder
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        tokenOwner_result = self.socket_handler.send_rpc('tokenOwner',
                                                         self._json_id,
                                                         timeout=timeout,
                                                         params=None,
                                                         debug_mode=debug_mode)
        owner_result = self._result_checker(tokenOwner_result)
        if debug_mode:
            print(("owner_result result: {0}".format(owner_result)))
            print(("tokenOwner result: {0}".format(tokenOwner_result)))
        return owner_result #.get('result',{})
    def get_token(self,program_name=None,calling_obj=None,override=False,**kwargs):
        '''
        Facilitates taking the token from yourself
        '''
        if program_name is None: program_name = __name__ # Module
        if calling_obj is None: calling_obj = self.__class__.__name__ # Class
        debug_mode = kwargs.pop('debug_mode',False)
        result = {}
        token_name = "{0}.{1}".format(program_name,calling_obj)
        result['tokenOwner 1'] = self.tokenOwner(debug_mode=debug_mode)
        try:
            token_owner = result['tokenOwner 1'].get('result',result['tokenOwner 1'])
        except:
            token_owner = result['tokenOwner 1']
        if program_name in token_owner:
            self.logger.debug( "Token is owned by self ({0}). Using _token_force_acquire".format(token_owner))
            result['_token_force_acquire'] = self._token_force_acquire(token_name)
            result['acquire_result'] = result['_token_force_acquire']
        elif token_owner == '':
            self.logger.debug( "Token is unowned. Using _token_acquire")
            result['_token_acquire'] = self._token_acquire(token_name)
            result['acquire_result'] = result['_token_acquire']
        else:
            if override:
                self.logger.info( "Override flag set, using _token_force_acquire to take token from {0}".format(token_owner))
                result['acquire_type'] = '_token_force_acquire'
                result['_token_force_acquire'] = self._token_force_acquire(token_name)
                result['acquire_result'] = result['_token_force_acquire']
            else:
                result['acquire_type'] = '_token_acquire'
                result['_token_acquire'] = self._token_acquire(token_name)
                if debug_mode: print(("Acquiring token from {0} for {1}".format(token_owner,token_name)))
                result['acquire_result'] = result['_token_acquire']
        # result['acquire_result'] should be {'result':'ok'} but might be {'error':{error stuff}}
        if result['acquire_result'].get('result','error') == 'ok':
            result['tokenOwner 2'] = self.tokenOwner(debug_mode=debug_mode)
            try:
                token_owner = result['tokenOwner 2'].get('result',result['tokenOwner 2'])
            except:
                token_owner = result['tokenOwner 2']
            self.logger.debug( "{0} token now owned by {1}".format(self.BROKER_NAME,token_owner))
        elif 'error' in result['acquire_result']:
            error_msg = result['acquire_result'].get('error',{}).get('message','bad msg')
            error_data = result['acquire_result'].get('error',{}).get('data','')
            error_code = result['acquire_result'].get('error',{}).get('code',0)
            self.logger.error("{0} error acuuiring token for {1} {2} {3}[{4}]".format(
                                self.BROKER_NAME, token_name,error_msg,error_data,error_code))
        else:
            print((result.get('acquire_result')))
            self.logger.error("Unknown response in {0}.get_token: {1}",format(
                                self.BROKER_NAME,result.get('acquire_result')))
        if debug_mode: print("get_token result:{0}".format(result))
        return result
    def shutdown_broker(self,timeout=None,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        self.token_acquired = False
        return self.socket_handler.send_rpc('shutdown',
                                            self._json_id,
                                            timeout=timeout,
                                            params=None,
                                            debug_mode=debug_mode)
    def suspend_broker(self,timeout=None,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        return self.socket_handler.send_rpc('suspend',
                                            self._json_id,
                                            timeout=timeout,
                                            params=None,
                                            debug_mode=debug_mode)
    def resume_broker(self,timeout=None,**kwargs):
        '''
        
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if timeout is None:
            timeout = self.RESUME_TIMEOUT # Sonde takes longer to startup
        self._json_id += 1
        resume_result =  self.socket_handler.send_rpc('resume',
                                                      self._json_id,
                                                      timeout=timeout,
                                                      params=None,
                                                      debug_mode=debug_mode)
        if debug_mode: print(("resume_result ={0}".format(resume_result)))
        if resume_result.get('result') == 'ok' and self.initialized is False:
            self.logger.info("Initializing {0}".format(self.BROKER_NAME))
            self.re_structure_data(debug_mode=debug_mode)
        return self._result_checker(resume_result)
    def broker_status(self,timeout=None,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        self._json_id += 1
        result =  self.socket_handler.send_rpc('broker_status',
                                               self._json_id,
                                               timeout=timeout,
                                               params=None,
                                               debug_mode=debug_mode)
        broker_status_result = self._result_checker(result)
        self.power_on = avp_util.t_or_f(broker_status_result.get('power_on',False),debug_mode=debug_mode)
        self.db_connected = avp_util.t_or_f(broker_status_result.get('db_connected',False),debug_mode=debug_mode)
        self.instr_connected = avp_util.t_or_f(broker_status_result.get('instr_connected',False),debug_mode=debug_mode)
        self.suspended = avp_util.t_or_f(broker_status_result.get('suspended',False),debug_mode=debug_mode)
        self.last_db_time = broker_status_result.get('last_db_time',None)
        self.last_data_time = broker_status_result.get('last_data_time',None)
        self.start_time = broker_status_result.get('start_time',None)
        return broker_status_result

class _DataItem(object): 
    '''
    This class represents a single broker parameter.
    Keyword Arguments:
        broker_name --  Name of broker to which this parameter belongs. E.g. 'sonde'
        data_name   --  Name of this parameter. E.g. 'depth_m' in most cases this will alo be the object instances's name
        data_type   --  One of ('RO', 'RW', 'WO')
        data_units  --  Units for parameter
        ...
        stale_time  --  If a subscribed value is older than this (seconds), call status() before returning _value
    We are using property() to use getters and setters for class attributes
    RW Class Attributes (getters and setters):
    The availability of these attributes vary by data_type
        value               --  Queries the broker for a new value or tells the broker to set it to new value.
        mem_value           --  The most recent value of this parameter recieved from broker.
        subscribed          --  Are we subscribed to this parameter? (True/False)
        tz                  --  Time Zone for message_time
        set_to              --  Most revent value used in set() command
        set_at              --  datetime when last set()
    RO Class Attributes (getters only):
        data_name
        units
        sample_time_long    --  Integer representing time of most recent value update
        sample_time         --  Datetime object representing sample_time_long
        tz                  -- Time Zone
    
    '''
    READ_CLASSES = ('RO','RW')
    WRITE_CLASSES = ('WO','RW')
    def __init__(self,broker_name,data_name,data_type,data_units,logger,set_method,get_method,stale_time=10,**kwargs):
        self.logger = logger
        self._data_name = data_name
        self.data_type = data_type
        self.BROKER_NAME = broker_name
        self.set = set_method
        self.get = get_method
        self._stale_td = timedelta(seconds=stale_time)
        self._subscribed = False # For some this will always be False
        self._value = None
        self._tz = None
        if self.data_type in self.READ_CLASSES + self.WRITE_CLASSES:
            self._units = data_units
            self._value = None # These values are all come from the broker. Was float('nan')
            if self.data_type in self.READ_CLASSES:
                self._sample_time_long = 20000101123000000
                self._sample_time = get_date_time(self._sample_time_long)
                self._tz = '?'
            if self.data_type in self.WRITE_CLASSES: # These just record the last time the values was changed by the program.
                self.set_to = None
                self.set_at = datetime(1,1,1) # A long long time ago.
        else:
            # probably 'NI'
            pass
    def DI_status(self):
        message  = "Status of {0}.{1}\r\n".format(self.BROKER_NAME,self._data_name)
        message += "Subscribed == {0}, data_type = {1}\r\n".format(self._subscribed,self.data_type)
        if hasattr(self,'_value'):
            message +=     "value = {0}".format(self._value)
            if hasattr(self,'_units'):
                message +=            "{0}".format(self._units)
            else:
                message +=            "\r\n"
        if hasattr(self,'_sample_time_long'):
            message += 'sample time == {0} {1}\r\n'.format(self._sample_time_long,self._tz)
        if hasattr(self,'set_to'):
            message += ""
    '''
    We use property() here to defines setters and getters for these.
    First the read only attributes which only have getters
    '''
    def get_mem_value(self):
        return self._value
    def get_data_name(self): return self._data_name # Always have a  _data_name
    def get_units(self):
        if hasattr(self,'_units'):
            return self._units
        else: return None
    def get_sample_time_long(self): 
        if hasattr(self,'_sample_time_long'):
            return self._sample_time_long
        else: return 0
    def get_sample_time(self): 
        if hasattr(self,'_sample_time'):
            return self._sample_time
        else: return None
    def get_tz(self):
        if hasattr(self,'_tz'):
            return self._tz
        else: return None
    mem_value = property(get_mem_value)
    data_name = property(get_data_name)
    units = property(get_units)
    sample_time_long = property(get_sample_time_long)
    sample_time = property(get_sample_time)
    tz = property(get_tz)
    # Now the more involved ones...
    def value_getter(self):
        # Returns value currently in memory
        if hasattr(self,'_value') and self.data_type in self.READ_CLASSES:
            if (self._subscribed == False or (self._sample_time < datetime.now(pytz.reference.LocalTimezone()) - self._stale_td)):
                # RYAN is _sample_time not updating with subscriprions?
                status_return = self.get([self.data_name]) # Only ask for it if we aren't subscribed.
            return self._value
        else:
            self.logger.debug("Parameter {1}.{2} of type {0} has no value.".format(self.data_type,self.BROKER_NAME,self._data_name))
            return None
    def value_setter(self,set_value):
        if hasattr(self,'_value'):
            if self.data_type in self.WRITE_CLASSES:
                self.set({self._data_name:set_value})
            else:
                self.logger.warning("Parameter {1}.{2} of type {0} can not be set to {3}.".format(
                                        self.data_type,self.BROKER_NAME,self._data_name,set_value))
        else:
            self.logger.warning("Parameter {1}.{2} of type {0} has no value.".format(
                                    self.data_type,self.BROKER_NAME,self._data_name))
    def del_value(self,value):
        if hasattr(self,'_value'):
            self._value = None
        else:
            self.logger.warning("Parameter {1}.{2} of type {0} has no value to clear.".format(
                                    self.data_type,self.BROKER_NAME,self._data_name))
    value = property(value_getter,value_setter,del_value)
    def get_sub(self):
        if hasattr(self,'_subscribed'):
            return self._subscribed
        else:
            self.logger.warning("Parameter {1}.{2} of type {0} not subscribable.".format(
                                    self.data_type,self.BROKER_NAME,self._data_name))
            return None
    def set_sub(self,value):
        if hasattr(self,'_subscribed'):
            if value:
                self.logger.warning("Use {0}.add_subscriptions() method.".format(self.BROKER_NAME))
            else:
                self.logger.warning("Use {0}.unsubscribe() method.".format(self.BROKER_NAME))
        else:
            self.logger.warning("Parameter {1}.{2} of type {0} not subscribable.".format(
                                    self.data_type,self.BROKER_NAME,self._data_name))
    subscribed = property(get_sub,set_sub)

class SondeBroker(_BrokerClient):
    '''
    Adds methods and variables specific to the YSI sonde

    Public Methods: wipe, calibrate_pressure, start_sampling, start_logging,
                    stop_logging, stop_sampling,  is_logging,
                    in_water
    Instance Variables: broker_name, WIPE_TIMEOUT, INSTRUMENT_OFFSET,
                        BOTTOM_OFFSET, inwater_cond,
                        INWATER_DEPTH, location, pressure_error
                        SONDE_STARTUP_TIME, PRESSURE_ERROR
    '''
    BROKER_NAME = 'sonde'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False) # Not .pop()
        self.pressure_error = 0.00 # This can be altered to represent pressure errors too small to 
                                   # warrant a re-calibration
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(SondeBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # These are default values which are overwritten by [[constants]] in config when load_config
        # is called below
        self.SAMPLE_TIMEOUT     = 40
        self.WIPE_TIMEOUT       = 120
        self.INSTRUMENT_OFFSET  = 0.254
        self.BOTTOM_OFFSET      = 0.200
        self.inwater_cond       = 3.0
        self.INWATER_DEPTH      = 0.010
        self.SONDE_STARTUP_TIME = 5.0
        self.PRESSURE_ERROR     = 0.004
        super(SondeBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def wipe(self,**kwargs):
        ''' Wipe is a method specific to the sonde broker.
        '''
        if not self._is_initialized(method_name='wipe'): return {}
        if self.sampling.value != False: 
            self.logger.error("Can not wipe while in sampling mode ({0}).".format(self.sampling.value))
            return 0
        self._json_id += 1
        wipe_result =  self.socket_handler.send_rpc('wipe',
                                                    self._json_id,
                                                    timeout=self.WIPE_TIMEOUT,
                                                    params=None,
                                                    **kwargs)
        return self._result_checker(wipe_result)
    def _cal_press(self,timeout=None,**kwargs):
        ''' calibrate_pressure is a method specific to the sonde broker.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='_cal_press'): return {}
        if debug_mode: print("Calibrating pressure")
        self._json_id += 1
        calibrate_pressure_result =  self.socket_handler.send_rpc('calibratePressure',
                                                                  self._json_id,
                                                                  timeout=timeout,
                                                                  params=None,
                                                                  debug_mode=debug_mode)
        return self._result_checker(calibrate_pressure_result)
    def calibrate_pressure(self,check_instruments=True,**kwargs):
        '''
        Wraps the _cal_press method around some additional error checking functionality.
        Leaves sampling mode the same as when it starts.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='calibrate_pressure'): return {}
        result = {}
        #if not self.depth_m.subscribed:
        #    self.add_subscriptions(['depth_m'],**kwargs)
        #if not self.spcond_mScm.subscribed:
        #    self.add_subscriptions(['spcond_mScm'],**kwargs)
        result['in_water'] = self.in_water(instrument='spcond_mScm',debug_mode=debug_mode)
        if result['in_water'][0]:
            if check_instruments:
                result['error'] = "Error calibrating pressure: Conductivity {0} indicates sonde may be in water.({1})".format(self.spcond_mScm.value,result['in_water'])
                self.logger.warning(result['error'])
                return result
            else:
                self.logger.warning("Calibrating pressure despite conductivity {0} indicating sonde may be in water.({1})".format(self.spcond_mScm.value,result['in_water']))
        # Calibrate
        old_depth = self.depth_m.value
        sampling_status = self.sampling.value # Record original sampling state, so we can return in same state.
        if self.sampling.value != False:
            result['stop_sampling'] = self.stop_sampling(timeout=None,debug_mode=debug_mode)  # Stop sampling mode
        result['_cal_press'] = self._cal_press(timeout=60,debug_mode=debug_mode)        # Calibrate needs longer timeout
        if result['_cal_press'].get('error',False):
            self.logger.warning("Error calibrating pressure: {0}".format(result['_cal_press']['error']))
        wake_time = datetime.now(pytz.reference.LocalTimezone()) + timedelta(seconds=self.SONDE_STARTUP_TIME)
        self.logger.info("Waiting {0} sec for calibration procedure and settling.".format(self.SONDE_STARTUP_TIME))
        while datetime.now(pytz.reference.LocalTimezone()) < wake_time:
            print(".")
            time.sleep(1)
        print()
        result['SondeBroker.start_sampling'] = self.start_sampling(debug_mode=debug_mode) # Restart sampling
        wake_time = datetime.now(pytz.reference.LocalTimezone()) + timedelta(seconds=5)
        self.logger.info("Waiting {0} sec for new depth value ".format((wake_time - datetime.now(pytz.reference.LocalTimezone())).seconds),)
        while datetime.now(pytz.reference.LocalTimezone()) < wake_time:
            print("{0:6} {1}".format(self.depth_m.value,self.depth_m.units))
            time.sleep(1)
        print()
        self.get_value(['depth_m'],verbose=False,timeout=None,debug_mode=debug_mode) #refresh value
        # See if calibration was successful
        if abs(self.depth_m.value) > self.PRESSURE_ERROR:
            result['error'] = {'message':'Pressure {0} indicates bad calibration may have occured.'.format(self.depth_m.value),'code':0}
            self.logger.error("In {0}.calibrate_pressure: {1}".format(self.BROKER_NAME, result['error'].get('message')))
        else:
            self.logger.info("Pressure calibrated from {0} to {1}".format(old_depth,self.depth_m.value))
            result['result'] = 'ok'
        self.pressure_error = 0.00 # No more calibration error, or old value not appropriate.
        if not sampling_status:
            result['stop_sampling'] = self.stop_sampling(timeout=timeout,debug_mode=debug_mode)  # return to the state in which we started.
        return result
    def start_sampling(self,**kwargs): # was start_collection
        '''
        Put sonde in sampling (run) mode
        Status can be checked with self.sampling.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='start_sampling'): return {}
        if debug_mode: print("Starting sampling")
        self._json_id += 1
        start_sampling_result =  self.socket_handler.send_rpc('start_sampling',
                                                                self._json_id,
                                                                timeout=self.SAMPLE_TIMEOUT,
                                                                params=None,
                                                                debug_mode=debug_mode)
        return self._result_checker(start_sampling_result)
    def stop_sampling(self,timeout=None,**kwargs): # was stop_collection
        '''
        Take sonde out of sampling (run) mode
        Status can be checked with self.sampling.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='stop_sampling'): return {}
        if self.is_logging(timeout=timeout,debug_mode=debug_mode):
            self.stop_logging(timeout=timeout,debug_mode=debug_mode)
        if debug_mode: print("Stopping sampling")
        self._json_id += 1
        stop_sampling_result =  self.socket_handler.send_rpc('stop_sampling',
                                                               self._json_id,
                                                               params=None,
                                                               timeout=timeout,
                                                               debug_mode=debug_mode)
        return self._result_checker(stop_sampling_result)
    def start_logging(self,cast_number,timeout=None,**kwargs):
        '''
        Put sonde in logging to database mode. Requires cast_number
        Status can be checked with self.logging.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='start_logging'): return {}
        if self.sampling.value != True:
            self.start_sampling(debug_mode=debug_mode)
        self._json_id += 1
        start_logging_result =  self.socket_handler.send_rpc('start_logging',
                                                             self._json_id,
                                                             timeout=timeout,
                                                             params = {"cast_number":cast_number},
                                                             debug_mode=debug_mode)
        return self._result_checker(start_logging_result)
    def stop_logging(self,timeout=None,**kwargs):
        '''
        Stop sonde logging to database
        Status can be checked with self.logging.value
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='stop_logging'): return {}
        self._json_id += 1
        stop_logging_result =  self.socket_handler.send_rpc('stop_logging',
                                                            self._json_id,
                                                            timeout=timeout,
                                                            params=None,
                                                            debug_mode=debug_mode)
        return self._result_checker(stop_logging_result)
    def is_logging(self,timeout=None,**kwargs):
        if not self._is_initialized(method_name='is_logging'): return {}
        debug_mode = kwargs.pop('debug_mode',False)
        if not self.sampling.subscribed:
            self.add_subscriptions(['logging'],
                                   on_change=True,
                                   verbose=False,
                                   timeout=timeout,
                                   min_interval=None,
                                   max_interval=None,
                                   debug_mode=debug_mode)
            try:
                self.get_value(['logging'],verbose=False,debug_mode=debug_mode)
            except Exception as e:
                self.logger.error("Error: Unable to get logging status: {0}".format(e))
                return 0
        return self.logging.value
    def in_water(self,instrument='all',**kwargs):
        '''
        Uses specified instrument ('depth_m'|'spcond_mScm'|'any'|'all') to determine if sensor is in water.
        Returns a list with two elements.
        The first list element is a True if it is in the water, False if it isn't, or None if unknown
        The second is the comparison used.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='in_water'): return [None,'sonde object not initialized']
        depth_in_water = spcond_in_water = None
        in_water = None
        conductivity = None
        message = ''
        valid_instruments = ['any','all','spcond_mScm','spcond_uScm','depth_m']
        if instrument not in valid_instruments:
            message = '{0} is not a valid instrument for sonde.in_water'.format(instrument)
            self.logger.error(message)
            return [None,message]
        if self.sampling.value is not True:
            if debug_mode: print("Starting sonde sampling:")
            self.start_sampling(debug_mode=debug_mode)
            time.sleep(self.SONDE_STARTUP_TIME)
        try:
            # Conductivity comes in different units.
            if hasattr(self,"spcond_mScm"):
                if self.spcond_mScm.subscribed is False:
                    self.get_value(['spcond_mScm'])
                conductivity = self.spcond_mScm.value
            if hasattr(self, "spcond_uScm"):
                if self.spcond_uScm.subscribed is False:
                    self.get_value(['spcond_uScm'])
                conductivity = self.spcond_uScm.value * 1000
        except TypeError as e:
            # probably don't have a conductivity value
            print(("Couldn't find conductivity value"))
        if self.depth_m.subscribed is False:
            self.get_value(['depth_m'])
        if debug_mode:
            print(("comparing current conductivity {0} to max allowed {1}".format(conductivity,self.inwater_cond)))
        if conductivity is None:
            message += "spcond unknown. "
        elif conductivity >= self.inwater_cond:
            message += "{0}: {1} >= {2}. ".format('spcond_mScm',conductivity,self.inwater_cond)
            spcond_in_water = True
        else:
            message +=  '{0}: {1} < {2}. '.format('spcond_mScm',conductivity,self.inwater_cond)
            spcond_in_water = False
        if debug_mode: print("comparing current depth_m {0} to max allowed {1}".format(self.depth_m.value,self.INWATER_DEPTH))
        if self.depth_m.value is None:
            message += 'depth_m unknown. '
        elif self.depth_m.value >= self.INWATER_DEPTH + self.pressure_error: 
            message += "{0}: {1} >= {2} + {3}. ".format('depth_m',self.depth_m.value,self.INWATER_DEPTH,self.pressure_error)
            depth_in_water = True
        else:
            message += "{0}: {1} < {2} + {3}. ".format('depth_m',self.depth_m.value,self.INWATER_DEPTH,self.pressure_error)
            depth_in_water = False
        if debug_mode: print(("in_water depth:{0} cond:{1} req:{2}".format(depth_in_water,spcond_in_water,instrument)))
        if instrument   == 'all':         in_water = depth_in_water and spcond_in_water
        elif instrument == 'any':         in_water = depth_in_water or spcond_in_water
        elif instrument == 'depth_m':     in_water = depth_in_water 
        elif instrument == 'spcond_mScm': in_water = spcond_in_water
        elif instrument == 'spcond_uScm': in_water = spcond_in_water
        return [in_water,message]

class MM3Broker(_BrokerClient):
    '''
    This MM3Broker class adds methods and attributes specific to the
        Motion Mind 3 motor controller

    Public Methods: _move_to_setup, move_to_position, move_to_relative,
                    move_at_speed, stop, motor_cb, limit_cb, reset, restore,
                    write_store, store_position
    Instance Variables: broker_name, AMPS_LIMIT
    '''
    BROKER_NAME = 'mm3'
    def __init__(self,config,check_defaults=True,**kwargs):
        '''
        Initializes the MotionMind3 controller client's interface.
        '''
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        try: # IPC Database stuff
            self.ipc_db = avp_db.AvpDB(self.config,self.IPC_TABLE,polling=True)
        except Exception as e:
            self.logger.critical('Error in {0}.__init__ initializing IPC database {1}'.format(self.BROKER_NAME,e))
        self.amps_limit = None
        self.temperature = None
        self.position  = None
        self.amps = None
        super(MM3Broker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
        if check_defaults is True:
            self._check_defaults(debug_mode=debug_mode)
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # These are default values which are overwritten by [[constants]] in config when load_config
        # is called below
        self.AMPS_LIMIT    = 3500
        self.DEFAULT_SPEED = 5
        self.MIN_SPEED     = 1
        self.IPC_TABLE = self.config.get('db',{}).get('IPC_TABLE','avp_ipc')
        # This broker uses the IPC_TABLE
        super(MM3Broker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def _check_defaults(self,**kwargs):
        '''
        Reads in a list of defaults from the config file.
        Checks these default values against the current values.
        Updates any which are wrong.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        defaults_to_set = {}
        checked_defaults = {}
        defaults = self.config[self.BROKER_NAME].get('defaults')
        if not defaults: return 0
        for param,value in list(defaults.items()): # make sure we have all these
            if hasattr(self,param):
                checked_defaults[param] = value
            else:
                self.logger.error("Broker {0} has no parameter {1}. Default not set.".format(self.BROKER_NAME,param))
        current_value_dict = self.get_value(list(checked_defaults.keys())) # returns a dictionary of values
        if 'error' in current_value_dict:
            self.logger.error("Error {cvec} in {bn}._check_defaults: {cvem} ({cvd})".format(
                                cvec=current_value_dict.get('error').get('code'),bn=self.BROKER_NAME,
                                cvem=current_value_dict.get('error').get('message'),
                                cvd=current_value_dict))
            return 0
        for param,default_value in list(checked_defaults.items()):
            current_value = str(current_value_dict.get(param))
            if default_value != current_value:
                defaults_to_set[param] = default_value
                self.logger.info("{bn}:parameter {p} is {cv} will be set to default of {dv}".format(
                                    p=param,cv=current_value,dv=default_value,bn=self.BROKER_NAME))
        if len(defaults_to_set) > 0:
            self.get_token(override=True,
                           calling_obj="{0}._check_defaults".format(self.BROKER_NAME),
                           debug_mode=debug_mode)
            result = self.set(defaults_to_set)
            self.tokenRelease()
        else:
            self.logger.debug("No {0} default values to set.".format(self.BROKER_NAME))
            result = 1
        return result
    def _move_to_setup(self, speedlimit=None, velocity_limit_enable=1, enable_db=1, PWM_limit=1023, amps_limit=None, disable_pid=0, **kwargs):
        '''
        Sets a number of mm3 registers in anticipation of a move.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        set_dict = {}
        if speedlimit is None:
            speedlimit = self.DEFAULT_SPEED
            if debug_mode: print(("No speedlimit given to _move_to_setup. Using default of {0}".format(self.DEFAULT_SPEED)))
        if amps_limit is None:
            amps_limit = self.AMPS_LIMIT
        set_dict['velocity_limit'] = speedlimit
        set_dict['velocity_limit_enable'] = velocity_limit_enable # Turn on velocity limits
        set_dict['enable_db'] = enable_db # Turn on deadband enable
        set_dict['PWM_limit'] = PWM_limit # set this to max value
        set_dict['amps_limit'] = amps_limit # set this to default
        set_dict['disable_pid'] = disable_pid # don't disable PID
        result = {'set':self.set(set_dict,write_store=False,timeout=None,debug_mode=debug_mode)}
        #result['set'] = self.set(set_dict,write_store=False,timeout=None,debug_mode=debug_mode)
        return result
    def move_to_position(self, location, speedlimit=None, amps_limit=None, enable_db=1, **kwargs):
        '''
        This method encapsulates a few settings which should be set before a move_to_absolute is performed.
        Instance variables:
            result
                _move_to_setup, db.update, set,
        '''        
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='move_to_position'): return {}
        result = {}
        if speedlimit is None:
            speedlimit = self.DEFAULT_SPEED
        if amps_limit is None:
            amps_limit = self.AMPS_LIMIT
        if debug_mode: print(("{0} move_to_position: setup".format(str(datetime.now(pytz.reference.LocalTimezone())))))
        result['_move_to_setup'] = self._move_to_setup(speedlimit=speedlimit,
                                                       amps_limit=amps_limit,
                                                       velocity_limit_enable=1,
                                                       enable_db=enable_db,
                                                       PWM_limit=1023,
                                                       disable_pid=0,
                                                       debug_mode=debug_mode)
        result['_clear_stop_reason'] = self._clear_stop_reason(debug_mode=debug_mode)
        if result['_clear_stop_reason'].get('error',False):
            self.logger.error("Error in {0}.move_to_position._clear_stop_reason: {1}".format(self.BROKER_NAME,result['_clear_stop_reason']['error']))
        if debug_mode: print(("     {0} start move to {1}".format(str(datetime.now(pytz.reference.LocalTimezone())),location)))
        try:
            result['set'] = self.set({'move_to_absolute':location},
                                     write_store=False,
                                     timeout=None,
                                     debug_mode=debug_mode)
            result['stop'] = ''
        except Exception as e:
            self.logger.error( "Error with set in {0}.move_to_absolute:{1}".format(self.BROKER_NAME,e) )
            result['stop'] = self.stop(debug_mode=debug_mode)
            result['error'] = e
        if result.get('error',False):
            self.logger.error("Error in {0}.move_to_position.set: {1}".format(self.BROKER_NAME,result['error']))
        if debug_mode: print(("     {0} done".format(str(datetime.now(pytz.reference.LocalTimezone())))))
        return result
    def move_to_relative(self, distance, speedlimit=None, velocity_limit_enable=1, enable_db=1, PWM_limit=1023, amps_limit=None, disable_pid=0, **kwargs):
        '''
        Abstract's mm3's move_to_rel functionality.
        '''
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='move_to_relative'): return {}
        result = {}
        result['_move_to_setup'] = self._move_to_setup(speedlimit=speedlimit,
                                                       velocity_limit_enable=velocity_limit_enable,
                                                       enable_db=enable_db,
                                                       PWM_limit=PWM_limit,
                                                       amps_limit=amps_limit,
                                                       disable_pid=disable_pid,
                                                       debug_mode=debug_mode)
        result['_clear_stop_reason'] = self._clear_stop_reason(debug_mode=debug_mode)
        if result['_clear_stop_reason'].get('error',False):
            self.logger.error("Error in {0}.move_to_relative._clear_stop_reason: {1}".format(self.BROKER_NAME,result['_clear_stop_reason']['error']))
        if debug_mode: print(("     {0} start relative move:{1}".format(str(datetime.now(pytz.reference.LocalTimezone())),distance)))
        try:
            result['set'] = self.set({'move_to_rel':distance},write_store=False,timeout=None,debug_mode=debug_mode) # Here is the move
        except Exception as e:
            self.logger.error( "Error with set in {0}.move_to_relative:{1}".format(self.BROKER_NAME,e) )
            self.stop(check_defaults=False,timeout=None,debug_mode=debug_mode)
            result['error'] = e
        if result.get('error',False):
            self.logger.error("Error in {0}.move_to_relative.set: {1}".format(self.BROKER_NAME,result['error']))
        if debug_mode: print(("     {0} done".format(str(datetime.now(pytz.reference.LocalTimezone())))))
        return result
    def move_at_speed(self, motor_speed, direction=None, amps_limit=None, enable_db=True, **kwargs):
        '''
        Abstract's mm3's move_at functionality.
        '''
        if not self._is_initialized(method_name='move_at_speed'): return {}
        if amps_limit is None:
            amps_limit = self.AMPS_LIMIT
        debug_mode = kwargs.pop('debug_mode',False) 
        result = {}
        try:
            motor_speed = abs(int(motor_speed))
        except Exception as e:
            self.logger.error("Invalid move_at_speed.motor_speed parameter:{0},e".format(motor_speed, e))
            return result
        if direction == 'up':
            motor_speed *= -1
        elif direction == 'down':
            pass
        else:
            self.logger.debug("Error in move_at: {0} at {1} is an invalid command".format(direction, motor_speed))
            return result
        if enable_db is True: enable_db = 1
        else: enable_db = 0
        if amps_limit != self.amps_limit.value:
            if debug_mode: print(("Setting amps_limit from {0} to {1} mA".format(self.amps_limit.value,amps_limit)))
            result['set(amps_limit)'] = self.set({'amps_limit':int(amps_limit)},write_store=False,timeout=None,debug_mode=debug_mode)
        try:
            if debug_mode: print(( "{0} move_at_speed: setup".format(str(datetime.now(pytz.reference.LocalTimezone())))))
            result['_clear_stop_reason'] = self._clear_stop_reason(debug_mode=debug_mode)
            #stop_reason = ''
            #set_values={'value':stop_reason,'time':datetime.now(pytz.reference.LocalTimezone())}
            #where_condition = {'broker':self.BROKER_NAME,'param':'stop_reason'}
            #self.ipc_db.update(set_values,
            #                   where_condition=where_condition,
            #                   where_oper='=',debug_mode=debug_mode)
            #if debug_mode: print "cleared stop_reason in database "
            result['set(velocity_limit_enable)'] = self.set({'velocity_limit_enable':0,
                                'velocity_limit':99,
                                'enable_db':enable_db,
                                'PWM_limit':1023,
                                'disable_pid':0},
                                write_store=False,timeout=None,debug_mode=debug_mode)
            if debug_mode: print(("     {0} start move at {1}".format(str(datetime.now(pytz.reference.LocalTimezone())), motor_speed)))
            result['set(move_at)'] = self.set({'move_at':motor_speed}, write_store=False, timeout=None, debug_mode=debug_mode)
        except Exception as e:
            self.logger.error( "Error with set in {0}.move_at_speed:{1}".format(self.BROKER_NAME,e) )
            self.stop(check_defaults=False,timeout=None,debug_mode=debug_mode)
            result['set(move_at)'] = {'error':e}
        if result['set(move_at)'].get('error',False):
            self.logger.error("Error in move_at_speed: {0}".format(result['set(move_at)']['error']))
        return result
    def _clear_stop_reason(self,**kwargs):
        '''
        Clears stop reason from ipc database
        '''
        result = {}
        debug_mode = kwargs.pop('debug_mode',False) 
        where_condition = {'broker':self.BROKER_NAME,'param':'stop_reason'}
        set_values={'value':'','time':datetime.now(pytz.reference.LocalTimezone())}
        try:
            result['result'] = self.ipc_db.update(set_values,
                                                  where_condition=where_condition,
                                                  where_join='AND',
                                                  where_oper='=',
                                                  debug_mode=debug_mode)
            if debug_mode: print("cleared stop_reason in database ")
            self.ipc_db.poll() # Clear any notification this caused.
        except Exception as e:
            self.logger.error( "Error in {0}._clear_stop_reason:{1}".format(self.BROKER_NAME,e) )
            result['stop'] = self.stop(check_defaults=False,debug_mode=debug_mode)
            result['error'] = e
        return result
    def stop(self,check_defaults=False,timeout=None,**kwargs):
        '''
        Stop the motor
        We could put a try here, and the except would kill the power to the mm3 via the aio broker.
        Keyword Arguments:
            check_defaults -- Defaults to False
        '''
        result = {}
        debug_mode = kwargs.pop('debug_mode',False) 
        if self.token_acquired is False: # if we already had the token, do nothing with it
            self.get_token(override=True,
                           calling_obj="{0}.stop".format(self.BROKER_NAME),
                           debug_mode=debug_mode)
            release_token = True
        else:
            release_token = False
        result['set'] = self.set({'move_at':0,'PWM_limit':0,'disable_pid':1},write_store=False,timeout=timeout,debug_mode=debug_mode) #Stop motor
        if release_token:
            self.tokenRelease(timeout=timeout,debug_mode=debug_mode)
        if result['set'].get('error',False):
            self.logger.error("In {0}.stop: {1}".format(self.BROKER_NAME,result['set']['error']))
        if check_defaults:
            self._check_defaults(debug_mode=debug_mode)
        return result
    def motor_cb(self,date_stamp,callback_obj,**kwargs):
        ''' This method will get called on any motor fault.
        It will often be used as a callback routine.
        '''
        result = {}
        if callback_obj.value == 1:
            result['stop'] = self.stop() # Stop Motor due to callback
            set_values = {'value':'{0}'.format(callback_obj.data_name),
                          'time':datetime.now(pytz.reference.LocalTimezone())}
            where_condition = {'broker':self.BROKER_NAME,'param':'stop_reason'}
            self.ipc_db.update(set_values,
                               where_condition=where_condition,
                               **kwargs)
            # Determine cause of fault.
            if callback_obj.data_name == 'current_limit':
                result['message'] = 'MM3 Current Limited at {0} mA'.format(self.amps_limit.value)
                self.logger.warning(result['message'])
            elif callback_obj.data_name == 'temp_fault':
                if 'temperature' not in self.subscriptions: # Can't assume we are subscribed to temperature
                    self.get_value(['temperature'])
                result['message'] = 'MM3 Temperature Error {0} {1}'.format(self.temperature.value,self.temperature.units)
                self.logger.critical(result['message'])
            else:
                result['message'] = 'MM3 unknown Error {0} {1}'.format(self.temperature.value,self.temperature.units)
                self.logger.critical(result['message'])
        else:
            # Just the bit resetting
            self.logger.debug("{0} motor callback reset.".format(callback_obj.data_name))
    def limit_cb(self,date_stamp,callback_obj):
        ''' This method will get called on any limit switch trip.
        It will often be used as a callback routine.
        '''
        if callback_obj.value == 1:
            if 'position' not in self.subscriptions: # Can't assume we are subscribed to temperature
                self.get_value(['position'])
            # Determine cause of fault.
            if callback_obj.data_name == 'neg_limit_switch':
                self.logger.info('Upper limit photo-switch tripped. Position = %s' % self.position.value)
            elif callback_obj.data_name == 'pos_limit_switch':
                self.logger.info('Cable tension switch tripped. Position = %s' % self.position.value)
            else:
                self.logger.error('Unknown limit callback: {0}'.format(callback_obj.data_name))
        else:
            # Just the bit resetting
            self.logger.debug("{0} limit callback reset.".format(callback_obj.data_name))
    def reset(self,timeout=None,**kwargs):
        ''' Implements the Motion Mind 3's reset command
        Sending the RESET command causes the Motion Mind Controller to stop the motor and software reset.
        '''
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='reset'):
            return 0
        self._json_id += 1
        result =  self.socket_handler.send_rpc('reset',
                                               self._json_id,
                                               timeout=timeout,
                                               params=None,
                                               debug_mode=debug_mode)
        if debug_mode: print("mm3Broker.reset result:{0}".format(result))
        return self._result_checker(result)
    def restore(self,timeout=None,**kwargs):
        ''' Implements the Motion Mind 3's resore command
        The restore command restores the factory default values to EEPROM. Since this command writes to
        EEPROM, the motor is stopped after the command is deemed valid.
        '''
        debug_mode = kwargs.pop('debug_mode',False) 
        if not self._is_initialized(method_name='restore'): return 0
        self._json_id += 1
        result =  self.socket_handler.send_rpc('restore',
                                               self._json_id,
                                               timeout=timeout,
                                               params=None,
                                               debug_mode=debug_mode)
        if debug_mode: print("mm3Broker.restore result:{0}".format(result))
        return self._result_checker(result)
    def do_write_store(self,params,**kwargs): #Can't call this write-store since there is already a parameter called that
        ''' Implements the Motion Mind 3's write store command
        '''
        if not self._is_initialized(method_name='do_write_store'): return {}
        debug_mode = kwargs.pop('debug_mode',False) 
        result = self.set(params,write_store=True,timeout=None,debug_mode=debug_mode)
        return result
    def store_position(self,position=None,**kwargs):
        '''Store current MM3 position to EEPROM
        If position isn't given, stores current position
        '''
        if not self._is_initialized(method_name='store_position'): return {}
        debug_mode = kwargs.pop('debug_mode',False) 
        if position is None:
            result = self.get_value(['position'],verbose=False,debug_mode=debug_mode)
            position = self.position.value
        if debug_mode: print("Saving position {0} to EEPROM".format(position))
        result = self.do_write_store(params={'position':position}, debug_mode=debug_mode)
        return result

class SounderBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the NMEA depth sounder
    Public Methods: None
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'sounder'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(SounderBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # Sounder doesn't have anything to load.
        super(SounderBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return

class GpsBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the GPS
    Public Methods: None
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'gps'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(GpsBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # Sounder doesn't have anything to load.
        super(GpsBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return

class IscoBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the ISCO
    Public Methods: take_sample, sampler_on, get_sample_status, get_isco_status
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'isco'
    _ISCO_STATUS = {1:'WAITING TO SAMPLE',
                    4:'POWER FAILED',
                    5:'PUMP JAMMED',
                    6:'DISTRIBUTOR JAMMED',
                    9:'SAMPLER OFF',
                    12:'SAMPLE IN PROGRESS',
                    20:'INVALID COMMAND',
                    21:'CHECKSUM MISMATCH',
                    22:'INVALID BOTTLE',
                    23:'VOLUME OUT OF RANGE'}
    _SAMPLE_STATUS = {0:'SAMPLE OK',
                    1 :'NO LIQUID FOUND',
                    2 :'LIQUID LOST',
                    3 :'USER STOPPED',
                    4 :'POWER FAILED',
                    5 :'PUMP JAMMED',
                    6 :'DISTRIBUTOR JAMMED',
                    8 :'PUMP LATCH OPEN',
                    9 :'SAMPLER SHUT OFF',
                    11:'NO DISTRIBUTOR',
                    12:'SAMPLE IN PROGRESS'}
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.BROKER_NAME)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(IscoBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Supe
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # These are default values which are overwritten by [[constants]] in config when load_config
        # is called below
        self.BOTTLE_SIZE = 1000
        self.NUM_BOTTLES = 24
        self.SAMPLE_TIMEOUT = 24
        super(IscoBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def take_sample(self,bottle, volume, cast_number, sample_depth,timeout=None,**kwargs):
        # take a sample into a specific bottle using a specific volume
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='take_sample'): return {}
        self._json_id += 1
        params = {"bottle_num":bottle, "sample_volume":volume, "cast_number":cast_number, "sample_depth":sample_depth}
        result =  self.socket_handler.send_rpc('take_sample',
                                               self._json_id,
                                               timeout=timeout,
                                               params=params,
                                               debug_mode=debug_mode)
        return self._result_checker(result)
    def sampler_on(self,timeout=None,**kwargs):
        # If the sampler is turned off via the panel, this will turn it on.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='sampler_on'): return {}
        self._json_id += 1
        result =  self.socket_handler.send_rpc('sampler_on',
                                               self._json_id,
                                               timeout=timeout,
                                               params=None,
                                               debug_mode=debug_mode)
        return self._result_checker(result)
    def get_sample_status(self,status_num=None,**kwargs):
        # Translate a number into a meaningfule string.
        if not self._is_initialized(method_name='get_sample_status'): return {}
        if status_num == None:
            status_num = self.sample_status.value
        result = self._SAMPLE_STATUS.get(status_num,"{0} is an unknown sample status.".format(status_num))
        return result
    def get_isco_status(self,status_num=None,**kwargs):
        # Translate a number into a meaningfule string.
        if not self._is_initialized(method_name='get_isco_status'): return {}
        if status_num == None:
            status_num = self.sample_status.value
        result = self._ISCO_STATUS.get(status_num,"{0} is an unknown ISCO status.".format(status_num))
        return result

class LisstBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the LISST
    Public Methods: get_file, delete_file, start_collection, stop_collection
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'lisst'
    MAX_FLUSH_TIME = 60 # Will not flush for longer than this. Limited by broker as well.
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(LisstBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # These are default values which are overwritten by [[constants]] in config when load_config
        # is called below
        self.SAMPLE_LATENCY      = 0
        self.FLUSH_TIME          = 5
        self.ZERO_TIME           = 10
        self.ZERO_FLUSH_DELAY    = 3
        self.FILE_TIMEOUT        = 20 #Longer timeout for file transfer.
        self.WATER_LEVEL_MIN     = 0.0
        self.WATER_LEVEL_WARN    = 10.0
        super(LisstBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return
    def get_file(self,lisst_file=None,**kwargs):
        # Process file from lisst data recorder.  Empty lisst_file retrieves most recent.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='get_file'): return {}
        self._json_id += 1
        self.logger.debug('Downloading LISST file')
        if lisst_file is None:
            params = None
        else:
            params = {'lisst_file':lisst_file}
        result = self.socket_handler.send_rpc('get_file',
                                              self._json_id,
                                              timeout=self.FILE_TIMEOUT,
                                              params=params,
                                              debug_mode=debug_mode)
        return self._result_checker(result)
    def delete_file(self,lisst_file,timeout=None,**kwargs):
        # delete file from lisst data recorder.  File name must be given.
        if not self._is_initialized(method_name='delete_file'): return {}
        self._json_id += 1
        result =  self.socket_handler.send_rpc('delete_file',
                                               self._json_id,
                                               timeout=timeout,
                                               params={'lisst_file':lisst_file},
                                               **kwargs)
        return self._result_checker(result)
    def start_collection(self,cast_number,pump_delay=0,timeout=None,**kwargs):
        # start LISST data collection.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='start_collection'): return {}
        self._json_id += 1
        result =  self.socket_handler.send_rpc('start_collection',
                                               self._json_id,
                                               timeout=timeout,
                                               params={"cast_number":cast_number,"pump_delay":pump_delay},
                                              debug_mode=debug_mode)
        return self._result_checker(result)
    def stop_collection(self,timeout=None,**kwargs):
        # stop data collection.
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='stop_collection'): return {}
        self._json_id += 1
        result = self.socket_handler.send_rpc('stop_collection',
                                              self._json_id,
                                              timeout=timeout,
                                              params=None,
                                              debug_mode=debug_mode)
        return self._result_checker(result)
    def is_pumping(self,**kwargs):
        result =  self.get_value(['seawater_pump'],**kwargs)
        return avp_util.t_or_f(result.get('seawater_pump',False))
    def start_pump(self,timeout=None,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        result = self.set({'seawater_pump':True},timeout=timeout,debug_mode=debug_mode)
        return result
    def stop_pump(self,timeout=None,**kwargs):
        debug_mode = kwargs.pop('debug_mode',False)
        result = self.set({'seawater_pump':False},timeout=timeout,debug_mode=debug_mode)
        return result
    def is_flushing(self,**kwargs):
        result = self.get_value(['clean_water_flush'],**kwargs)
        return avp_util.t_or_f(result.get('clean_water_flush',False))
    def flush(self,blocking=False,flush_time=None,**kwargs):
        '''
        Opens and closes flush valve for a set amount of time.
        Arguments:
        FLUSH_TIME - Seconds between opening and closing flush valve.
        blocking - If True, wait for fluch to complete before returning
        '''
        if flush_time is None:
            flush_time = self.FLUSH_TIME
        debug_mode = kwargs.pop('debug_mode',False)
        if blocking:
            result = self._do_flush(flush_time=flush_time,debug_mode=debug_mode)
        else:
            name = "{0}.flush".format(self.BROKER_NAME)
            flush_thread = threading.Thread(target=self._do_flush,
                                            name=name,
                                            kwargs = {'FLUSH_TIME':flush_time,'thread':True,'debug_mode':debug_mode})
            if debug_mode: print("Spawning {0} as {1} with FLUSH_TIME={2}".format(self._do_flush,name,flush_time))
            flush_thread.start()
            result  = {'result':'ok','message':'Flush routine started as a thread','thread':flush_thread}
        return result
    def _do_flush(self,flush_time=None,thread=False,**kwargs):
        '''
        Open flush valve,
        wait flush_time
        close flush valve.
        return dictionary of results
        '''
        if flush_time is None:
            flush_time = self.FLUSH_TIME
        if flush_time > self.MAX_FLUSH_TIME:
            return {'error':'{0} is > MAX_FLUSH_TIME of {1}'.format(flush_time,self.MAX_FLUSH_TIME)}
        result = {}
        self.logger.info("Flushing LISST for {0} seconds".format(flush_time))
        result['flush_on'] = self.__flush_on()
        time.sleep(int(flush_time))
        result['flush_off'] = self._flush_off()
        self.logger.info("LISST flush done.")
        if thread:
            self.logger.info("Flush thread result {0}".format(result))
        else:
            return result
    def __flush_on(self):
        '''
        '''
        return self.set({'clean_water_flush':True})
    def _flush_off(self):
        '''
        '''
        result =  self.set({'clean_water_flush':False})
        # We need to be very sure this is turned off
        if result.get('error',{}).get('code',False) == -31929: # A token error?
            self.get_token(program_name=__name__,
                            calling_obj=self.__class__.__name__,
                            override=True)
            result = self.set({'clean_water_flush':False}) # Try again
        return result
    def zero_sample(self,cast_number,**kwargs):
        '''
        Blocking
        Turns on Starts flush procedure as a thread,
        waits
        Starts sampling
        waits
        stops sampling
        Joins with flush thread
        returns
        '''
        result = {}
        debug_mode = kwargs.pop('debug_mode',False)
        self.logger.debug('LISST zero sample procedure for cast {0}'.format(cast_number))
        result['flush'] = self.flush(blocking=True,flush_time=self.FLUSH_TIME,debug_mode=debug_mode)
        time.sleep(self.ZERO_FLUSH_DELAY) # Give the flush time to start.
        result['start_collection'] = self.start_collection(cast_number=cast_number,pump_delay=0,debug_mode=debug_mode)
        time.sleep(self.ZERO_TIME)
        result['stop_collection'] = self.stop_collection(debug_mode=debug_mode)
        return result
    
class AIOBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the IO board
    Public methods: 
    Instance Variables: broker_name, VOLTAGE_MULTIPLIER
    This broker supports attrubite aliases. In the config['aio']['aliases']
    '''
    BROKER_NAME = 'aio'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode) # Done by parent
        super(AIOBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
        #This allows us to alias parameters with their functions.
        self.param_aliases = self.config[self.BROKER_NAME].get('aliases',{})
        for key,value in list(self.param_aliases.items()):
            this_data_item = getattr(self,value)
            setattr(self,key,this_data_item)
            self.data_points[key] = getattr(self,key)
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # These are default values which are overwritten by [[constants]] in config when load_config
        # is called below
        self.VOLTAGE_MULTIPLIER = 3.089
        self.LOAD_CURRENT_OFFSET = 0.515
        self.CHARGE_CURRENT_OFFSET = 0.4077
        self.LOAD_CURRENT_MULTIPLIER = 7.519
        self.CHARGE_CURRENT_MULTIPLIER = 9.259
        super(AIOBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return


class WindBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the RM Young 32500 wind instrument
    Public Methods: start_collection, stop_collection
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'wind'
    MPS_TO_KNOTS = 1.94384

    def __init__(self, config, **kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode', False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False, debug_mode=debug_mode)
        super(WindBroker, self).__init__(self.config, self.BROKER_NAME, **kwargs)  # Run Superclass __init__
        # super().__init__(self.config, self.BROKER_NAME, **kwargs)  # Run Superclass __init__

    def load_config(self, reload_config=False, **kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.

        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode', False)
        if reload_config is True:
            self.config.reload()
        # These are default values which are overwritten by [[constants]] in config when load_config
        # is called below
        self.COMPASS_TARGET = 0
        self.COMPASS_MARGIN = 90
        super(WindBroker, self).load_config(reload_config=reload_config,
                                              debug_mode=debug_mode)  # Run Superclass load_config
        return

    def start_collection(self, timeout=None, **kwargs):
        # Just testing
        if not self._is_initialized(method_name='start_collection'): return {}
        self._json_id += 1
        start_collection_result = self.socket_handler.send_rpc('startCollection',
                                                               self._json_id,
                                                               timeout=timeout,
                                                               params=None,
                                                               **kwargs)
        return self._result_checker(start_collection_result)

    def stop_collection(self, timeout=None, **kwargs):
        # Just testing...
        if not self._is_initialized(method_name='stop_collection'): return {}
        self._json_id += 1
        stop_collection_result = self.socket_handler.send_rpc('stopCollection',
                                                              self._json_id,
                                                              timeout=timeout,
                                                              params=None,
                                                              **kwargs)
        return self._result_checker(stop_collection_result)



class PowerBroker(_BrokerClient):
    '''
    Adds methods and attributes specific to the micro-controller based power sensor.
    Public Methods: None
    Instance Variables: broker_name
    '''
    BROKER_NAME = 'powermon'
    def __init__(self,config,**kwargs):
        self.config = config
        debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.load_config(reload_config=False,debug_mode=debug_mode)
        super(PowerBroker, self).__init__(self.config,self.BROKER_NAME,**kwargs) # Run Superclass __init__
    def load_config(self,reload_config=False,**kwargs):
        '''
        Set variables based on self.config. Allows changes to avp.ini to be read in.
        
        self.load_config(reload_config=False,debug_mode=debug_mode)
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if reload_config is True:
            self.config.reload()
        # Sounder doesn't have anything to load.
        super(PowerBroker, self).load_config(reload_config=reload_config,debug_mode=debug_mode) # Run Superclass load_config
        return

def null(*doesnt_matter,**ignored): return False

    
def get_date_time(long_time,**kwargs):
    '''
    If the date/time string fractional part is exactly zero it will not be printed.
    This changes the datetime format used below.  Need to verify what will happen given a
    format string with a fractional part and a datetime string with no fractional part.
    '''
    debug_mode = kwargs.get('debug_mode',False)
    result = None
    if long_time:
        try:
            ds = str(long_time)[0:14]
            ts = str(long_time)[14:]
            if ts:
                ms = timedelta(0,0,0,int(ts))
            else:
                ms = timedelta(0)
            result = datetime.strptime(ds, '%Y%m%d%H%M%S').replace(tzinfo=pytz.reference.LocalTimezone()) + ms
        except Exception as e:
            if (debug_mode): print("Error in get_date_time {0} processing {1}".format(e,long_time))
    return result
    
    
def example():
    from configobj import ConfigObj
    config = ConfigObj('./{hostname}_avp.ini'.format(hostname=socket.gethostname())) #This file will have all the needed configuration data
    
    
    # This stuff should be made to work in the background!!!
    logger = logging.getLogger('')
    FORMAT="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=FORMAT)
    dbh = avp_db.DB_LogHandler(config)
    dbh.setLevel(logging.DEBUG)
    logger.addHandler(dbh)   
    
    mm3 = MM3Broker(config) # Instantiate the broker. In this case, the motor controller
    # Subscribe to some values
    mm3.add_subscriptions(['amps','temp_fault'],on_change=True,subscriber="example_code")
    mm3.subscriptions #show subscription values
    print("position is", mm3.value(['position'])) #Update the value of position object and return value
    print(mm3.position.value,mm3.position.units) # This should print out the same thing, since it doesn't generate a status call
    print(mm3.position.sample_time,mm3.position.tz)
    print(mm3.amps.value, mm3.amps.units)
    result = mm3.get_token(program_name='avp_broker',
                                calling_obj='main') # Get the token if we are going to set a value.
    if result.get('acquire_result','') == 'ok':
        mm3.set({'position':0}) #Reset the position counter.
        print(mm3.position.set_to,mm3.position.set_at)
    mm3.unsubscribe_all()
    mm3.disconnect()

