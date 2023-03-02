#! /usr/bin/env python
#Built in Modules
from __future__ import print_function
import cmd
from datetime import datetime, timedelta
import logging
from select import select as sselect
import socket
import sys
from telnetlib import Telnet
import termios
import tty
import time
#Installed Modules
import pytz.reference
#Custom Modules
import avp_broker
import avp_cast
import avp_db
from avp_sched import AVPScheduleStatus
import avp_util
from avp_winch import Winch
import gislib


CR = '\n'

class _BaseConsole(cmd.Cmd):
    '''
    Always instantiated as a parent class.
    These are commands common to all consoles.
    self.obj is the device object of the child class
    '''
    program_name='avp_console' # Class attribute
    def __init__(self,context,console_name='UnknownConsole',obj=False,other_obj=False,**kwargs):
        self.context = context
        self.console_name = console_name
        self.debug_mode = kwargs.pop('debug_mode',False)
        self.logger = logging.getLogger(self.console_name)
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        if obj:
            self.obj = getattr(context,obj)
        else:
            self.obj = None
        if other_obj is not False:
            setattr(self,other_obj,getattr(context,other_obj))
        cmd.Cmd.__init__(self)
    def do_debug(self,args):
        if self.debug_mode:
            self.debug_mode = False
            print("debug mode off")
            if self.prompt.startswith('DB-'):
                self.prompt = self.prompt[3:]
        else:
            self.debug_mode = True
            print("debug mode on")
            if not self.prompt.startswith('DB-'):
                self.prompt = 'DB-{0}'.format(self.prompt)
    def help_debug(self): print("togles debug mode")
    def help_exit(self): print("Exits from sub menu, or if in main menu, exits from console.")
    def do_exit(self,args):
        return -1
    def help_quit(self): self.help_exit
    def preloop(self):
        """Initialization before prompting user for commands.
           Despite the claims in the Cmd documentaion, Cmd.preloop() is not a stub.
        """
        cmd.Cmd.preloop(self)   ## sets up command completion
        self._hist    = []      ## No history yet
        self._locals  = {}      ## Initialize execution namespace for user
        self._globals = {}
    def precmd(self, line):
        """ This method is called after the line has been input but before
            it has been interpreted. If you want to modifdy the input line
            before execution (for example, variable substitution) do it here.
        """
        cmd = line.strip()
        if cmd:
            self._hist += [ line.strip() ]
        return line
    def default(self,args):
        print("?")
    def emptyline(self):
        pass
    def help_hist(self):
        print("Print a list of commands that have been entered")
    def do_hist(self,args):
        print(self._hist)
    # Aliases and their help
    do_quit = do_exit
    do_x = do_exit
    do_hi = do_hist
    
class _BrokerConsole(_BaseConsole):
    ''' This class contains the methods typically common to most brokers.
    '''
    def __init__(self,context,console_name='UnknownConsole',obj=False,other_obj=False,consoles={},**kwargs):
        _BaseConsole.__init__(self,context,console_name=console_name,obj=obj,
                                other_obj=other_obj,**kwargs)
        self.consoles = consoles
    def do_aio(self,args):
        self.other_console('aio',args)
    def help_aio(self):
        print("Issue a command to the aio console.")
    def do_powermon(self,args):
        self.other_console('powermon',args)
    def help_powermon(self):
        print("Issue a command to the power monitor console if it has been initialized.")
    def do_sonde(self,args):
        self.other_console('sonde',args)
    def help_sonde(self):
        print("Issue a command to the sonde console if it has been initialized.")
    def do_sounder(self,args):
        self.other_console('sounder',args)
    def help_sounder(self):
        print("Issue a command to the sounder console if it has been initialized.")
    def do_winch(self,args):
        self.other_console('mm3',args)
    def help_winch(self):
        print("Issue a command to the winch console if it has been initialized.")
    def do_wind(self,args):
        self.other_console('wind',args)
    def help_wind(self):
        print("Issue a command to the wind console if it has been initialized.")
    def do_isco(self,args):
        self.other_console('isco',args)
    def help_isco(self):
        print("Issue a command to the isco console if it has been initialized.")
    def do_lisst(self,args):
        self.other_console('lisst',args)
    def help_lisst(self):
        print("Issue a command to the lisst console if it has been initialized.")
    def other_console(self,console_name,args):
        try:
            sub_console = self.consoles.get(console_name,{}).get('console_obj',None)
            if sub_console is None:
                print("{0} console not initialized yet".format(console_name))
            else:
                sub_console.onecmd(args)
        except Exception as e:
            print("Unable to issue command {0} to {1} console:{2}".format(args,console_name,e))
    def do_sock(self,args):
        try:
            if ( len(args.split()) == 0):
                print("Usage: sock [off|on]")
            elif (args.split()[0] == "on"):
                self.obj.socket_handler.debug_mode = True
            elif (args.split()[0] == "off"):
                self.obj.socket_handler.debug_mode = False
            print("{0} RPC socket debug_mode is {1}".format(self.console_name,self.obj.socket_handler.debug_mode))
        except Exception as e:
            print(e)
    def help_sock(self):
        print("Turns printing of lowest level socket messages on")
        print("Usage: sock [on]")
    def help_report(self):
        print("Like para, but requests all values and prints them IN THE FORMAT THEY ARE RECIEVED.")
        print("    To se the values as they are in memory, use 'mem all'.")
    def do_report(self,args):
        print(self.report(para_only=False))
    def report(self,para_only=True):
        result = {}
        result['list_data'] = self.obj.list_data(debug_mode=self.debug_mode)
        if result['list_data'].get('error',False):
            print("Error: {0} code:{1}".format(result['list_data'].get('error').get('message'),result['list_data'].get('error').get('code')))
            return
        if self.debug_mode: print("list_data result: {0}".format(result['list_data']))
        try:
            max_para_length = max(len(k) for k in list(result['list_data'].keys())) + 1
        except Exception as e:
            print("Error {0}: unexpected list_data() result, {1}".format(e,result['list_data']))
            max_para_length = 20
            result['list_data'] = list(result['list_data'])
        return_list = []
        subscribed = ''
        if para_only:
            value_label = ' '
            value_width = 1
            timestamp_label = ' '
            timestamp_width = 1
            tz_width = 1
            result['current_values'] = {}
        else:
            value_label = 'VALUE'
            timestamp_label = 'SAMPLE_TIME'
            value_width = 10
            timestamp_width = 20
            tz_width = 5
            para_list = []
            for item in result['list_data']: # get rid of anything not yet implemented ('NI' or 'WO').
                if result['list_data'][item].get('type',None) in ('RO','RW'):
                    para_list.append(item)
            try:
                result['current_values'] = self.obj.get_value(para_list,verbose=True,debug_mode=self.debug_mode)
            except Exception as e:
                print("{0}.get_value error in _BaseConsole.report: {1} ({2})".format(self.obj.BROKER_NAME,e,para_list))
                return 0
        return_result = "{0:{1}}{2:{3}}{4:10}{5:5}{6:4}{7:{8}}{9:{10}}".format('PARAMETER', #0
                                                                    max_para_length,
                                                                    value_label,            #2
                                                                    value_width,
                                                                    'UNITS',                #4
                                                                    'TYPE',
                                                                    'SUB',                  #6
                                                                    timestamp_label,
                                                                    timestamp_width,        #8
                                                                    'TZ',
                                                                    tz_width)               #10
        if 'error' in result['current_values']:
            print("Error: {0}".format(result['current_values']))
            return 0
        for item in result['list_data']:
            subscribed = tz = stt = ' '
            if item != 'message_time': # message_time is special and is added at the end.
                this_item = getattr(self.obj,item)
                try:
                    if not para_only:
                        if item in result['current_values']:
                            value_label = str(result['current_values'][item]) + " "
                        else:
                            value_label = ' '
                        if this_item.data_type in ('RO','RW'):
                            if this_item.subscribed: # Just because it is easier to read 'T' & '' than 'T' & 'F'
                                subscribed = 'T'
                            else:
                                subscribed = ' '
                            tz = this_item.tz
                            stt=this_item.sample_time.strftime('%Y-%m-%d %H:%M:%S')
                    return_list.extend(["{cr}{i:<{iw}}{v:<{vw}}{u:10}{dt:5}{s:4}{st:<{stw}}{tz:<{tzw}}".format(
                                    cr=CR,
                                    i=item,
                                    iw=max_para_length,
                                    v=value_label,
                                    vw=value_width,
                                    u=this_item.units,
                                    dt=this_item.data_type,
                                    s=subscribed,
                                    st=stt,
                                    stw=timestamp_width,
                                    tz=this_item.tz,
                                    tzw=tz_width)])
                except Exception as e:
                    print("Exception in report {0}-{1}-{2}".format(e,item,result['list_data']))
                    print("item",item,item.__class__)
                    print("max_para_length",max_para_length, max_para_length.__class__)
                    print("value_label",value_label, value_label.__class__)
                    print("value_width",value_width, value_width.__class__)
                    #print "units",units, units.__class__
                    #print "data_type",data_type, data_type.__class__
                    print("subscribed",subscribed, subscribed.__class__)
                    print("this_sample_time",this_item.sample_time, this_item.sample_time.__class__)
                    print("timestamp_width", timestamp_width,timestamp_width.__class__)
        return_list.sort(key=lambda x: x.lower()) # Sort the
        for i in return_list: # get the list into a string
            return_result += i
        if not para_only: return_result += "\r\nmessage_time is {0} {1}".format(self.obj.message_time.sample_time,self.obj.message_time.units)
        return return_result
    def help_para(self):
        print("Print a list of valid parameters for current system")
        print("    usage: para")
    def do_para(self,args):
        print(self.report(para_only=True))
    def help_token(self):
        print("usage: token [option]")
        print("    options:status  - See who has token")
        print("            acquire|1 - acquire token")
        print("            force|2   - Force acquire token")
        print("            release|0 - Relese control token")
    def do_token(self,args):
        # acq,acquire, rel, release, force
        if not args:
            args = 'status'
        args_l = args.split()
        if len(args_l) > 1:
            print("Too many arguments")
            self.help_token()
            return 1
        elif args_l[0] == 'status':
            result = self.obj.tokenOwner(debug_mode=self.debug_mode)
            if result.get('result',result.get('error','unknown')) != '':
                print("{0} token owned by {1}".format(self.obj.BROKER_NAME,result.get('result',result.get('error','unknown'))))
            else:
                print("{0} token has no owner ({1})".format(self.obj.BROKER_NAME,result.get('result',result.get('error','unknown'))))
        elif args_l[0] in ['acquire','1']:
            result = self.obj.get_token(program_name=self.program_name,
                                        calling_obj=self.__class__.__name__,
                                        override=False,
                                        debug_mode=self.debug_mode)
            if result.get('acquire_result',{}).get('result',None) == 'ok':
                #self.obj.has_token = True
                print("{0} token acquired".format(self.obj.BROKER_NAME))
                if self.debug_mode: print(result)
            else:
                # This should be printed from a lower level by the logger
                #print "{0} token NOT acquired({1})".format(self.obj.BROKER_NAME,result)
                pass
        elif args_l[0] in ['force','2']:
            result = self.obj.get_token(program_name=self.program_name,
                                        calling_obj=self.__class__.__name__,
                                        override=True,
                                        debug_mode=self.debug_mode) 
            if result.get('acquire_result',{}).get('result',None) == 'ok':
                #self.obj.has_token = True
                print("{0} token force acquired".format(self.obj.BROKER_NAME))
                if self.debug_mode: print(result)
            else:
                print("{0} token NOT force acquired({1})".format(self.obj.BROKER_NAME,result))
        elif args_l[0] in ['release','0']:
            result = self.obj.tokenRelease(debug_mode=self.debug_mode)
            if result.get('result') == 'ok':
                #self.obj.has_token = False
                print("{0} token released.".format(self.obj.BROKER_NAME))
                if self.debug_mode: print(result)
            else:
                print("{0} token NOT released({1})".format(self.obj.BROKER_NAME,result))
        else:
            self.help_token()
            return 1
    def do_value(self,args):
        self.value_lookup(args,from_mem=False)
    def do_vvalue(self,args):
        self.value_lookup(args,from_mem=False,verbose=True)
    def value_lookup(self,args,from_mem=False,verbose=False):
        if args == 'all':
            args = ' '.join(list(self.obj.data_points.keys()))
            if not from_mem: print("The 'report' command may produce clearer results.")
        parameter_l = args.split()
        if len(parameter_l) < 1:
            self.help_value()
            return 0
        result = []
        checked_parameters = []
        values_dict = {}
        for item in parameter_l:
            if hasattr(self.obj,item):
                this_item = getattr(self.obj,item)
                if hasattr(this_item,'data_type'):
                    if this_item.data_type in ('RW','RO'):
                        checked_parameters.append(item)
                    else:
                        print("can't get value of {0} of type {1}".format(item,this_item.data_type))
            else:
                print("Broker {0} has no attribute {1} in {2}".format(self.obj.BROKER_NAME,item,dir(self.obj)))
        checked_parameters.sort()
        for param in checked_parameters:
            try:
                this_param = getattr(self.obj,param)
                if from_mem:
                    value = this_param.mem_value
                else:
                    value = this_param.value
                if self.debug_mode: print(value)
                units = this_param.units
                sample_time = this_param.sample_time
                tz = this_param.tz
            except AttributeError as e:
                print("error in {0}: {1} for param {2}".format(self.console_name,e,param))
                sample_time = units = tz = '?'
            source = "{0}.{1}".format(self.obj.BROKER_NAME,param)
            result.append("{0:25} = {1:15} {2:10} @ {3} {4}{cr}".format(source,str(value),units,sample_time,tz,cr=CR))
        print(''.join(result))
    def help_value(self):
        print("Given one or more parameters returns a list of values.")
        print("    usage: value <all>|<parameter_1 [parameter_2] [parameter_N]>")
        print("    example: value depth_m sal_ppt")
    def help_set(self):
        print("Set a value directly. Use caution")
        print("     usage: set <parameter> <value>")
    def do_set(self,args,write_store=False):
        ''' Parse the input and pass it to set_value
        '''
        args_l = args.split()
        if len(args_l) != 2:
            self.help_set()
            return
        else:
            param = args_l[0]
            value = args_l[1]
        result = self.set_value(param=param,value=value,write_store=write_store)
        print("set result:{0}".format(result))
    def set_value(self,param,value,write_store=False):
        params = {param:value}
        # Put a try here?
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            return "Unable to get token, aborting."
        # Should check if we got the token
        result =  self.obj.set(params,write_store=write_store,debug_mode=self.debug_mode)
        self.do_token('release')
        return result
    def help_init(self): print("Re-initialize {0} client".format(self.obj.BROKER_NAME))
    def do_init(self,args):
        if self.debug_mode: print("Shutting down {0}...".format(self.obj.BROKER_NAME, end=' '))
        self.context.shutdown(self.obj.BROKER_NAME)
        time.sleep(2)
        if self.debug_mode: print("Starting up {0}...".format(self.obj.BROKER_NAME))
        self.context.startup(self.obj.BROKER_NAME)
    def help_sub(self):
        print("Subscribe to parameters. If no parameters are given, it lists current subscriptions.")
        print("    Subscribing to 'all' will subscribe to every readable parameter.")
        print("     usage: sub [parameter_1 [parameter_2 ...[parameter_N]]]|[all] ")
    def do_sub(self,args):
        parameters = args.split()
        if len(parameters) == 0:
            print("{0} Subscription List:".format(self.obj.BROKER_NAME))
            print(list(self.obj.subscriptions.keys()))
        else:
            if args == 'all':
                parameters = []
                if self.debug_mode: print(self.obj.data_points)
                for this_obj in list(self.obj.data_points.values()):
                    if self.debug_mode: print(this_obj)
                    if hasattr(this_obj,'data_type'):
                        if this_obj.data_type in ('RW','RO'):
                            parameters.append(this_obj.data_name)
                print("Adding subscriptions: {0}".format(parameters))
            result =  self.obj.add_subscriptions(parameters,on_change=True,subscriber=self.console_name,debug_mode=self.debug_mode)
            print(result)
    def help_unsub(self):
        print("Unsubscribe to parameters. if 'all' is given as the first parameter, all values will be unsubscribed.")
        print("     usage: unsub <all>|<parameter_1 [parameter_2 ...[parameter_N]]> ")
    def do_unsub(self,args):
        parameters = args.split() # convert to list
        if len(parameters) < 1:
            self.help_unsub()
        else:
            if args == 'all':
                print("{0}: Unsubscribing from everything".format(self.obj.BROKER_NAME))
                print(self.obj.unsubscribe_all(debug_mode=self.debug_mode))
            else:
                print("{0}: Unsubscribing from: {1}".format(self.obj.BROKER_NAME,args))
                print(list(self.obj.unsubscribe(parameters,debug_mode=self.debug_mode).keys()))
    def help_console(self): # Help for direct_connect()
        print("Connect directly to instrument via telnet. Only available from certain sub-menus")
    def direct_connect(self,eol=None,mode='RO'):
        '''
        eol is either '\x0a' or '\x0d\x0a'
        '''
        sends_CR = False
        CR = '\x0d'
        LF = '\x0a'
        CRLF = CR + LF
        GS = '\x1d'
        if eol is None:
            eol = LF
        try:
            console_port = self.obj.config[self.obj.BROKER_NAME]['INSTRUMENT_PORT']
        except KeyError as e:
            print("Error: {0}".format(e))
            return
        print(("Connecting to {0} on port {1}".format(self.obj.BROKER_NAME,console_port)))
        print("Press ctrl-] then enter to exit telnet mode")
        telnet_session = Telnet(host='localhost',port=console_port,timeout=10)
        # need to be in character more, and probably set the CRLF
        telnet_running = True
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            while telnet_running:
                if mode == 'RO':
                    read_list, write_list, except_list = sselect([telnet_session, sys.stdin], [], [])
                elif mode == 'RW':
                    read_list, write_list, except_list = sselect([telnet_session, sys.stdin], [telnet_session], [])
                if telnet_session in read_list:
                    try:
                        text = telnet_session.read_eager()
                    except EOFError:
                        print('*** Connection closed by remote host ***')
                        break
                    if text:
                        sys.stdout.write(text)
                        sys.stdout.flush()
                if sys.stdin in read_list:
                    char = sys.stdin.read(1)
                    '''
                    if char == '\x0d': # We got a LF
                        if eol == '\x0a': # No CR if eol is LF only
                            continue
                        if eol == '\x0d\x0a': # need to chage LF into eol
                            char = eol
                    '''
                    if char == CR and sends_CR is False:
                        sends_CR = True
                    if sends_CR is True and char == CR and eol == LF:
                        char = eol # Change a CR into a LF
                    elif sends_CR is False and char == LF and eol == CRLF: # We don't usually send a CR, but need to
                        char = eol
                    if char == GS: # ctrl-]
                        telnet_running = False
                        break 
                    if not char: break
                    if mode is 'RW':
                        telnet_session.write(char)
        finally:
            print("Closing telnet connection")
            telnet_session.close()
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    def help_mem(self):
        print("Get value(s) without making call to broker i.e. see value in memory.")
        print("    usage: mem <parameter_1 [parameter_2] [parameter_N]>")
        print("    example: mem depth_m sal_ppt")
        print("    if no argument is given, all values will be returned")
    def do_mem(self,args='all'):
        return self.value_lookup(args,from_mem=True)
    def help_status(self):
        print("When in a sub-menu, prints a report of the current instrument.")
    def do_status(self,args):
        self.status(verbose=True)
    def status(self,verbose=True):
        br_status =  self.obj.broker_status(debug_mode=self.debug_mode) #This may  be overridden by child classes
        lines = []
        if self.debug_mode: lines.append("Broker_status() = {0}".format(br_status))
        try:
            lines = []
            if self.obj.instr_connected:
                line = "Instrument connected,    "
            else:
                line = "Instrument NOT connected,"
            if self.obj.suspended:
                line += " SUSPENDED,    "
            else: 
                line += " not suspended,"
            if self.obj.power_on == True:
                line += " and powered on."
            elif self.obj.power_on == False:
                line += " and NOT powered on."
            else:
                line += " and power status is unknown."
            lines.append(line)
            if self.obj.db_connected:
                line = "Database Connected"
            else:
                line = "Database NOT Connected"
            if self.obj.last_db_time: 
                line += " at {0}.".format(self.obj.last_db_time)
            else: 
                line += ". No database connection time available."
            lines.append(line)
            if self.obj.start_time:
                lines.append("Broker start time: {0}".format(self.obj.start_time))
            else:
                lines.append("No start time available")
            if self.obj.last_data_time:
                lines.append("Last broker data time: {0}".format(self.obj.last_data_time))
            else: 
                lines.append("No last data time available")
            if len(self.obj.subscriptions) > 0:
                _subs = list(self.obj.subscriptions.keys())
                _subs.sort()
                lines.append("The subscribed parameters are:")
                line = '    '
                for parameter in _subs:
                    if len(line) + 2 + len(parameter) <= 74:
                        line += '{0}, '.format(parameter)
                    else:
                        lines.append(line)
                        line = '    {0}, '.format(parameter)
                else:
                    lines.append(line[:-2]) # remove trailing comma
            else:
                lines.append("There are no subscribed parameters.")
            if len(self.obj.callbacks) > 0:
                _cbs = list(self.obj.callbacks.keys())
                _cbs.sort()
                lines.append("The callback parameters are:")
                line = '    '
                for parameter in _cbs:
                    if len(line) + 2 + len(parameter) <= 74:
                        line += '{0}, '.format(parameter)
                    else:
                        lines.append(line)
                        line = '    {0}, '.format(parameter)
                else:
                    lines.append(line[:-2]) # remove trailing comma
            else:
                lines.append("There are no callback parameters.")
            t_o = self.obj.tokenOwner().get('result',None)
            if t_o is None:
                lines.append('Token owner is unknown.')
            elif len(t_o) == 0:
                lines.append('Token has no owner.')
            else:
                lines.append('Token owned by {0}.'.format(t_o))
        except Exception as e:
            lines.append("Error in _baseConsole.status processing {0}: {1}".format(br_status,e))
        if verbose is True:
            print("-"*80)    
            for line in lines:
                print("|    {line:74}|".format(line=line))
            print("-"*80)
    def help_connect(self):
        print("For debugging. Instantiate socket and subscription handlers. Connect to broker. Usually done automatically")
    def do_connect(self,args):
        result = self.obj.connect_to_broker()
        if result:
            print("Connection successful: {0}".format(result))
        else: print("Connection UN-successful: {0}".format(result))
    def help_suspend(self): print("Suspend broker ({0})to instrument communications. To resume, use resume command.".format(self.obj.BROKER_NAME))
    def do_suspend(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        print(self.obj.suspend_broker())
        self.do_token('release')
        self.status(verbose=False)
    def help_resume(self): print("Resume broker ({0})to instrument communications after they have been suspended.".format(self.obj.BROKER_NAME))
    def do_resume(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        print(self.obj.resume_broker(debug_mode=self.debug_mode))
        self.do_token('release')
    def help_shutdown(self):
        print("Shut down broker and disconnect. At this time, this may  cause console to crash as well.")
        print("Use connect command to re-connect")
    def do_shutdown(self,args):
        result = self.obj.shutdown_broker()
        print("Shutting down broker: {0}".format(result))
        result = self.obj.disconnect()
        print("Disconnecting from broker: {0}".format(result))
    def help_power(self):
        print("Get or set instrument power status.\r\nUsage:\r\npower [on|off]")
    def do_power(self,arg):
        if arg not in ('on','off','check'):
            arg = 'check'
        if arg is not 'check':
            self.do_token('acquire')
            if self.obj.token_acquired is False:
                print("Unable to get token, aborting.")
                return
        result = self.obj.power(command=arg,debug_mode=self.debug_mode)
        if self.obj.token_acquired is True:
            self.do_token('release')
        print("{0}.power({1}) is {2}".format(self.obj.BROKER_NAME,arg,result.get('result',result)))

class MainConsole(_BaseConsole):
    def __init__(self,context,program_name=__name__,**kwargs):
        self.context = context
        self.logger = logging.getLogger(self.__class__.__name__)
        if program_name:
            _BaseConsole.program_name = program_name # Note that this a class attribute and so will be shared by all instances (consoles)
        _BaseConsole.__init__(self,self.context,console_name='MainConsole',**kwargs)
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        self.prompt = "AVP> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        self.setup_intro()  # Prints out a bunch of info.
        self.consoles = {}
        self.consoles['aio']    = {'console_name':'AIO_c'    ,'obj':AIOConsole,'console_obj':AIOConsole(self.context,debug_mode=self.debug_mode),'initialized':False}
        self.consoles['powermon']= {'console_name':'powermon_c','obj':PowerMonConsole,'console_obj':None,'initialized':False}
        self.consoles['gps']    = {'console_name':'gps_c'    ,'obj':GPSConsole,'console_obj':None,'initialized':False}
        self.consoles['isco']   = {'console_name':'isco_c'   ,'obj':ISCOConsole,'console_obj':None,'initialized':False}
        self.consoles['lisst']  = {'console_name':'lisst_c'  ,'obj':LISSTConsole,'console_obj':None,'initialized':False}
        self.consoles['sonde']  = {'console_name':'sonde_c'  ,'obj':SondeConsole,'console_obj':None,'initialized':False}
        self.consoles['sounder']= {'console_name':'sounder_c','obj':SounderConsole,'console_obj':None,'initialized':False}
        self.consoles['mm3']    = {'console_name':'winch_c'  ,'obj':WinchConsole,'console_obj':None,'initialized':False}
        self.consoles['wind']   = {'console_name':'wind_c'   ,'obj':WindConsole,'console_obj':None,'initialized':False}
        #Start up aio
        self.start_sub_menu('aio',init_only=True)
        if hasattr(self,'schedule_status') is False:
            self.schedule_status = AVPScheduleStatus(self.context.config,debug_mode=self.debug_mode)
    def setup_intro(self):
        # Set up intro block of text.
        CR = '\n'
        self.intro  = (80*"-") + CR
        line = "Welcome to the AVP console."
        self.intro += "|     {0:^68}     |{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|     {0:^68}     |{cr}".format(line,cr=CR)
        line = 'Instrument Sub-Consoles:'
        self.intro += "|     {0:<68}     |{cr}".format(line,cr=CR)
        consoles = ('aio','powermon','gps','isco','lisst','sonde','sounder','winch','wind')
        for c in consoles:
            line = '{cmd:<10}- {cmd} commands.'.format(cmd=c)
            self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|     {0:^68}     |{cr}".format(line,cr=CR)
        
        line = 'Commands common to most sub-consoles:'
        self.intro += "|     {0:<68}     |{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Control token operations.".format(cmd='token')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Get a list of all broker's parameters.".format(cmd='para')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Report of every parameter and its value.".format(cmd='report')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        #line = "{cmd:<10}- Attempt communications connection with broker.".format(cmd='connect') # Almost never needed
        #self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Suspend communications between broker and instrument.".format(cmd='suspend')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Resume communications between broker and instrument.".format(cmd='resume')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Start direct communications with suspended instrument.".format(cmd='console')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Get parameter value(s) from broker.".format(cmd='value')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Get parameter value(s) from memory.".format(cmd='mem')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Set parameter value.".format(cmd='set')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Subscribe to automatic parameter updates.".format(cmd='sub')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Un-subscribe from automatic parameter updates.".format(cmd='unsub')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        
        line = 'Other Console Commands:'
        self.intro += "|     {0:<68}     |{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get help on [cmd].'.format(cmd='help [cmd]')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Perform a standard cast'.format(cmd='cast')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Perform an ISCO cast'.format(cmd='casti')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Perform a LISST cast'.format(cmd='castl')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Query or set cast schedule'.format(cmd='sched')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- exit Console or Sub-Console'.format(cmd='exit')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        #print ">>>>{0}".format(self.intro)
        self.intro += line
    def do_sonde(self,args):
        self.start_sub_menu('sonde')
    def help_sonde(self): print("Enters the sonde sub-menu")
    def do_powermon(self,args):
        self.start_sub_menu('powermon')
    def help_powermon(self): print("Enters the power monitor sub-menu")
    def do_gps(self,args):
        self.start_sub_menu('gps')
    def help_gps(self): print("Enters the GPS sub-menu")
    def do_isco(self,args):
        self.start_sub_menu('isco')
    def help_isco(self): print("Enters the ISCO sub-menu")
    def do_lisst(self,args):
        self.start_sub_menu('lisst')
    def help_lisst(self): print("Enters the LISST sub-menu")
    def do_winch(self,args):
        self.start_sub_menu('sonde',init_only=True) # Winch needs the sonde to be instantiated
        self.start_sub_menu('mm3')
    def help_winch(self): print("Enters the winch sub-menu")
    def do_aio(self,args):
        self.start_sub_menu('aio')
    def help_aio(self): print("Enters the aio sub-menu")
    def do_sounder(self,args):
        self.start_sub_menu('sounder')
    def help_sounder(self): print("Enters the sounder sub-menu")
    def do_wind(self,args):
        self.start_sub_menu('wind')
    def help_wind(self): print("Enters the wind sub-menu")
    def start_sub_menu(self,broker,init_only=False):
        # broker is a string, the name of the broker.
        # If init_only is true, initialize everything, but don't go into sub-menu
        if self.consoles[broker]['initialized'] is False:
            self.context.startup(broker,debug_mode=self.debug_mode)
            if broker not in self.context.brokers:
                print(("{0} not in context.brokers".format(broker)));
                # Didn't work.
                return False
            self.consoles[broker]['console_obj'] = self.consoles[broker]['obj'](self.context,consoles=self.consoles,debug_mode=self.debug_mode)
            console_name = self.consoles[broker]['console_name']
            console_device = self.consoles[broker]['console_obj']
            setattr(self,console_name,console_device)
            self.consoles[broker]['initialized'] = True
        if init_only is False:
            sub_cons = getattr(self,self.consoles[broker]['console_name'])
            sub_cons.cmdloop()
    def help_sched(self):
        print('View or set the schedule status')
        print('    Usage:')
        print('    sched [on|off|paused]')
    def do_sched(self,args):
        if len(args) == 0:
            print('Schedule state is {0} as of {1}'.format(self.schedule_status.state,self.schedule_status.change_time))
        else:
            if args in self.schedule_status.VALID_SCHEDULE_STATES: 
                self.schedule_status.state = args
            else:
                print('Schedule request {0} not in {1}'.format(args,self.schedule_status.VALID_SCHEDULE_STATES))
    def do_status(self,args='all'):
        print("System status")
        if self.consoles['aio']['initialized'] is True:
            self.AIO_c.do_status(1)
        if self.consoles['powermon']['initialized'] is True:
            self.powermon_c.do_status(1)
        if self.consoles['gps']['initialized'] is True:
            self.gps_c.do_status(1)
        if self.consoles['isco']['initialized'] is True:
            self.isco_c.do_status(1)
        if self.consoles['lisst']['initialized'] is True:
            self.lisst_c.do_status(1)
        if self.consoles['sonde']['initialized'] is True:
            self.sonde_c.do_status(1)
        if self.consoles['sounder']['initialized'] is True:
            self.sounder_c.do_status(1)
        if self.consoles['mm3']['initialized'] is True:
            self.winch_c.do_status(1)
        if self.consoles['wind']['initialized'] is True:
            self.wind_c.do_status(1)
        print('-'*80)
    def help_cast(self):
        print("Perform a cast")
        print("    usage: cast [depth in meters [S <sample time in seconds>]] ")
        print("    S = Static cast, not a profile. Lower to depth and sample for sample time")
        print("    Notes: If no depth is specified cast status is returned")
        print("        To cast to bottom, use large depth such as 999")
    def help_castl(self):
        print("Perform a LISST cast")
        print("    usage: lcast [depth in meters [S <sample time in seconds>]] ")
        print("    S = Static cast, not a profile. Lower to depth and sample for sample time")
        print("    Notes: If no depth is specified cast status is returned")
        print("        To cast to bottom, use large depth such as 999")
    def help_casti(self):
        print("Perform a cast")
        print("    usage: casti <depth in meters> <bottle_number> <sample_volume ml> ")
        print("    Notes: If no depth is specified cast status is returned")
        print("        To cast to bottom, use large depth such as 999")
    def do_castl(self,args=None):
        args_l = args.split()
        depth_target = None
        profile = True
        max_sample_time = None
        park_pos='default'
        try:
            depth_target = args_l[0]
            try:
                if args_l[1] == 'S':
                    try:
                        max_sample_time = float(args_l[2])
                        profile = False
                        park_pos='bottom' # No retrieve after non-profile cast
                        print("STATIC CAST TO {0}".format(depth_target))
                    except Exception as e:
                        print(e)
                        return
                else:
                    print("Unknown arguments {0} or {1}".format(args,args_l))
                    self.help_castl()
                    return
            except:
                pass
        except:
            print("Cast status is {0}".format(self.schedule_status.state))
            return
        self.cast(isco_cast=False,
                  lisst_cast=True,
                  depth_target=depth_target,
                  profile=profile,
                  max_sample_time=max_sample_time,
                  park_pos=park_pos)
    def do_casti(self,args=None):
        args_l = args.split()
        try:
            depth_target = args_l[0]
            try:
                self.cast(isco_cast=True,
                          lisst_cast=False,
                          depth_target=depth_target,
                          isco_bottle=args_l[1],
                          isco_volume=args_l[2])
            except:
                print("Unknown arguments {0} or {1}".format(args,args_l))
                self.help_casti()
        except:
            print("Cast status is {0}".format(self.schedule_status.state))
            return
    def do_cast(self,args=None):
        args_l = args.split()
        depth_target = None
        profile = True
        max_sample_time = None
        park_pos='default'
        try:
            depth_target = args_l[0]
            try:
                if args_l[1] == 'S':
                    try:
                        max_sample_time = float(args_l[2])
                        profile = False
                        park_pos='bottom' # No retrieve after non-profile cast
                        print("STATIC CAST TO {0}".format(depth_target))
                    except Exception as e:
                        print(e)
                        return
                else:
                    print("Unknown arguments {0} or {1}".format(args,args_l))
                    return
            except:
                pass
        except:
            print("Cast status is {0}".format(self.schedule_status.state))
            return
        self.cast(depth_target=args,
                  profile=profile,
                  max_sample_time=max_sample_time,
                  isco_cast=False,
                  lisst_cast=False,
                  park_pos=park_pos)
    def cast(self,depth_target=None,wipe=True,profile=True,max_sample_time=None,lisst_cast=False,isco_cast=False,
             isco_bottle=1,isco_volume=1000,park_pos='default',**kwargs):
        if not depth_target or depth_target is None:
            depth_target = 999.9 # This should get us to use depth from sounder.
        try:
            depth_target = float(depth_target)
        except:
            print("Error, invalid depth:{0}.".format(depth_target))
            self.help_cast()
            return 0
        if depth_target <= 0:
            print("Invalid depth:{0}, depth must be > 0".format(depth_target))
            return 0
        if not hasattr(self,'console_cast'): # Instantiate a cast if we haven't already
            self.console_cast = avp_cast.Cast(self.context,
                                              program_name=self.program_name,
                                              debug_mode=self.debug_mode)
        self.console_cast.pre_config(depth_target=depth_target,
                                 cast_number=None, # Will auto-increment
                                 cast_time=datetime.now(pytz.reference.LocalTimezone()), # No Waiting
                                 wipe=wipe,
                                 profile=profile,
                                 max_sample_time=max_sample_time,
                                 lisst_cast=lisst_cast, 
                                 isco_cast=isco_cast,
                                 isco_bottle=isco_bottle,
                                 isco_volume=isco_volume,
                                 park_pos=park_pos,
                                 debug_mode=self.debug_mode)
        result = self.console_cast.start()
        print("cast result:{cr}{res}".format(res=avp_util.print_dict(result),cr=CR))
    def do_para(self,args='all'):
        args_l = args.split()
        if self.consoles['aio']['initialized'] is True:
            if 'aio' in args_l or 'all' in args_l: self.AIO_c.do_para(args)
        if self.consoles['powermon']['initialized'] is True:
            if 'powermon' in args_l or 'all' in args_l: self.powermon_c.do_para(args)
        if self.consoles['gps']['initialized'] is True:
            if 'gps' in args_l or 'all' in args_l: self.GPS_c.do_para(args)
        if self.consoles['isco']['initialized'] is True:
            if 'isco' in args_l or 'all' in args_l: self.isco_c.do_para(args)
        if self.consoles['lisst']['initialized'] is True:
            if 'lisst' in args_l or 'all' in args_l: self.lisst_c.do_para(args)
        if self.consoles['sonde']['initialized'] is True:
            if 'sonde' in args_l or 's' in args_l or 'all' in args_l: self.sonde_c.do_para(args)
        if self.consoles['sounder']['initialized'] is True:
            if 'sounder' in args_l or 'all' in args_l: self.sonde_c.do_para(args)
        if self.consoles['mm3']['initialized'] is True:
            if 'mm3' in args_l or 'w' in args_l or 'all' in args_l: self.winch_c.do_para(args)
        if self.consoles['wind']['initialized'] is True:
            if 'wind' in args_l or 'all' in args_l: self.wind_c.do_para(args)
    def help_para(self):
        print("Print parameters")
        print("     usage: para [aio] [powermon] [gps] [isco] [lisst] [sonde|s] [sounder] [winch|w] [wind]")
    def do_exit(self,args):
        avp_input = input("enter x to exit:")
        if avp_input.upper() == 'X': return -1
    def do_shutdown(self,args):
        # Perhaps support all
        args_l = args.split()
        if len(args_l) == 0: self.help_shutdown()
        if 'aio' in args_l: self.AIO_c.do_shutdown(args)
        if 'powermon' in args_l: self.powermon_c.do_shutdown(args)
        if 'gps' in args_l: self.GPS_c.do_shutdown(args)
        if 'isco' in args_l: self.isco_c.do_shutdown(args)
        if 'lisst' in args_l: self.lisst_c.do_shutdown(args)
        if 'sonde' in args_l or 's' in args_l: self.sonde_c.do_shutdown(args)
        if 'sounder' in args_l: self.sonde_c.do_shutdown(args)
        if 'winch' in args_l or 'w' in args_l: self.winch_c.do_shutdown(args)
        if 'wind' in args_l: self.wind_c.do_shutdown(args)
    def help_shutdown(self):
        print("Shut down specified broker")
        print("usage: shutdown <broker1> [broker2 ... [brokerN]]")
    def do_connect(self,args):
        # Perhaps support all
        print("Command only supported in sub-consoles.")
    def help_connect(self):
        print("Command only supported in sub-consoles.")
    def do_report(self,args='all'):
        args_l = args.split()
        if self.consoles['aio']['initialized'] is True:
            if 'aio' in args_l or 'all' in args_l: self.AIO_c.do_report(args)
        if self.consoles['powermon']['initialized'] is True:
            if 'powermon' in args_l or 'all' in args_l: self.powermon_c.do_report(args)
        if self.consoles['gps']['initialized'] is True:
            if 'gps' in args_l or 'all' in args_l: self.GPS_c.do_report(args)
        if self.consoles['isco']['initialized'] is True:
            if 'isco' in args_l or 'all' in args_l: self.isco_c.do_report(args)
        if self.consoles['lisst']['initialized'] is True:
            if 'lisst' in args_l or 'all' in args_l: self.lisst_c.do_report(args)
        if self.consoles['sonde']['initialized'] is True:
            if 'sonde' in args_l or 's' in args_l or 'all' in args_l: self.sonde_c.do_report(args)
        if self.consoles['sounder']['initialized'] is True:
            if 'sounder' in args_l or 'all' in args_l: self.sonde_c.do_report(args)
        if self.consoles['mm3']['initialized'] is True:
            if 'mm3' in args_l or 'w' in args_l or 'all' in args_l: self.winch_c.do_report(args)
        if self.consoles['wind']['initialized'] is True:
            if 'wind' in args_l or 'all' in args_l: self.wind_c.do_report(args)
    # Shortcuts
    do_w = do_winch
    do_s = do_sonde
    do_stat = do_status

class WinchConsole(_BrokerConsole):
    ''' Any command which takes the token, should pause the schedule first. Schedule can be un-paused when console is exited
    These command should also check to see if a cast is in progress
    '''
    REQUIRED_MM3_SUBSCRIPTIONS = ('position','desired_position','in_position',
        'neg_limit_switch','pos_limit_switch','pwm_out','amps_limit','deadband','enable_db')
    def __init__(self,context,**kwargs):
        self.debug_mode = kwargs.pop('debug_mode',False)
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='mm3',debug_mode=self.debug_mode,**kwargs)
        self.prompt = "AVP winch> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        tokenName = "AVPconsole.{0}".format(self.console_name)
        self.setup_intro()
        self.winch = Winch(context,interactive=True,debug_mode=self.debug_mode)
        self.sonde = self.winch.sonde
        self.sonde.add_subscriptions(['depth_m'],subscriber=tokenName,**kwargs)
        if hasattr(self.obj,'spcond_mScm'):
            self.sonde.add_subscriptions(['spcond_mScm'],subscriber=tokenName,**kwargs)
        if hasattr(self.obj,'spcond_uScm'):
            self.sonde.add_subscriptions(['spcond_uScm'],subscriber=tokenName,**kwargs)
        self.speedlimit = self.winch.SLOW_SPEED
        self.max_stopped = timedelta(seconds=10)
        self.obj.add_subscriptions(self.REQUIRED_MM3_SUBSCRIPTIONS,on_change=True,subscriber=self.console_name)
        if hasattr(self,'schedule_status') is False:
            self.schedule_status = AVPScheduleStatus(self.context.config,debug_mode=self.debug_mode)
        if self.schedule_status.cast_status != 'done':
            print('')
            print("!!!!WARNING: Cast status is currently {0}!!!\n!!!Operating winch will cause cast to fail. !!!!".format(self.schedule_status.cast_status))
            print('')
        elif self.schedule_status.state == 'on':
            print('')
            print('    CAUTION: Schedule status is {0}.'.format(self.schedule_status.state))
            print('             Please check time of next cast before operating winch.')
            print('')
        if self.sonde.instr_connected is True:
            if self.sonde.sampling.value != True:
                print('    NOTICE:  Sonde is not currently sampling. Start sampling using')
                print('             AVP winch> sonde sample on')
        else:
            print("Sonde is not conneced. Some functions may not work properly")
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP winch sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = 'The winch sub-console uses both the motor and sonde brokers to control'
        self.intro += "|     {0:^73}|{cr}".format(line,cr=CR)
        line = 'the sonde. Please note that there are 64k index positions per drum'
        self.intro += "|     {0:<73}|{cr}".format(line,cr=CR)
        line = 'revolution, 0 is with the sonde completely raised, and winch speeds'
        self.intro += "|     {0:<73}|{cr}".format(line,cr=CR)
        line = 'range from 1 to 35.'
        self.intro += "|     {0:<73}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|     {0:^73}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|     {0:<73}|{cr}".format(line,cr=CR)
        
        line = '{cmd:<10}- Get winch status'.format(cmd='status')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Move winch to an index position'.format(cmd='to')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Move winch up or down. There are various options.'.format(cmd='up|down')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Move winch to a specified depth'.format(cmd='depth')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Monitor winch without moving it or taking token'.format(cmd='mon')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Set current position to zero (fully raised)'.format(cmd='zero')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Set current position to zero (fully raised)'.format(cmd='zero')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<11}- Run position calibration routine'.format(cmd='calibration')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        #print ">>>>{0}".format(self.intro)
        self.intro += line

    def help_to(self):
        print("move to a specified posision. Optionally stop when water is detected is reached.")
        print("     usage: to <position> [at <speed>] [PWL|CWL|WL]")
    def complete_to(self,text,line,begidx,endidx):
        _OPTIONS = ('','at','PWL','CWL','WL')
        return [i for i in _OPTIONS if i.startswith(text)]
    def do_to(self,args):
        args_l = args.split()
        location = 0
        #stop_check = set()
        stop_conditions = {'PWL':self.winch.press_wl,'CWL':self.winch.cond_wl,'WL':self.winch.any_wl}
        speedlimit=self.speedlimit
        if len(args_l) < 1:
            self.help_to()
            return
        try:
            location = int(args_l[0])
        except ValueError as e:
            print("Position must be an integer {0}".format(e))
            return
        if self.obj.position.value > location:# up
            stop_args = [1]
            limit_stop = "up"
        else:# down
            stop_args = [0]
            limit_stop = "down"
        if 'at' in args_l and len(args_l) >= 3:
            try:
                speedlimit = int(args_l[2])
            except ValueError as e:
                print("Speed must be an integer {0}".format(e))
                return
        stop_check = set(stop_conditions.keys()) & set(args_l) # Bitwise and to see if any of the stop conditions are in our arguments
        if stop_check:
            stop_funct_name = stop_check.pop()
            stop_funct = stop_conditions.get(stop_funct_name)
            print("     Using stop function {0} with argument {1}.".format(stop_funct_name,stop_args))
        else:
            stop_funct = None
        print("Moving to {0} at {1}, ".format(location,speedlimit, end=' '))
        if limit_stop:
            print("using {0} limit_stop, ".format(limit_stop, end=' '))
        if stop_funct is not None:
            print("using stop functions {0} with argument {1}, ".format(stop_funct.__name__,stop_args, end=' '))
        print("max stopped time is {0} sec.".format(self.max_stopped))
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result = self.winch.move_to_absolute(
                    location,
                    speedlimit=speedlimit,
                    limit_stop=limit_stop,
                    in_pos=False,
                    max_stopped=self.max_stopped,
                    stop_funct=stop_funct,
                    stop_args=stop_args,
                    debug_mode=self.debug_mode)
        self.do_token('release')
        print("Motor stopped due to: {0}".format(result['monitor_move']))
    def help_down(self):
        print("usage: down|up [<count>[m]] [at <speed>] [PWL|CWL|WL]")
        print("    examples: up 5000 at 5")
        print("    examples: down .5m at 3 WL")
        print("    Optional stop conditions:")
        print("        PWL = pressure water line")
        print("        CWL = condictivity water line")
        print("         WL = any waterline")
    def do_down(self,args):
        self.move(args,direction='down')
    def help_up(self):
        self.help_down()
    def do_up(self,args):
        self.move(args,direction='up')
    def help_depth(self):
        print("Move to given depth")
        print("usage: depth <depth in meters>")
    def do_depth(self,args):
        if self.sonde.initialized is False:
            print("Sonde not initialized")
            return
        motorspeed = self.speedlimit
        # See if argument is valid
        try:
            desired_depth = float(args)
        except Exception as e:
            print("Depth format incorrect: {0}".format(args,e))
            return
        # CHECK IF NUMBER IS TOO BIG OR NEGATIVE
        if desired_depth < 0:
            print("Requested depth {0} must be >= 0 meters".format(desired_depth))
            return
        max_depth = 100 # NEED A BETTER VARIABLE HERE
        if desired_depth > max_depth:
            print("Requested depth {0} must be <= {1}meters ".format(desired_depth,max_depth))
            return
        # Check current depth
        if self.sonde.sampling.value == False: # Is sonde data current?
            print("Starting sonde data sampling:", end=' ')
            result = self.sonde.start_sampling(debug_mode=self.debug_mode)
            if result.get('result') == 'ok': time.sleep(1)
            else:
                print("depth result:{0}".format(result))
                return
        # Up or down?
        if self.sonde.depth_m.value < desired_depth:
            direction = 'down'
        elif self.sonde.depth_m.value > desired_depth:
            direction = 'up'
        else:
            print("Depth {0} has reached desired depth {1}".format(self.sonde.depth_m.value,desired_depth))
            return
        # Estimate distance
        position_change = abs(desired_depth - self.sonde.depth_m.value)
        desired_clicks = self.winch.meters_to_clicks(position_change)
        # Now move
        args = "{0} at {1}".format(desired_clicks, motorspeed)
        if self.debug_mode: print(("Moving {0} {1} clicks or {2} meters to {3}".format(direction,desired_clicks,position_change,desired_depth)))
        self.move(args,direction=direction)
    def help_move(self):
        print("Using down, up, and to commands is preferred.")
        self.help_down()
        self.help_to()
    def move(self,args,direction='unknown'):
        '''may want to support -stop
        direction should be 'up' or 'down'
        The argument have several permutations
        at <speed> does a move_at_speed
        <position> does a move_to_relative
        <position at <speed> does a move_to_relative with a velocity_limit.
        Any of these can have a -stop <stop condition>
        '''
        args_l = args.split()
        #stop_check = set()
        units = 'unknown'
        stop_conditions = {'PWL':self.winch.press_wl,'CWL':self.winch.cond_wl,'WL':self.winch.any_wl}
        motorspeed = self.speedlimit
        limit_stop = direction
        # First dome error checking and setup
        if direction == 'up':
            stop_args = [1]
        elif direction =='down':
            stop_args = [0]
        else:
            print("{0} is an invalid direction".format(direction))
            limit_stop = None
            return
        if len(args_l) < 1: # need some arguments
            self.help_down()
            return
        stop_check = set(stop_conditions.keys()) & set(args_l) # See if any of the stop conditions are in our arguments
        if stop_check:
            stop_funct_name = stop_check.pop()
            stop_funct = stop_conditions.get(stop_funct_name)
            print("     Using stop function {0} with argument {1}.".format(stop_funct_name,stop_args))
        else:
            stop_funct = None
        if 'at' in args_l:
            at_speed_pos = args_l.index('at') + 1
            try:
                motorspeed = args_l[at_speed_pos]
            except ValueError as e:
                print("Error: Bad command '{0}'. Speed must be an integer{1}".format(args,e))
                return
            if args_l[0] == 'at':
                print("Moving {0} at {1}, ".format(direction,motorspeed), end=' ')
                if limit_stop:
                    print("using {0} limit_stop, ".format(limit_stop), end=' ')
                try:
                    print("using stop functions {0} with argument {1}, ".format(stop_funct.__name__,stop_args), end=' ')
                except AttributeError:
                    pass
                print("max stopped time is {0} sec.".format(self.max_stopped))
                self.do_token('acquire')
                if self.obj.token_acquired is False:
                    print("Unable to acquire token, aborting move.")
                    return
                result = self.winch.move_at_speed(
                            motorspeed,
                            direction=direction,
                            limit_stop=limit_stop,
                            in_pos=False,
                            max_stopped=self.max_stopped,
                            stop_funct=stop_funct,
                            stop_args=stop_args,
                            debug_mode=self.debug_mode)
                self.do_token('release')
                return result
        distance = str(args_l[0])
        if distance[-1:] == 'm':
            units = 'meters'
            try:
                distance = abs(float(distance[:-1])) # strip 'm' and convert to float
            except ValueError as e:
                print("Couldn't parse depth in meters {0}".format(e))
                return
        else:
            units = 'clicks'
            try:
                distance = abs(int(distance))
            except ValueError as e:
                print("Position must be an integer {0}".format(e))
                return
        if direction == 'up':
            distance *= -1
        if stop_funct is not None:
            print("using stop functions {0} with argument {1},".format(stop_funct.__name__,stop_args), end=' ')
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to acquire token, aborting move.")
            return
        result = self.winch.move_to_relative(distance,
                                             speedlimit=motorspeed,
                                             limit_stop=limit_stop,
                                             max_stopped=self.max_stopped,
                                             neg_lim_max_time=self.max_stopped,
                                             pos_lim_max_time=self.max_stopped,
                                             stop_funct=stop_funct,
                                             stop_args=stop_args,
                                             units=units,
                                             debug_mode=self.debug_mode)
        self.do_token('release')
        return result
    def do_stop(self,args):
        try:
            self.do_token('force')
            self.obj.stop(debug_mode=self.debug_mode)
        except Exception as e:
            print("{0}.do_stop error {1}".format(self.console_name,e))
        self.do_token('release')
        self.do_value('PWM_limit PWM_limited disable_pid velocity amps position desired_position in_position')
    def help_monitor(self):
        print("Monitor winch status without moving winch. Does not take token.")
        print("    usage: monitor|mon")
    def do_monitor(self,args):
        print("-------------------- Press ANY key to exit monitor mode. --------------------")
        #print self.winch.feedback_header()
        print(self.winch.monitor_move(in_pos=False,
                                      ipc_poll=False,
                                      max_zero_v=timedelta(days=1),
                                      debug_mode=self.debug_mode))
    def help_setpos(self):
        print("Sets current position to given value")
        print("    usage: setpos <position>")
    def do_setpos(self,args):
        args_l = args.split()
        try:
            location = int(args_l[0])
        except ValueError as e:
            print("Position must be an integer {0}".format(e))
            return
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        print("Setting 'position' to {0}:".format(location), end=' ')
        result = self.obj.set({'position':location},debug_mode=self.debug_mode) # set position to 0
        self.do_token('release')
        print("setpos result:{0}".format(result))
    def help_storepos(self,args):
        print("Store current position to EEPROM")
    def do_storepos(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        print("Storing position {0} to EEPROM:".format(args), end=' ')
        result = self.obj.store_position(debug_mode=self.debug_mode)
        self.do_token('release')
        print("storepos result:{0}".format(result))
    def help_store(self):
        print("Store a value to EEPROM using WRITE_STORE. Use with caution")
        print("     usage: store <parameter> <value>")
    def do_store(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        print("Storing {0} to EEPROM:".format(args), end=' ')
        result = self.do_set(args,write_store=True)
        self.do_token('release')
        print("store result:{0}".format(result))
    def help_zero(self):
        print("Sets current position to 0")
        print("    usage: zero")
    def do_zero(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        self.do_setpos('0') # This will print out diagnostics and result.
        #self.do_token('release') # token already released by set_pos
    def help_reset(self):
        print("Implements the Motion Mind 3's reset command")
        print("Sending the reset command causes the Motion Mind Controller to stop the motor and software reset.")
    def do_reset(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result = self.obj.reset(debug_mode=self.debug_mode)
        self.do_token('release')
        print("reset result:{0}".format(result))
    def help_restore(self):
        print(self.obj.restore.__doc__)
    def do_restore(self,args):
        result = self.obj.restore(debug_mode=self.debug_mode)
        print("restore result:{0}".format(result))
    def help_calibration(self):
        print("Run winch's mm3/sonde calibration routine")
        print(self.winch.calibration.__doc__)
    def do_calibration(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get motor token, aborting.")
            return
        self.sonde.get_token(program_name=self.program_name,
                             calling_obj=self.__class__.__name__,
                             override=True,
                             debug_mode=self.debug_mode)
        if self.sonde.token_acquired is False:
            print("Unable to get sonde token, aborting.")
            return        
        self.winch.calibration(debug_mode=self.debug_mode)
        self.do_token('release')
    def help_get_amps(self):
        print('Calls winch.get_amps_limits(debug_mode=True) for testing')
    def do_get_amps(self,args):
        self.winch.get_amps_limits(self.obj.config,debug_mode=True)
    # The following have their help in the parent class
    def do_status(self,args):
        self.status(verbose=True) # Broker Status
        lines = []
        if self.obj.initialized is False:
            lines.append("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
        elif not self.obj.instr_connected:
            lines.append("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
        else:
            self.obj.get_value(('position','neg_limit_switch','pos_limit_switch','desired_position','amps_limit','temperature','in_position','deadband','enable_db'),debug_mode=self.debug_mode)
            if self.obj.neg_limit_switch.value :
                lines.append("Negative limit switch activated. Will not be able to move up.")
            if self.obj.pos_limit_switch.value:
                lines.append("Positive limit switch activated. Will not be able to move down.")
            lines.append("Max speed is {0}.  Position: {1} Target:{2} {3}"
                 .format(self.speedlimit,self.obj.position.value,self.obj.desired_position.value,
                         self.obj.position.units))
            lines.append("Motor amps_limit {0}{1}".format(self.obj.amps_limit.value,self.obj.amps_limit.units ))
            try:
                tempC = self.obj.temperature.value
                tempF = (9 / 5)*tempC + 32
                lines.append("Motor temperature {0:.2f}{1} ({2:.2f} {3})".format(tempC,self.obj.temperature.units,tempF,'degF'))
            except TypeError as e:
                # Probably not initialized yet
                pass
            if self.obj.enable_db.value == 0: db_enabled = 'not enabled'
            elif self.obj.enable_db.value == 1: db_enabled = 'enabled'
            else: db_enabled = 'status is unknown'
            lines.append("Motor in_position={0}, Position deadband is {1} and {2}.".format(self.obj.in_position.value,self.obj.deadband.value,db_enabled))
            lines.append("Last stop reason: {0}".format(self.winch.get_stop_reason()))
        for line in lines:
            print(("|    {line:74}|".format(line=line)))
        print(("-")*80)
    def do_console(self,args):
        if self.obj.suspended is False:
            print("Instrument must be suspended before console communications may be started.")
        else:
            eol = "\x0d\x0a"
            self.direct_connect(eol,'RW')
    # Aliases
    do_mon = do_monitor
    do_dn = do_down
    def help_help(self): # Summary of sonde commands
        print("calibration:          Calibrate winch (sonde & mm3)")
        print("debug:                Toggle debug mode")
        print("depth:                Move to given depth")
        print("down:                 Move down")
        print("x,exit,quit:          Return to main menu")
        print("init:                 Re-initialize broker client")
        print("mem:                  See values in memory without querrying broker")
        print("mon,monitor:          Monitor winch status")
        print("para:                 List available parameters")
        print("report:               List all parameters and their current values")
        print("reset:                Reset motor controller")
        print("restore:              Restore motor controller factory defaults")
        print("set:                  Set a value directly")
        print("setpos:               Set winch position")
        print("status:               Summary of most important data")
        print("sub:                  Subscribe to one or more or all parameters")
        print("to:                   Move to a position")
        print("token:                Acquire or release broker control token")
        print("unsub:                Unsubscribe to one or more or all parameters")
        print("up:                   Move up")
        print("value:                Return one or more or all values")
        print("zero:                 Set winch position to 0")

class SondeConsole(_BrokerConsole):
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='sonde',**kwargs)
        self.prompt = "AVP sonde> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        #self.intro  = "AVP sonde sub-console. enter 'x' to return to main console"
        self.setup_intro()
        #self.obj.has_token = False
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP sonde sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|     {0:<73}|{cr}".format(line,cr=CR)
        
        line = "{cmd:<10}- Alter or query sampling status. E.g. 'sample on'".format(cmd='sample')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get sonde status'.format(cmd='status')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Alter or query db logging status. E.g. 'logging on'".format(cmd='logging')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Is sonde in water?'.format(cmd='in_water')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Connect directly to sonde. Broker must be suspended.'.format(cmd='console')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Wipe instruments (sampling must be off).'.format(cmd='wipe')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Calibrate sonde pressure to 0.'.format(cmd='calibrate')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|          {0:<68}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line
    def help_in_water(self):
        print("Check if sonde is in water (required token)")
        print("Usage: (defualts to any)")
        print("in_water [any|all|depth_m|spcond_mScm|spcond_uScm]")
    def complete_in_water(self,text,line,begidx,endidx):
        _OPTIONS = ('','any','all','depth_m','spcond_mScm','spcond_uScm')
        return [i for i in _OPTIONS if i.startswith(text)]
    def do_in_water(self,args):
        if self.obj.sampling.value != True:
            print("Sonde is NOT sampling. Results may not be accurate.")
        if len(args) > 0:
            instrument = args
        else:
            instrument = 'any'
        result = self.obj.in_water(instrument=instrument,debug_mode=self.debug_mode)
        result_str = "Sonde is "
        if result[0] is False:
            result_str += "not "
        elif result[0] is True:
            pass
        else:
            result_str += "perhaps "
        result_str += "in the water based upon {0}".format(result[1])
        print(result_str)
    def help_wipe(self): print("Start sonde wipe procedure")
    def do_wipe(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result = self.obj.wipe(debug_mode=self.debug_mode)
        self.do_wipestatus(())
        self.do_token('release')
        print("wipe result:{0}".format(result))
    def help_wipestatus(self): print("Returns number fo wipes remaining. Alias = ws")
    def do_wipestatus(self,args):
        wipes_remaining = self.obj.get_value(['wipes_left']).get('wipes_left')/2.0
        print("Wipe status: {0} wipes remaining.".format(wipes_remaining))
    def help_calibrate(self):
        print("Calibrates sonde depth to 0.")
        print("usage: calibrate [force]")
        print("    force - force calibration even if sonde is in water") 
    def do_calibrate(self,args):
        if 'force' in args:
            check_instruments = False
        else:
            check_instruments = True
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result = self.obj.calibrate_pressure(check_instruments=check_instruments,debug_mode=self.debug_mode)
        self.do_token('release')
        print("calibrate result:{0}".format(result)) 
    def help_sample(self):
        print("usage: <sample|col> [on|off]")
        print("    note: withough any arguments, returns sampling status")
    def complete_sample(self,text,line,begidx,endidx):
        _OPTIONS = ('','on','off')
        return [i for i in _OPTIONS if i.startswith(text)]
    def do_sample(self,args):
        '''
        THIS SHOULD ONLY BE DONE THROUGH ????
        '''
        result = ''
        if args in ('on','off',):
            self.do_token('acquire')
            if self.obj.token_acquired is False:
                print("Unable to get token, aborting.")
                return
            if args == 'on':
                result = self.obj.start_sampling(debug_mode=self.debug_mode)
            else:
                result = self.obj.stop_sampling(debug_mode=self.debug_mode)
            self.do_token('release')
        else:
            if self.obj.sampling.value == True:
                result = "Sonde IS sampling"
            elif self.obj.sampling.value == False:
                result = "Sonde IS NOT sampling"
            else:
                result = "Sonde sampling status is unknown"
        print("sample result:{0}".format(result))
    def help_logging(self):
        print("usage: <logging|log> [on <cast number>|off]")
        print("    note: withough any arguments, logging returns status.")
        print("          Run number will be 1.")
    def complete_logging(self,text,line,begidx,endidx):
        _OPTIONS = ('','on','off')
        return [i for i in _OPTIONS if i.startswith(text)]
    def do_logging(self,args):
        args_l = args.split()
        if not args:
            if self.obj.is_logging(): result = "Sonde IS logging"
            else: result = "Sonde IS NOT logging"
            print(result)
            return
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        if args_l[0] == 'on':
            try:
                result = self.obj.start_logging(cast_number=int(args_l[1]),debug_mode=self.debug_mode)
            except Exception as e:
                result =  "Unknown cast number {0}. Use 1 as default:{1}".format(args, e)                
        elif args_l[0] == 'off':
            result = self.obj.stop_logging(debug_mode=self.debug_mode)
        else:
            result =  "Unknown arguments {0}".format(args)
        self.do_token('release')
        print("logging result:{0}".format(result))
    # The following have their help in the parent class
    def do_status(self,args):
        self.obj.get_value(['sampling','logging'])
        print('-'*80)
        self.status(verbose=True) # Broker Status
        if self.obj.initialized is False:
            print("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
            return
        if not self.obj.instr_connected:
            print("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
            return
        try:
            print("| At {0} the subscribed values were:".format(datetime.strftime(self.obj.depth_m.sample_time,"%H:%M:%S.%f %Z")))
        except AttributeError:
            print("sonde does not seem to have depth sensor.")
        print("| sampling={0}  logging={1}".format(self.obj.sampling.value,self.obj.logging.value))
        print("| Sonde at {0} {1}".format(self.obj.depth_m.value,self.obj.depth_m.units))
        if hasattr(self.obj,'spcond_mScm'):
            print("| Conductivity is {0} {1}".format(self.obj.spcond_mScm.value,self.obj.spcond_mScm.units))
        if hasattr(self.obj,'spcond_uScm'):
            print("| Conductivity is {0} {1}".format(self.obj.spcond_uScm.value,self.obj.spcond_uScm.units))
        # may want to add some unsubscribed values here.
    def do_console(self,args):
        if self.obj.suspended is False:
            print("Instrument must be suspended before console communications may be started.")
        else:
            eol = "\x0d\x0a"
            self.direct_connect(eol,'RW')
    # Aliases
    do_cal = do_calibrate
    def help_cal(self): self.help_calibrate()
    do_ws = do_wipestatus
    def help_ws(self): self.help_wipestatus()
    do_log = do_logging
    def help_log(self): self.help_logging()
    def help_help(self): # Summary of sonde commands
        print("cal,calibrate:        Used to zero pressure sensor")
        print("sample:               Start, stop, or see sampling status (run mode)")
        print("console:              Communicate directly with sonde")
        print("debug:                Toggle debug mode")
        print("x,exit,quit:          Return to main menu")
        print("init:                 Re-initialize broker client")
        print("log,logging:          Start, stop, or see database logging status (run mode)")
        print("mem:                  See values in memory without querrying broker")
        print("para:                 List available parameters")
        print("report:               List all parameters and their current values")
        print("status:               Summary of most important data")
        print("sub:                  Subscribe to one or more or all parameters")
        print("token:                Acquire or release broker control token")
        print("unsub:                Unsubscribe to one or more or all parameters")
        print("value:                Return one or more or all values")
        print("wipe:                 Start wipe procedure")
        print("ws,wipestatus:        Report status of wipe procedure")

class SounderConsole(_BrokerConsole):
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='sounder', **kwargs)
        self.prompt = "AVP sounder> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        self.setup_intro()
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP depth sounder sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get sounder status'.format(cmd='status')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line
    # The following have their help in the parent class
    def do_status(self,args):
        self.status(verbose=True) # Broker Status
        lines = []
        if self.obj.initialized == False:
            lines.append("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
        elif self.obj.instr_connected == False:
            lines.append("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
        else:
            lines.append("Water depth is {0:.2f} {1}".format(
                self.obj.water_depth.value,self.obj.water_depth.units))
            lines.append("Working depth is {0:.2f} {1}".format(
                self.obj.water_depth_working.value,self.obj.water_depth_working.units))
            lines.append("Surface water temperature is {0:.1f} {1}".format(
                self.obj.water_temp_surface.value,self.obj.water_temp_surface.units))
        for line in lines:
            print("|    {line:74}|".format(line=line))
        print("-"*80)
    def do_console(self,args):
        if self.obj.suspended is False:
            print("Instrument must be suspended before console communications may be started.")
        else:
            eol = ""
            self.direct_connect(eol,'RO')
    # Aliases
class GPSConsole(_BrokerConsole):
    ''' GPS Console Cmd class
    '''
    GPS_MODES = {0:'Unknown',1:'No Fix (bad)',2:'2D (fair)',3:'3D (good)'}
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='gps', **kwargs)
        self.prompt = "AVP GPS> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        self.anchor_watch_center = (self.obj.ANCHOR_WATCH_LAT,self.obj.ANCHOR_WATCH_LON,)
        self.setup_intro()
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP GPS sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get gps status'.format(cmd='status')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line
    # The following have their help in the parent class
    def do_status(self,args):
        self.status(verbose=True) # Broker Status
        lines = []
        if self.obj.initialized == False:
            lines.append("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
        elif self.obj.instr_connected == False:
            lines.append("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
        else:
            try:
                loc = (self.obj.lat.value,self.obj.lon.value,)
                distance,bearing = gislib.get_distance_bearing(self.anchor_watch_center,loc,)
                lines.append("GPS mode: {0}".format(self.GPS_MODES.get(self.obj.mode.value,'Error')))
                lines.append("Position: {0[0]:5.6},{0[1]:5.6} is".format(loc))
                lines.append("{dist:d} m at {brg:5.4}{deg} True. from anchor watch center".format(
                              dist=int(distance*1000), brg=bearing,deg=chr(176)))
                lines.append("at {ctr[0]:5.6},{ctr[1]:5.6} of radius {rad:d} m".format(
                              ctr=self.anchor_watch_center, rad=int(self.obj.ANCHOR_WATCH_RADIUS * 1000)))
            except (TypeError, AttributeError):
                lines.append("GPS communications failure".format(loc))
        for line in lines:
            print("|    {line:74}|".format(line=line))
        print("-"*80)
    def do_console(self,args):
        if self.obj.suspended is False:
            print("Instrument must be suspended before console communications may be started.")
        else:
            eol = ""
            self.direct_connect(eol,'RO')
    # Aliases
class LISSTConsole(_BrokerConsole):
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='lisst', **kwargs)
        self.prompt = "AVP LISST> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        self.setup_intro()
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP LISST sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get LISST status'.format(cmd='status')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line
    def help_collect(self):
        print("Start/stop data collection. Get status")
        print("usage: collect [on <cast number>|off]")
    def do_collect(self,args):
        if args:
            self.do_token('acquire')
            if self.obj.token_acquired is False:
                print("Unable to get token, aborting.")
                return
            if args == 'off':
                print(self.obj.stop_collection(debug_mode=self.debug_mode))
            else:
                args_l = args.split()
                if args_l[0] == 'on':
                    try:
                        cast_number = int(args_l[1])
                        result = self.obj.start_collection(cast_number=cast_number,
                                                           pump_delay=self.obj.SAMPLE_LATENCY,
                                                           debug_mode=self.debug_mode)
                        print(result)
                    except Exception as e:
                        print("Error parsing arguments {0}:{1}".format(args,e))
            self.do_token('release')
        else:
            result = self.obj.data_collection.value
            if result == True:
                print("LISST IS collecting")
            elif result == False:
                print("LISST IS NOT collecting")
            else:
                print("Unknown lisst status ({0})".format(result))
        return    
    def help_flush(self):
        print("Flush LISST")
        print("usage: flush [time in seconds [b]]")
        print("    If no time is given, status will be returned")
        print("    b - blocking will wait until operation is over to return")
    def do_flush(self,args):
        args_l = args.split()
        print(args_l)
        if args_l:
            try:
                flush_time  = int(args_l[0])
            except Exception as e:
                print("Error, invalid argument {0}: {1}".format(args,e))
                return
            blocking=False
            if len(args_l) >= 2:
                if args_l[1][0] == 'b':
                    blocking=True
            self.do_token('acquire')
            if self.obj.token_acquired is False:
                print("Unable to get token, aborting.")
                return
            result = self.obj.flush(flush_time=flush_time,blocking=blocking,debug_mode=self.debug_mode)
            self.do_token('release')
            print("flush result:{0}".format(result))
        else:
            result = self.obj.is_flushing(debug_mode=self.debug_mode)
            if result:
                print("LISST IS flushing {0}".format(result))
            else:
                print("LISST IS NOT flushing {0}".format(result))
        return
    def help_pump(self):
        print("Turn LISST pump on,off or get status")
        print("usage: pump [on|off]")
    def do_pump(self,args):
        if args:
            self.do_token('acquire')
            if self.obj.token_acquired is False:
                print("Unable to get token, aborting.")
                return
            if args in ['on',1,True]:
                result = self.obj.start_pump(debug_mode=self.debug_mode)
            elif args in ['off',0,False]:
                result = self.obj.stop_pump(debug_mode=self.debug_mode)
            else:
                result = "Could not parse arguments {0}".format(args)
            print("pump result:{0}".format(result))
            self.do_token('release')
        else:
            result = self.obj.is_pumping(debug_mode=self.debug_mode)
            if result:
                print("LISST IS pumping ({0})".format(result))
            else:
                print("LISST IS NOT pumping ({0})".format(result))
        return
    def do_get(self,args):
        if args:
            lisst_file = args
        else:
            lisst_file = None
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result = self.obj.get_file(lisst_file=lisst_file,debug_mode=self.debug_mode)
        self.do_token('release')
        print(result)
    def do_del(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result = self.obj.delete_file(lisst_file=args,debug_mode=self.debug_mode)
        self.do_token('release')
        print(result)
    # The following have their help in the parent class
    def do_status(self,args):
        print('-'*69)
        self.status(verbose=True) # Broker Status
        if self.obj.initialized is False:
            print("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
            return
        if not self.obj.instr_connected:
            print("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
            return
        print("| SN: {0:20} Firmware:{1:32}|".format(self.obj.serial_number.value,self.obj.firmware_version.value))
        print("| Pumping: {0:15} Flushing:{1:32}|".format(self.obj.seawater_pump.value,self.obj.clean_water_flush.value))
        print("| Clean water level: {0:3} {1:41}|".format(self.obj.clean_water_level.value,' '))
        print('-'*69)
    def do_console(self,args):
        if self.obj.suspended is False:
            print("Instrument must be suspended before console communications may be started.")
        else:
            eol = "\x0a" # LISST doesn't like CR
            self.direct_connect(eol,'RW')

class ISCOConsole(_BrokerConsole):
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='isco', **kwargs)
        self.prompt = "AVP ISCO> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        self.setup_intro()
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP ISCO sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get ISCO status'.format(cmd='status')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line
    # The following have their help in the parent class
    def do_status(self,args):
        print('-'*80)
        self.status(verbose=True) # Broker Status
        if self.obj.initialized is False:
            print("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
            return
        if not self.obj.instr_connected:
            print("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
            return
        result = self.obj.get_value(['hardware_revision','software_revision','model','ID','isco_time','isco_status','isco_sample_time','bottle_num','sample_volume','sample_status'])
        try:
            print("| ISCO version: Hardware:{0} software:{1}".format(self.obj.hardware_revision.value,self.obj.software_revision.value))
            print("| model: {0} ID: {1}".format(self.obj.model.value,self.obj.ID.value))
            print("| time: {0} sample_time: {1} bottle no: {2} volume: {3} {4}".format(self.obj.isco_time.value,self.obj.isco_sample_time.value,self.obj.bottle_num.value,self.obj.sample_volume.value,self.obj.sample_volume.units))
            print("| isco status: {0}({1})".format(self.obj.get_isco_status(self.obj.isco_status.value,debug_mode=self.debug_mode),self.obj.isco_status.value))
            print("| sample status: {0}({1})".format(self.obj.get_sample_status(self.obj.sample_status.value,debug_mode=self.debug_mode),self.obj.sample_status.value))
        except Exception as e:
            print("Error: {0} in ISCOConsole.do_status".format(e))
        print('-'*80)
        return
    def help_on(self):
        print("If ISCO is off by front panel button, this will turn it on")
    def do_on(self,args):
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result = self.obj.sampler_on(debug_mode=self.debug_mode)
        self.do_token('release')
        print("on result:{0}".format(result))
    def help_sample(self):
        print("Take a sample.")
        print("usage:")
        print("sample ['b'bottle=1] ['v'volume=1000] ['c'cast=0] ['d'depth=0]")
        print("example:")
        print("sample b5 v1000 c1 d2.5")
        print("This will fill bottle 5 with 1000 ml for cast 0 at a recorded depth of 2.5 m")
    def do_sample(self,args):
        args_l = args.split()
        result = {}
        result['get_value'] = self.obj.get_value(['bottle_num','sample_volume'])
        bottle_num = self.obj.bottle_num.value
        sample_volume = 1000 # mL
        cast_number = 0
        sample_depth = 0 # mm
        try:
            for arg in args_l:
                param = int(arg[1:]) # All arguments we are looking for are integers
                if arg[:1] is 'b':
                    if param >= 1 and param <= self.obj.NUM_BOTTLES:
                        bottle_num = param
                    else:
                        print("{0} is not a valid bottle number".format(param))
                        return
                elif arg[:1] is 'v':
                    if param >= 1 and param <= self.obj.BOTTLE_SIZE:
                        sample_volume = param
                    else:
                        print("{0} is not a valid bottle volume".format(param))
                        return
                elif arg[:1] is 'c':
                    if param >= 0 :
                        cast_number = param
                    else:
                        print("{0} is not a valid cast number".format(param))
                        return
                elif arg[:1] is 'd':
                    sample_depth = param
                else:
                    print("{0} is not a valid argument")
                    return
        except Exception as e:
            print("Exception {0} from {1} in ISCOConsole.do_sample".format(e,args_l))
            return
        print("Taking {1} mL sample to bottle {0} at {3} mm for cast {2}".format(bottle_num, sample_volume, cast_number, sample_depth))
        self.do_token('acquire')
        if self.obj.token_acquired is False:
            print("Unable to get token, aborting.")
            return
        result['take_sample'] = self.obj.take_sample(bottle_num, sample_volume, cast_number, sample_depth,debug_mode=self.debug_mode)
        self.do_token('release')
        print("sample result:{0}".format(result))
    def do_console(self,args):
        if self.obj.suspended is False:
            print("Instrument must be suspended before console communications may be started.")
        else:
            print('To control the sampler keypad remotely, First enter menu mode by typing MENU at the ">" prompt and pressing ENTER. Then type CONTROL at the ">" prompt and press ENTER.')
            print('The sampler display appears on your computer monitor as you step through the programming screens.')
            print('While in this mode, the computer keys will be redirected to simulate the samplers keypad, and the sampler keypad itself will be disabled to avoid any conflict. The active keys and their corresponding functions are given below')
            print('    Computer                    Sampler')
            print('    <Esc>, S, s                 STOP')
            print('    L,l,U,u, <Backspace>        Left / Up')
            print('    R, r, D, d                  Right / Down')
            print('    O, o                        ON')
            print('    <Enter>, arrows, decimal, numbers Same as sampler')
            print('NOTE: As far as I know yet, to get out of this mode you need to let it time-out or cycle the power.')
            eol = "\x0d\x0a"
            self.direct_connect(eol,'RW')
    # Aliases
class AIOConsole(_BrokerConsole):
    AIO_DEVICES = { 'modem':'relay_modem_reset',
                    'sonde':'relay_sonde',
                    'winch':'reset_MM3',
                    'wind':'relay_wind',
                    'sounder':'relay_sounder',
                    'tension':'tension_switch_enable',
                    'limit':'limit_switch_enable'}
    AIO_OPTIONAL_PARAM = {'adcp':'relay_ADCP',
                    'isco':'relay_ISCO',
                    'lisst':'relay_LISST',
                    '24v':'relay_24V',
                    '5v':'relay_5V'}
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='aio', **kwargs)
        self.prompt =  "AVP aio> "
        if self.debug_mode:
            self.prompt = 'DB-{0}'.format(self.prompt)
        # Add the optional aio parameters
        for device,relay in list(self.AIO_OPTIONAL_PARAM.items()):
            if hasattr(context.aio,relay) is True:
                print(("Adding {0} relay".format(device)))
                self.AIO_DEVICES[device]=relay
        self.setup_intro()
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP aio sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = 'The aio broker monitors digital and analog inputs as well as digital' # Blank Line
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = 'outputs. Parameters can be referenced by address (pin_n_x or adc_x) or by' # Blank Line
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = 'alias. Either can be used for most console functionality.' # Blank Line
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Alter or query power status. E.g. 'power isco on'".format(cmd='power')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get aio status'.format(cmd='status')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line
    def help_power(self):
        print("Turns power to the instruments on or off")
        print("    usage: power [device [on|off]]")
        print("        device = adcp,isco,lisst,modem,sonde,sounder,winch,wind,24v")
        print("    if nothing is specified, lists all power statuses")
    def do_power(self,args):
        param_aliases = self.obj.config[self.obj.BROKER_NAME]['aliases']
        if self.debug_mode: print(("param_aliases:{cr}{pa}".format(pa=param_aliases,cr=CR)))
        args_l = args.split()
        current_value = None
        if len(args_l) >= 1:
            device = args_l[0]
            if device in self.AIO_DEVICES:
                pin_name = self.AIO_DEVICES[device]
                pin_address = param_aliases.get(pin_name)
                if pin_name.startswith('relay'):
                    pin_on = self.obj.RELAY_ON
                    pin_off = self.obj.RELAY_OFF
                else:
                    pin_on = 1
                    pin_off= 0
                if len(args_l) == 2:
                    mode = args_l[1]
                    param = {}
                    if mode =='on':
                        param[pin_address] = pin_on
                    elif mode == 'off':
                        param[pin_address] = pin_off
                    else:
                        print(("{0} is not a valid request".format(mode)))
                    if len(param) > 0:
                        print(("setting {0}.{1} to {2}".format(self.obj.BROKER_NAME,pin_address,param[pin_address])))
                        self.do_token('acquire')
                        if self.obj.token_acquired is False:
                            print("Unable to acquire token, aborting power command.")
                            return
                        result = self.obj.set(param,debug_mode=self.debug_mode)
                        self.do_token('release')
                        print(("Set result:", result))
                        return
                else:
                    current_value = self.obj.get_value([pin_address],debug_mode=self.debug_mode).get(pin_address)
                    if current_value == pin_on:
                        current_status = 'on'
                    elif current_value == pin_off:
                        current_status = 'off'
                    else:
                        current_status = 'unknown'
                    print(("Status of {0}/{1}/{2} is {3}={4}".format(device,pin_name,pin_address,current_status,current_value)))
                    return
            else:
                print(("{0} is not a valid device".format(args_l[0])))
        else:
            print(("{0:9}{1:25}{2:8}{3:4}".format('DEVICE','FUNCTION','ADDRESS','STAT')))
            for device,pin_name in list(self.AIO_DEVICES.items()):
                pin_address = param_aliases.get(pin_name)
                if self.debug_mode: print(("Pin name,address: {0},{1}".format(pin_name,pin_address)))
                current_value = self.obj.get_value([pin_address],debug_mode=self.debug_mode).get(pin_address)
                if pin_name.startswith('relay'):
                    pin_on = self.obj.RELAY_ON
                    pin_off = self.obj.RELAY_OFF
                else:
                    pin_on = 1
                    pin_off= 0
                if current_value == pin_on: pin_value = 'on'
                elif current_value == pin_off: pin_value = 'off'
                else: pin_value = "? {0} {1}".format(current_value,current_value.__class__)
                print(("{0:9}{1:25}{2:8}{3:4}={4}".format(device,pin_name,pin_address,pin_value,current_value)))
    # The following have their help in the parent class
    def do_status(self,args):
        self.status(verbose=True) # Broker Status
        lines = []
        if not self.obj.initialized:
            lines.append("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
        elif not self.obj.instr_connected:
            lines.append("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
        else:
            loadCurrent = (float(self.obj.load_current_ADC.value) - self.obj.LOAD_CURRENT_OFFSET) * self.obj.LOAD_CURRENT_MULTIPLIER
            chargeCurrent = (float(self.obj.charge_current_ADC.value) - self.obj.CHARGE_CURRENT_OFFSET) * self.obj.CHARGE_CURRENT_MULTIPLIER
            humidity = (float(self.obj.humidity_ADC.value / 5) - 0.16) / .0062 # at 25 DegC # OR get_values? RYAN
            lines.append("AI0 Voltage: {0:5.3} volts".format(float(self.obj.voltage_ADC.value) * self.obj.VOLTAGE_MULTIPLIER))
            lines.append("AI1 Load Current: {0:5.3} amps".format(loadCurrent))
            lines.append("AI2 Charge Current: {0:5.3} amps".format(chargeCurrent))
            lines.append("AI3 Enclosure Humidity: {0:5.3} %".format(humidity))
        for line in lines:
            print(("|    {line:74}|".format(line=line)))
        print(("-")*80)
    def do_report(self,args):
        aliases = self.obj.config.get(self.obj.BROKER_NAME,{}).get('aliases',{})
        for param,alias in aliases.items():
            print(("{0} is {1}".format(alias,param)))
        print((self.report(para_only=False)))
    def do_console(self,args):
        print("AIO broker has no console")
    # Aliases
class WindConsole(_BrokerConsole):
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,
                                console_name = self.__class__.__name__,
                                obj='wind', **kwargs)
        self.prompt = "AVP wind> "
        self.setup_intro() #self.intro  = "AVP wind sub-console. enter 'x' to return to main console"
        #self.obj.has_token = False
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP wind sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        
        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Get a report of all parameters and their values".format(cmd='report')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get wind broker status'.format(cmd='status')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Suspend broker - instrument communications.'.format(cmd='suspend')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Connect directoy to instrument. Must be suspended.'.format(cmd='console')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Resume broker - instrument communications.'.format(cmd='resume')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line
    # The following have their help in the parent class
    def do_status(self,args):
        self.status(verbose=True) # Broker Status
        lines = []
        if self.obj.initialized == False:
            lines.append("{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
        elif self.obj.instr_connected == False:
            lines.append("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
        elif self.obj.wind_speed.value == None:
            lines.append("{0} has no wind speed data".format(self.obj.BROKER_NAME))
        else:
            lines.append('Wind speed is {spd:.2f}{w_units} ({kn:.1f} knots) from {dir}{deg}'.format(
                          spd=self.obj.wind_speed.value,
                          kn=self.obj.wind_speed.value * self.obj.MPS_TO_KNOTS,
                          w_units=self.obj.wind_speed.units,
                          dir=self.obj.wind_direction.value,
                          deg=chr(176)))
        for line in lines:
            print("|    {line:74}|".format(line=line))
        print("-"*80)
    def do_console(self,args):
        if self.obj.suspended is False:
            print("Instrument must be suspended before console communications may be started.")
        else:
            eol = "\x0d\x0a"
            self.direct_connect(eol,'RW')
    # Aliases

class PowerMonConsole(_BrokerConsole):
    def __init__(self,context,**kwargs):
        _BrokerConsole.__init__(self,context,console_name = self.__class__.__name__,obj='powermon', **kwargs)
        self.prompt = "AVP power> "
        self.setup_intro() #self.intro  = "AVP Power Monitoring sub-console. enter 'x' to return to main console"
    def setup_intro(self):
        # Set up intro block of text.
        self.intro  = (80*"-") + CR
        line = "AVP power monitoring sub-console."
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)
        line = '' # Blank Line
        self.intro += "|{0:^78}|{cr}".format(line,cr=CR)

        line = "These are some common commands ('help <command>' for usage):"
        self.intro += "|    {0:<74}|{cr}".format(line,cr=CR)
        line = "{cmd:<10}- Get a report of all parameters and their values".format(cmd='report')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Get power broker status'.format(cmd='status')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Connect directly to instrument. Must be suspended.'.format(cmd='console')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = '{cmd:<10}- Return to main menu.'.format(cmd='exit|x')
        self.intro += "|        {0:<70}|{cr}".format(line,cr=CR)
        line = (80*"-") + CR # Lower Border
        self.intro += line

    def do_status(self, args):
        self.status(verbose=True)  # Broker Status
        lines = []
        if self.obj.initialized == False:
            lines.append(
                "{0} has not been initialized. Can not get further status information".format(self.obj.BROKER_NAME))
        elif self.obj.instr_connected == False:
            lines.append("{0} is not connected. Can not get further status information".format(self.obj.BROKER_NAME))
        else:
            lines.append('Meed to have some data here'.format())
        for line in lines:
            print(("|    {line:74}|".format(line=line)))
        print(("-") * 80)


    def do_console(self, args):
        if self.obj.suspended is False:
            print()
            "Instrument must be suspended before console communications may be started."
        else:
            eol = "\x0d\x0a"
            self.direct_connect(eol, 'RW')


# Aliases
def null(*doesnt_matter):
    return 0

def main(config_obj, cl_options):
    logger = logging.getLogger('')
    if not cl_options.debug_mode:
        logger.setLevel(logging.INFO)
    else:
        print(cl_options)
    fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=fmt)
    dbh = avp_db.DB_LogHandler(config_obj)
    dbh.setLevel(logging.DEBUG)
    logger.addHandler(dbh)
    avp_util.verbinit(cl_options) # Define verbose()
    program_name = 'avp_console'
    context = avp_util.AVPContext(config_obj, startup=['aio'], program_name=program_name, debug_mode=cl_options.debug_mode) # Set up console context
    con = MainConsole(context, program_name=program_name, debug_mode=cl_options.debug_mode) # Instantiate main Console object
    con.cmdloop() # Start console
    context.shutdown('all')

if __name__ == '__main__':
    cloptions,config = avp_util.get_config(option_set='console') # parse command Line options
    main(config,cloptions)

def start(self):
    from configobj import ConfigObj
    config_obj = ConfigObj(infile='/home/avp/python/{hostname}_avp.ini'.format(hostname=socket.gethostname()),raise_errors=True)
    class CLo:
        debug_mode = False
        verbose = True
    cl_options = CLo()
    main(config_obj,cl_options)
