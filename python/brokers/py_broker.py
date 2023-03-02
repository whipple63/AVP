#Built in Modules
from datetime import datetime,timedelta
import json
import logging
from select import select as sselect
import socket
import threading
import time

#Installed Modules

class SocketHandler(threading.Thread):
    '''
    Handles sending jSON strings and awaiting replys via the public send_rpc() method.
    
    Arguments:
        host        -- Host to connect to
        PORT        -- Port to connect to
        rx_rpc      -- Shared list of received JSON-RPC messages (dicts)
        tx_reply    -- Shared list of messages (dict) to be transmitted
        so_timeout  -- Default socket timeout.
        broker_name -- Used for naming thread
    Instance attributes:
        connected   -- Are we connected to broker server
        
    '''
    def __init__(self, host, PORT, rx_rpc, tx_reply, broker_name):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.host = host
        self.PORT = PORT
        self.rx_rpc = rx_rpc
        self.tx_reply = tx_reply
        self.so_timeout = 0
        self.broker_name = broker_name
        self.running = False
        self.connected = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        super(SocketHandler,self).__init__()
        self.name = "{0}.{1}".format(self.broker_name,self.__class__.__name__)
    def send_rpc(self, response, error=False,json_id,timeout=None,**kwargs):
        '''
        
        '''
        debug_mode = kwargs.get('debug_mode',False)
        if not self.connected:
            error_msg = '{0} not connected to broker.'.format(self.name)
            self.logger.error(error_msg)
            return 0
        if error:
            self.msg = {'error':response, 'id':json_id}
        else:
            self.msg = {'result':response, 'id':json_id}
        if debug_mode: print "send_rpc message:{0}".format(self.msg)
        self._send(json.dumps(self.msg))
        return 1
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
        self.running = False
        time.sleep(1)
        self.logger.debug("Shutting down {0:24} {1:2} threads left..".format(self.name,threading.active_count()))
    def start(self):
        address = (self.host,self.PORT)
        # This should be in a try, so if we get "socket.error: [Errno 111] Connection refused" or some other error it is handled.
        try:
            self.socket.connect(address)
        except Exception,e:
            self.logger.debug("{0}.start, connection to {1}, failed ({2}).".format(self.name,address,e))
            self.shutdown()
        self.sf = self.socket.makefile('r')
        self.running = True
        self.connected = True
        super(SocketHandler,self).start() #threading.Thread.start(self)
        self.logger.debug("Started up {0:24} {1:2} active threads.".format(self.name,threading.active_count()))
    def run(self):
        '''
        Listens for JSON messages and puts them into rx_r with their id as the key
        '''
        while(self.running):
            # See ifthere are any messages for us...
            try:
                [item_1, item_2, item_3] = sselect([self.sf],[],[], 1)
                if(len(item_1) > 0):
                    self.jrx = self.sf.readline()[:-1]
                    self.rx = json.loads(self.jrx)
                    self.rxid = self.rx.get("id",-1) 
                    if(self.rxid != -1):
                        self.rx_rpc.append([self.rx])
                    else:
                        pass# What do we do if there is no ID?
                        #self.rx_r.append(self.rx)
            except Exception,e:
                self.running = False
                break
            # Now are there any messages to send 
            if tx_reply:
                for response in tx_reply:
                    self.send_rpc(
        self.connected = False
        self.sf.close()
        self.socket.close()
        
class _MethodHandler(threading.Thread):
    '''
    Monitors rx_rpc and performs the correct actions
    '''
    GENERIC_METHODS = ('status','subscribe','unsubscribe','set','list_data','broker_status')
    def __init__(self, rx_rpc, tx_reply,subscriptions,broker_name,broker_methods={}):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.rx_rpc = rx_rpc
        self.tx_reply = tx_reply
        self.broker_name = broker_name
        self.broker_methods = broker_methods
        self.running = False
        self.connected = False
        super(_MethodHandler,self).__init__()
        self.name = "{0}.{1}".format(self.broker_name,self.__class__.__name__)
        if not self.running:
            self.logger.debug("Socket not connected.")
            return
        try:
            self.socket.send(data)
        except Exception,e:
            self.running = False
            self.logger.debug('{0}.send broker failed ({1}).'.format(self.name,e))
    def shutdown(self):
        self.running = False
        time.sleep(1)
        self.logger.debug("Shutting down {0:24} {1:2} threads left..".format(self.name,threading.active_count()))
    def start(self):
        self.running = True
        self.connected = True
        super(_MethodHandler,self).start() #threading.Thread.start(self)
        self.logger.debug("Started up {0:24} {1:2} active threads.".format(self.name,threading.active_count()))
    def run(self):
        '''
        Parses rx_rpc and responds as required.
        '''
        actionable = {}
        while(self.running):
            if(len(self.rx_rpc) > 0):
                self.n = self.rx_rpc.pop()
                reply = {'result':None,'error':{},'id':-1} # default
                reply['id'] = self.n.get('id',-1) # Reply should have same ID as request
                if self.n.get('method',None) not in self.GENERIC_METHODS:
                    reply['result'],reply['error'] = self.non_generic(self.n)
                else:#This is a generic method
                    method = self.n.get('method')
                    params = self.n.get('params',None)
                    if method is 'status':
                        data = params.get('data',[])
                        style = params.get('style','verbose')
                        reply['result'] = {}
                        # Now results
                        for data_item in data:
                            reply['result'][data_item] = {}
                            reply['result'][data_item]['value'] = 'Value'
                            if style == 'verbose':
                                reply['result'][data_item]['units'] = 'Units'
                                reply['result'][data_item]['sample_time'] = datetime.strptime(datetime.now(), '%Y%m%d%H%M%S000').replace(tzinfo=pytz.reference.LocalTimezone())
                    elif method is 'subscribe':
                        data = params.get('data',[])
                        style = params.get('style','verbose')
                        updates = params.get('updates','on_new')
                        max_update_ms = params.get('max_update_ms',None)
                        min_update_ms = params.get('min_update_ms',None)
                    elif method is 'unsubscribe':
                        pass
                    elif method is 'set':
                        pass
                    elif method is 'list_data':
                        pass
                    elif method is 'broker_status':
                        pass
                    # See if we have anything to send
                if reply['id'] > 0:
                    tx_reply.append(reply)
            else:
                time.sleep(self.SLEEP_TIME)
    def non_generic(self,json_message):
        result = None
        error = {}
        method = json_message.get('method',None)
        if method in self.broker_methods:
            params = json_message.get('params',None)
            try:
                result = self.broker_methods[method](params)
            except Exception,e:
                error['message'] = e
                error['code'] = 1
        else:
            error['message'] = "No action for method {0}".format(method)
            error['code'] = 2
        return result,error
if __name__ = '__main__':
    host = 'localhost'
    port = 3431
    rx_rpc = []
    tx_reply = []
    subscriptions = {}
    socket_handler = SocketHandler(host, PORT, rx_rpc, tx_reply,broker_name="TESTING")
    method_handler = _MethodHandler(rx_rpc, tx_reply,subscriptions,broker_name="TESTING")
    socket_handler.start()
    method_handler.start()