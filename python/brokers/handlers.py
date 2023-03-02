#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        handlers.py
# Purpose:     Contains classes which brokers use to handle sockets and subscriptions
#              Examples:
#
# Author:      neve
#
# Created:     03/15/2013
#-------------------------------------------------------------------------------
#Built in Modules
import json
import logging
from select import select as sselect
import socket
import threading
import time
#Installed Modules
#Custom Modules
import avp_util

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
        debug_mode = kwargs.pop('debug_mode',False)
        if not self.connected:
            error_msg = 'Not connected to broker.'
            self.logger.error(error_msg)
            return {'error':{'message':error_msg,'code':0}}
        self.msg = {'method':method, 'id':json_id}
        if timeout == None:
            timeout=self.so_timeout
        if params:
            self.msg['params'] = params
        if debug_mode: print "send_rpc message:{0}".format(self.msg)
        self._send(json.dumps(self.msg))
        result = self._get_reply(json_id,timeout)
        return result
    def _get_reply(self,json_id,timeout):
        self.endtime = time.time() + int(timeout)
        while time.time() < self.endtime: 
            if json_id in self._rx_r:
                return self._rx_r.pop(json_id)
            try:
                [read_list, write_list, exception_list] = sselect([self.sf],[],[], 0.1)
            except (AttributeError,) as e:
                # This can happen if a broker is killed while awaiting a response
                break
        error_msg = 'Response from {0} timed out after {1} ({2},{3}). Request was {4}'.format(
                        self.address,timeout,self.name,json_id,self.msg)
        self.logger.error(error_msg)
        return {'error':{'message':error_msg,'code':0}}
    def _send(self, data):
        if not self.running:
            self.logger.debug("Socket not connected.")
            return
        try:
            self.socket.send(data)
        except Exception,e:
            self.running = False
            self.logger.debug('{0}.send broker failed ({1}).'.format(self.name,e))
    def shutdown(self):
        if self.running is True:
            self.running = False
            time.sleep(1) # Give main thread time to stop
            self.logger.debug("Shutting down {0:2} threads left.".format(threading.active_count()))
            try:
                self.sf.close()
            except AttributeError,e:
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
                        jrx = self.sf.readline()[:-1]
                        rx = json.loads(jrx)
                        rxid = rx.get("id",-1)
                        if(rxid != -1):
                            self._rx_r[rxid] = rx
                        else:
                            self._rx_n.append(rx)
                except (ValueError,) as e:
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
            self.sf = self.socket.makefile('r')
            self.connected = True
            if self.connect_tries > 1:
                self.logger.debug("{0}.start_connection re-connected to {1}.".format(self.name,self.address))
            else:
                self.logger.debug("{0}.start_connection connected to {1}.".format(self.name,self.address))
            self.connect_tries = 0
        except Exception,e:
            print "ERROR",e
            if self.connect_tries == 1 or self.connect_tries % 60 == 0:
                self.logger.info("in start_connection(), connection to {0}, failed ({1}).".format(self.address,e))
            time.sleep(1)
    def is_connected(self):
        return self.connected

class SubscriptionHandler(threading.Thread):
    '''
    Manages subscribed parameters.
    
    This class monitors rx_n for subscription replies, and when they match with items in the
    subscriptions dictionary, the associated _data_item is updated.
    If there is a key match in callbacks, the associated callback function is spawned as a thread.
    Parameters:
        rx_n          -- Shared(?) list of replies from _socket_handler
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
        while(self.running):
            if(len(self._rx_n) == 0):
                time.sleep(self.SLEEP_TIME)
            else:
                self.n = self._rx_n.pop(0) # This 0 is important to make this a FIFO not a LIFO
                if(self.n.get('method') == 'subscription'): #This is a subscription message
                    #print self.n
                    params = self.n.get('params')
                    # Since per-parameter timestamps have not been implemented, we need to give all the parameters the same time_stamep
                    timedict = params.pop('sample_time')
                    sample_time_long = timedict.get('value')
                    tz = timedict.get('units',None) # Only in verbose mode.
                    sample_time = get_date_time(sample_time_long)
                    for key_name in params.keys(): # process each data_item (key)
                        if key_name in self.subscriptions: #This gets rid of an error when we unsubscribe
                            if 'value' in params[key_name]:
                                # Some brokers (lisst,isco) return 'true'|'false' instead of True|False
                                if self.subscriptions[key_name]._units.lower() == 'boolean':
                                    params[key_name]['value'] = avp_util.t_or_f(params[key_name]['value'],debug_mode=False) 
                                self.subscriptions[key_name]._value = params[key_name]['value'] # Use _value, NOT value
                                self.subscriptions[key_name]._sample_time_long = sample_time_long
                                self.subscriptions[key_name]._sample_time = sample_time
                                if tz is not None:
                                    self.subscriptions[key_name]._tz = tz # This should never change once set
                                if key_name in self.callbacks:
                                    # check this key_name for a callback, and if so call it
                                    # arguments will be the sample_time and the subscription value
                                    cbt = threading.Thread(target=self.callbacks[key_name], args=(sample_time,
                                        self.subscriptions[key_name]) )
                                    cbt.setName("callback.{0}".format(key_name))
                                    cbt.start()
                            else:
                                # We occasionally get something with no 'value', so ignore it
                                self.logger.debug("JSON string {pk} has no item 'value'({k})".format(
                                                    pk=params[key_name],k=key_name))
                        else:
                            self.logger.debug("Parameter {k} subscribed but not in {bn}.subscriptions dictionary.".format(
                                                k=key_name, bn=self.broker_name))
                    if 'sample_time' in self.subscriptions: # This is for keeping track of the last subscription update's time
                        try:
                            self.subscriptions['sample_time']._value = sample_time_long
                            self.subscriptions['sample_time']._sample_time = sample_time
                            if tz:
                                self.subscriptions['sample_time']._tz = tz # This should never change once set
                        except Exception,e:
                            self.logger.error("{0}, unable to parse sample_time from {1}".format(e,self.subscriptions))

def get_date_time(long_time,**kwargs):
    '''
    If the date/time string fractional part is exactly zero it will not be printed.
    This changes the datetime format used below.  Need to verify what will happen given a
    format string with a fractional part and a datetime string with no fractional part.
    '''
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
        except Exception,e:
            print "Error in get_date_time {0}".format(e)
    return result
    