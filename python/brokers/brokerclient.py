#! /usr/bin/env python
#-------------------------------------------------------------------------------
# Name:        brokerclient.py
# Purpose:     Contains base classes for instrument broker clients
#              Examples:
#
# Author:      neve
#
# Created:     03/15/2013
#-------------------------------------------------------------------------------

#Built in Modules
from datetime import datetime,timedelta
import logging
import socket
import time
#Installed Modules
import pytz.reference
#Custom Modules
import avp_util
from brokers import SocketHandler,SubscriptionHandler,get_date_time




class BrokerClient(object):
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
        if debug_mode: print "{0} broker in debug_mode".format(broker_name)
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
            result['_structure_data'] = self._structure_data(**kwargs)
            # Now aliases if there are any
            if result['_structure_data'] > 0:
                #This allows us to alias parameters with their functions.
                self.logger.debug("Added {0} parameters to data structure.".format(result['_structure_data']))
                self.param_aliases = self.config.get(self.BROKER_NAME,{}).get('aliases',{})
                for key,value in self.param_aliases.items():
                    this_data_item = getattr(self,value)
                    setattr(self,key,this_data_item)
                    self.data_points[key] = getattr(self,key)
                    if debug_mode: print "Aliasing {0} to {1}".format(key,value)
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
        self.SOCKET_TIMEOUT = int(self.config.get('broker',{}).get('SOCKET_TIMEOUT',5))
        self.RESUME_TIMEOUT = int(self.config.get('broker',{}).get('RESUME_TIMEOUT',50))
        self.STALE_TIME = int(self.config.get('broker',{}).get('STALE_TIME',10))
        self.host = avp_util.check_hostname(host,broker_name=self.BROKER_NAME,debug_mode=debug_mode)
        if reload_config is True:
            self.logger.debug('Re-loaded {0} for {1} broker'.format(self.config.filename,self.BROKER_NAME))
        # Set up broker constants
        try:
            self.constants = self.config.get(self.BROKER_NAME,{}).get('constants',{})
            if debug_mode is True:
                print "{b} constants are {c}".format(b=self.BROKER_NAME,c=self.constants)
            for constant,value in self.constants.items():
                try:
                    if '.' in value: # Crude way of checking if it is a float
                        setattr(self,constant,float(value))
                    else:
                        setattr(self,constant,int(value))
                except ValueError:
                    # It is probably a string
                    setattr(self,constant,value)
        except KeyError:
            if debug_mode is True:
                print "{b} doesn't have [[constants]]".format(b=self.BROKER_NAME)
            pass
        return
    def connect_to_broker(self,**kwargs):
        '''
        Creates SocketHandler and SubscriptionHandler objects.
        Starts SocketHandler thread
        Calls initialize_data which creates objects based on list_data reply from broker.
        Args: None
        Kwargs: None
        Returns:
            bool.   If all actions were successful.
        Raises:
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if self.connected() == False:
            try:
                self.socket_handler = SocketHandler(self.host, self.PORT, self._rx_r, self._rx_n,
                    self.SOCKET_TIMEOUT,broker_name=self.BROKER_NAME,debug_mode=debug_mode)
                self.connected = self.socket_handler.is_connected
            except Exception,e:
                self.logger.error("Could not create SocketHandler: {0}".format(e))
            try:
                self.sub_handler = SubscriptionHandler(self._rx_n, self.subscriptions, 
                                                        self.callbacks,broker_name=self.BROKER_NAME,
                                                        debug_mode=debug_mode)
            except Exception,e:
                self.logger.error("Could not create SubscriptionHandler: {0}".format(e))
            try:
                self.socket_handler.start()
            except Exception,e:
                self.logger.error("Could not start SocketHandler: {0}".format(e))
            '''
            try:
                self.sub_handler.start()
            except Exception,e:
                self.logger.error("Could not start SubscriptionHandler: {0}".format(e))
            '''
        
        return self.connected()
    def disconnect(self,**kwargs):
        '''
        Releases token and shuts down SocketHandler and SubscriptionHandler
        Args: None
        Kwargs:
            debug_mode(bool):   Print extra debugging messages defaults to False
        Returns:
        Raises:
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if self.token_acquired is True:
            self.tokenRelease(**kwargs)
        # Should we unsubscribe to everything?
        self.sub_handler.shutdown()
        self.socket_handler.shutdown()
        self.connected = null
    def _is_initialized(self,method_name='unknown',**kwargs):
        '''
        Releases token and shuts down SocketHandler and SubscriptionHandler
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
            print "Structuring data: parameters for {0} are {1}".format(self.BROKER_NAME,data_list)
        added_parameters = 0
        try:
            for data_name in data_list:
                data_type = data_units = ''
                try:
                    data_dict = data_list.get(data_name)
                    data_type = data_dict.get('type') #Can be ('RW', 'RO', 'WO', or 'NI' (Not Implemented))
                    data_units = data_dict.get('units')
                except Exception,e:
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
                    self.logger.info("ot adding {0} of unknown type {1}".format(data_name,data_type)) 
            self.initialized = True
        except Exception,e:
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
        result = {'result':'unknown'}
        bad_results = ['java.lang.NullPointerException',
            'java.lang.ClassCastException: java.sql.Timestamp cannot be cast to java.lang.String',
            'java.lang.NullPointerException']
        # make sure it's a dictionary!
        if not raw_result:
            if debug_mode: print "raw_result=None"
            raw_result = {'error':{'message':'empty string','code':0}}
        if raw_result.__class__ != {}.__class__:
            if debug_mode: print "{0} not a dictionary, it is a {1}".format(raw_result,raw_result.__class__)
            self.logger.debug("Error in _result_checker, result {0} is not a dictionary".format(raw_result))
            raw_result = {'error':{'message':'Returned object {0} not a dictionary'.format(raw_result),'code':0}}
        raw_result.pop('id',None)
        # Now process what we have
        if raw_result.get('error'):
            if debug_mode: print "error result"
            result = raw_result
        elif raw_result.get('result') in bad_results:
            if debug_mode: print "Result was some sort of JAVA error"
            result = {'error':{'message':raw_result.get('result'),'code':0}}
        elif raw_result.get('result') == 'ok':
            if debug_mode: print "ok result"
            result = {'result':'ok'}
        else:
            #At this point we may have:
            #    {'result':<message>}    --> no change
            #    {'result':{<results}}   --> {results}
            try:
                temp_result = raw_result.get('result')
                if temp_result.__class__ == {}.__class__:
                    if debug_mode: print "result is a dictionary"
                    result = temp_result
                else:
                    if debug_mode:
                        print "result {tr} is NOT a dictionary, it is a {trc}".format(
                                tr=temp_result,trc=temp_result.__class__)
                    result = raw_result
            except Exception, e:
                result = {'error':{'message':'unknown error on:{0}'.format(raw_result),'code':0}}
            if debug_mode: print "final result={0}".format(result)
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
        sample_time = sample_time_long = sample_tz = None
        if verbose:
            style = 'verbose'
        else:
            style = 'terse'
        status_params = {'data':data_items,'style':style}
        status_dict = {}
        status_result = {}
        self._json_id += 1
        if debug_mode:
            print "send_rpc 'status' {0} {1}".format(status_params,str(datetime.now(pytz.reference.LocalTimezone())))
        status_dict = self.socket_handler.send_rpc(method='status',
                                                   json_id=self._json_id,
                                                   timeout=timeout,
                                                   params=status_params,
                                                   debug_mode=debug_mode)
        if debug_mode:
            print "     send_rpc result: {sd}{now}".format(
                    sd=status_dict,now=str(datetime.now(pytz.reference.LocalTimezone())))
        if not status_dict.__class__ == {}.__class__: #if it looks like the correct sort of thing, update the _DataItems
            self.logger.error("Error in {bn}._status, 'status' request of {sp} returned {sd}".format(
                                bn=self.BROKER_NAME,sp=status_params,sd=status_dict))
            status_dict = {'error':{'message':'type error in _BrokerObject._status','code':0}}
        if 'error' in status_dict:
            return status_dict
        try:
            status_result = status_dict.get('result')
        except Exception,e:
            self.logger.error("Error in _status get('result') {e}\r\n status_dict={sd}\r\n status_params={sp}".format(
                                e=e,sd=status_dict,sp=status_params) )
        try:
            if isinstance(status_result,dict): # message had a dictionary result
                timedict = status_result.pop('sample_time',None)
                if 'sample_time' in data_items:
                    data_items.remove('sample_time')
                if timedict != None:
                    sample_time_long = timedict.get('value',None)
                    sample_tz = timedict.get('units',None) # Only in verbose mode.
                    sample_time = get_date_time(sample_time_long)
                for requested_item in data_items:
                    this_object = getattr(self,requested_item)
                    this_param  = status_result.get(requested_item)
                    this_units = this_param.get('units',None)
                    this_value = this_param.get('value',None)
                    if this_value != None:
                        # Brokers will return double precision float minimum value when they don't have a real value...
                        if this_value <= self.MINIMUM_VALUE and this_value > 0: 
                            this_value = None # So set it to None
                        if this_object._units == 'boolean':
                            this_value = avp_util.t_or_f(this_value,**kwargs)
                        setattr(this_object,"_value",this_value)
                        if this_units != None:
                            setattr(this_object,"_units",this_units)
                        if sample_time_long != None:
                            setattr(this_object,"_sample_time_long",sample_time_long)
                            setattr(this_object,"_sample_time",sample_time)
                        if sample_tz != None:
                            setattr(this_object,"_tz",sample_tz)
            else:
                # We didn't get a dictionary, sometimes we get a {'result':'java.lang.NullPointerException'}
                return {'error':{'message':status_result,'code':0}}
        except Exception,e:
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
        if debug_mode: print "Looking up values for {0}".format(data_item_names)
        # Check if data_item_names is a list
        if not isinstance(data_item_names,(list,tuple)):
            error_str = "Error in get_value. Method takes a list or tuple as an argument, not {din} of {tdin}".format(
                            din=data_item_names,tdin=type(data_item_names))
            self.logger.error(error_str)
            return {'error':{'message':error_str,'code':0}}
        data_item_names = list(data_item_names) # Need to change to list so we can change values in place.
        # Check data_item_names for existance and aliases
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
                except Exception, e:
                    self.logger.error(
                        "Exception in g{0}.get_value: {1}. data_item_names = {2}. status_return = {3}".format(
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
    def _subscribe(self,params_list,on_change=True,min_interval=None,max_interval=None,verbose=False,timeout=None,**kwargs):
        '''
        Takes a list or tuple of parameters to subscribe to.
        Checks to make sure they are valid.
        '''
        debug_mode = kwargs.pop('debug_mode',False)
        if not self._is_initialized(method_name='_subscribe'): return {}
        # Check if params_list is a list
        if not isinstance(params_list,(list,tuple)):
            self.logger.error("Error, _BrokerClient._subscribe(params_list) method takes a list or tuple as an argument, not {0}".format(type(data_item_names)) )
            return 0
        if len(params_list) == 0:
            self.logger.debug("Subscrition list is empty")
            return 0
        params_list.append('sample_time')
        checked_data_item_names = []
        for parameter in params_list:
            if hasattr(self,parameter):
                this_data_item = getattr(self,parameter)    # This is to take care of aliases
                data_name = this_data_item.data_name        # data_name is what the broker recognizes
                if (parameter or data_name) not in self.subscriptions:
                    if self.sub_handler.running is False:
                        try:
                            self.sub_handler.start()
                        except Exception,e:
                            self.logger.error("Could not start SubscriptionHandler: {0}".format(e))
                    checked_data_item_names.append(data_name)
                    self.subscriptions[parameter] = this_data_item # Might be an alias, or just doing the same thing twice
                    self.subscriptions[data_name] = this_data_item
                    setattr(this_data_item,'_subscribed',True)
                    if debug_mode: print "Subscribing to {0}".format(data_name)
                else:
                    if debug_mode: self.logger.debug( "Already subscribed to {0}.{1}".format(self.BROKER_NAME,parameter) )
            else:
                self.logger.error( "Broker object {0} has no parameter '{1}'".format(self.BROKER_NAME,parameter) )
        try:
            checked_data_item_names.remove('sample_time')
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
        # If there is a problem here, we cold end up in an odd state
        return self._result_checker(subscribe_result)
    def subscribe(self,params_list,**kwargs):
        '''
        This method is depricated. Please use add_subscriptions() instead.
        '''
        self.logger.warning("{0}.subscribe() is depricated, use {0}.add_subscriptions()".format(self.BROKER_NAME))
        return self._subscribe(params_list,**kwargs)
    def add_subscriptions(self,params_list,subscriber='unknown',on_change=True,min_interval=None,max_interval=None,verbose=False,timeout=None,**kwargs):
        '''
        This will abstract the subscription process and may add more functionality later.
        May want to keep a list of who has subscribed, so if two subscribe and one unsubscribes, the subscription will remain.
        '''
        params_list = list(params_list) # Convert tuples to list...
        debug_mode = kwargs.pop('debug_mode',False)
        return self._subscribe(params_list,on_change=on_change,min_interval=min_interval,
                                max_interval=max_interval,verbose=verbose,timeout=timeout,
                                debug_mode=debug_mode)
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
            checked_params.remove('sample_time')
            self.subscriptions.pop(parameter,None)
            self.sample_time._subscribed = False
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
            if debug_mode: print "Unsubscribe from {0} result: {1}".format(checked_params,result['send_rpc'])
            for parameter in checked_params: # Now remove them from local subscription dictionary.
                this_data_item = getattr(self,parameter)
                self.subscriptions.pop(parameter,None)
                this_data_item._subscribed = False
            if 'error' in result['unsubscribe']:
                self.logger.error( "Unsubscribe error: {0}".format(result['unsubscribe']) )
        if len(self.subscriptions) == 0:
            self.sub_handler.shutdown()
        elif self.subscriptions.keys() == ['sample_time']:
            result['unsubscribe'] = self.unsubscribe(self.subscriptions.keys()) # A little recursive
        elif debug_mode:
            print "Remaining subscriptions {0}".format(self.subscriptions.keys())
        return result
    def unsubscribe_all(self,**kwargs):
        ''' Unsubscribe to all keys in subscription dictionary and remove all callbacks
        '''
        if len(self.subscriptions.keys()) > 0:
            self.logger.debug( "{0} UNSUBSCRIBING {1}".format(self.BROKER_NAME,self.subscriptions.keys()) )
            result =  self.unsubscribe(self.subscriptions.keys(),**kwargs) # This may include aliases, but no matter.
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
            if self.callbacks.has_key(key):
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
        for (data_item_name,desired_value) in params.items():
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
                print "     {now} {bn}.{c}.send_rpc() starting".format(
                    now=str(datetime.now(pytz.reference.LocalTimezone())),
                    bn=self.BROKER_NAME, c=command)
            if write_store: checked_params['write_store'] = True
            try:
                self._json_id = self._json_id + 1
                set_result = self.socket_handler.send_rpc('set',
                                                          self._json_id,
                                                          timeout=timeout,
                                                          params=checked_params,
                                                          debug_mode=debug_mode)
                if debug_mode: 
                    print "     {now} send_rpc {c} {cp} Result:{sr}".format(sr=set_result,
                            now=str(datetime.now(pytz.reference.LocalTimezone())),
                            cp=checked_params,c=command)
                result =  self._result_checker(set_result)
            except Exception,e:
                message = "Error {e} in _BrokerObject.socket_handler send_rpc({c},{ji},{cp})) failed".format(
                            ji=self._json_id,cp=checked_params,e=e,c=command)
                result = {'error':{'message':message,'code':0}}
        else:
            if debug_mode: print "No valid parameters in {0}".format(params.items())
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
        return self._result_checker(result)
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
                                              **kwargs)
        if debug_mode: print "{0}._token_acquire for {1} result: {2}".format(self.BROKER_NAME,name,result)
        acquire_result = self._result_checker(result)
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
        if debug_mode: print "_token_force_acquire for {0} result: {1}".format(name,_token_force_acquire_result)
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
        if debug_mode: print "tokenRelease result: {0}".format(tokenRelease_result)
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
            print "owner_result result: {0}".format(owner_result)
            print "tokenOwner result: {0}".format(tokenOwner_result)
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
                if debug_mode: print "Acquiring token from {0} for {1}".format(token_owner,token_name)
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
            print result.get('acquire_result')
            self.logger.error("Unknown response in {0}.get_token: {1}",format(
                                self.BROKER_NAME,result.get('acquire_result')))
        if debug_mode: print "get_token result:{0}".format(result)
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
        if debug_mode: print "resume_result ={0}".format(resume_result)
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
        tz                  --  Time Zone for sample_time
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

def null(*doesnt_matter,**ignored):
    return False
    
