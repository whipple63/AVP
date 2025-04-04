# AVP Utilities

#Built in Modules

import logging
import os
import pprint
import socket
import sys
import threading
import time
#Installed Modules
from configobj import ConfigObj
from optparse import OptionParser
#Custom Modules
import avp_broker



class AVPContext(object):
    ''' Provides a context object which contains some or all the device objects
    associated with the avp
    Public Methods: verbose, startup, shutdown
    Instance Variables: debug_mode
    '''
    
    # This is nested tuples and not a dictionary because the order is important.
    # This will become dynamic based upon config.ini
    # Add adcp later
    BROKER_WAIT_TIME = 10 #Time to wait after failed broker client startup attemt to try again
                           
    def __init__(self,config,program_name=__name__,startup='all',check_defaults=True,**kwargs):
        '''
        This object provides a context for one or more broker objects and allows 
        the suite of brokers to be instantiated, passed around, and terminated more easily.
        Arguments:
        config          -- ConfigObj dictionary
        program_name    -- Name oof program instantiating object. Used for identifying token requests.
        startup         -- list of brokers to start. Defaults to ['all']
        check_defaults  -- Some brokers have default settings which can be set on startup. The downside of this is that it will take the token away from anyone else who is using it.
        Keyword Arguments:
        debug_mode      -- [True|False]
        '''
        self.config = config
        self.debug_mode = kwargs.get('debug_mode',False)
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.debug_mode is False:
            self.logger.setLevel(logging.INFO)
        token_name = "AVPContext"
        self.brokers = []
        self.program_name = program_name + ".{0}".format(self.__class__.__name__)
        # Set up broker_config will replace (BROKER_CLASSES)
        self.broker_config = [] # needs to be ordered, so no dictionary
        # New stuff
        for key,value in list(self.config.items()):
            # These aren't all brokers so check:
            try:
                '''
                instance_name
                module
                broker_class
                '''
                (instance_name,broker_class,module) = value['BROKER_CLIENT']
                self.broker_config.append({'instance':instance_name,'module':module,'broker_class':broker_class})
            except KeyError:
                # Wasn't a broker key
                pass
        self.startup(startup=startup,check_defaults=check_defaults,**kwargs)
    def verbose(self,message):
        print(message)
    def startup(self,startup='all',check_defaults=True,**kwargs):
        '''
        Arguments:
        startup         -- List of brokers to start.
        check_defaults  -- Some brokers have default settings which can be set on startup. The downside of this is that it will take the token away from anyone else who is using it.
        '''
        try:
            startup_l = startup.split() #Convert to a list if a string....
        except:
            startup_l = startup #Otherwise just assume it is a list
        self.debug_mode = kwargs.get('debug_mode',False)
        # Start up brokers
        for info_set in self.broker_config:
            # Each info_set is a dictionary
            broker = info_set['instance']
            broker_class = info_set['broker_class']
            if broker in startup_l or 'all' in startup_l:
                # If you are having problems, get rid of this try temporarily as it seems to hide a lot
                try:
                    self.start_broker(broker,broker_class,check_defaults=check_defaults)
                except AttributeError as e:
                    # This happens if the broker is not ready for the client
                    self.logger.info("Could not start {0}. Waiting {1}s to try again.{2}".format(broker,self.BROKER_WAIT_TIME,e))
                    time.sleep(self.BROKER_WAIT_TIME)
                    try:
                        self.start_broker(broker,broker_class,check_defaults=check_defaults)
                    except AttributeError as e:
                        self.logger.error("Could not start {broker} broker client. {e}".format(broker=broker,e=e))
        return self.brokers
    def start_broker(self,broker_name,broker_class,check_defaults=False):
        if broker_name in self.brokers:
            self.logger.debug("Already have {broker} broker client".format(broker=broker_name))
        elif broker_class is not None:
            self.logger.debug("Starting up {broker} broker client".format(broker=broker_name))
            broker_class = getattr(avp_broker,broker_class)
            # Instantiate new broker!
            setattr(self, broker_name,
                broker_class(self.config,program_name=self.program_name,check_defaults=check_defaults,debug_mode=self.debug_mode))
            self.brokers.append(broker_name)
            if getattr(self,broker_name).connected() is False:
                # We were unable to connect, so broker is crippled. Do some cleanup
                self.logger.warning('{0} was unable to connect to broker. Shutting down instance'.format(broker_name))
                self.shutdown(shutdown=broker_name)
        else:
            #broker not enabled
            pass
    def shutdown(self,shutdown=''):
        try:
            args_l = shutdown.split() #Convert to a list if a string....
        except:
            args_l = shutdown #Otherwise just assume it is a list
        self.logger.debug("Shutting down {0}".format(shutdown))
        for info_set in reversed(self.broker_config):
            instance_name = info_set['instance']
            if instance_name in args_l or 'all' in args_l:
                if hasattr(self,instance_name):
                    this_obj = getattr(self,instance_name)
                    this_obj.unsubscribe_all()
                    threading.Thread(target=this_obj.disconnect).start()
                    try:
                        self.brokers.remove(instance_name)
                    except:
                        pass
def get_config(option_set=None):
    ''' Get command line options

    option_set -- ([avp_cast,][,console,])
    '''
    parser = OptionParser("usage: %prog [options] arg1 arg2")
    parser.set_defaults(configfile='./{hostname}_avp.ini'.format(hostname=socket.gethostname()),verbose=False,debug_mode=False)
    parser.add_option("-c", "--config", action="store", type="string",
                      dest="configfile",
                      help="Use config FILE (default = $default)")
    parser.add_option("-v", "--verbose",
                      action="store_true", dest="verbose",
                      help="print status messages to stdout")
    parser.add_option("-d", "--db","--debug",
                      action="store_true", dest="debug_mode",
                      help="start console in debug_mode")
    if option_set:
        if 'avp_cast' in option_set:
            parser.add_option("-t", "--time", action="store", type="string",
                                dest="cast_time",
                                help="Cast Time <%Y%m%d%H%M%S>")
            parser.add_option("--depth",action="store_true", type='float',
                                dest="cast_depth",
                              help="Depth to cast to in meters")
            parser.add_option("--pd",action="store_true", dest="park_depth",
                              help="Depth at which to park. ")
            parser.add_option("--lisst",action="store_true", dest="lisst_cast",
                              help="is this a LIST cast? <True|False>")
            parser.add_option("--isco",action="store_true", dest="isco_cast",
                              help="is this an ISCO cast? <True|False>")
        if 'console' in option_set:
            pass
        if 'sched' in option_set:
            pass
    (cloptions, clargs) = parser.parse_args()
    config_file = cloptions.configfile
    config = ConfigObj(infile=config_file,raise_errors=True)
    if cloptions.debug_mode: print("Using config file {0}".format(config_file))
    return cloptions,config
    
def check_hostname(hostname,**kwargs):
    ''' Checks to see if hostname is the same as localhost. If so, returns localhost, otherwise returns fully qualified name
    '''
    debug_mode = kwargs.get('debug_mode',False)
    result = socket.getfqdn()
    if hostname is result:
        hostname = 'localhost'
    elif debug_mode: print("host name info: {0}".format(result))
    return hostname

def traverse_tree(input_dict, desired_key=None):
    '''
    This function takes an input dictionary, usually nested, looks for the first instance of the desired key and returns its value.
    '''
    answer = None
    try:
        for key, value in list(input_dict.items()):
            answer = None
            if key == desired_key:
                return value
            elif value.__class__ is {}.__class__:
                answer = traverse_tree(value,desired_key)
                if answer: return answer
        return answer
    except AttributeError as e:
        print("Exception {0} in avp_util.traverse_tree, expecting dict and got {1}".format(e,input_dict))
        return input_dict
        
def print_dict(input_dict,tab_size=1,width=124):
    '''
    formats a dictionary so that nesting can more easily be seen.
    '''
    pp = pprint.PrettyPrinter(indent=tab_size,width=width)
    return pp.pformat(input_dict)
    #------------------------------------------------------OLD WAY BELOW
    '''
    result = ''
    sp = ' '
    def parser(this_dict,level=0):
        #print level
        result = ''
        for key,value in this_dict.iteritems():
            result += sp*level*tab_size + key
            if value.__class__ is {}.__class__: # value is a dict
                result += ":\r\n"
                result += parser(value,level + 1)
            else:
                result += ":{0}\r\n".format(value)
        
        return result
    return parser(input_dict)
    '''
    
def verbinit(cloptions=None):
    if cloptions.verbose:
        def verbose(message):
            print(message)
    else:
        def verbose(message):
            pass
    return verbose

def t_or_f(boolean,**kwargs):
    '''
    Takes a presumed boolean and returns True, False or None
    Often used with strings returned from java brokers which may not be formatted correctly
    '''
    debug_mode = kwargs.get('debug_mode',False)
    if debug_mode: print("Evaluated {0} as".format(boolean), end=' ')
    # First check the simple stuff...
    if boolean is True:
        if debug_mode: print(" boolean True")
        return True
    if boolean is False:
        if debug_mode: print(" boolean False")
        return False
    try: # Is is a String?
        if boolean.title() in ('False','F','No','N'):
            if debug_mode: print(" string False")
            return False
        elif boolean.title() in ('True','T','Yes','Y'):
            if debug_mode: print(" string True")
            return True
        elif boolean.title() in ('None'):
            if debug_mode: print(" string None")
            return None
    except Exception as e:
        if debug_mode: print(" not a string({0}), but a".format(e), end=' ')
        pass
    try: # Is is a Number?
        if float(boolean):
            if debug_mode: print(" Float True")
            return True
    except ValueError as e:
        pass
    except Exception as e:
        pass
    #print "{0} is None".format(boolean) # RYAN
    return None

def spawnDaemon (newDaemon, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'): 
    '''This forks the given process into a daemon. 
    The argumen newDaemon is given as arguments to os.execvp.
    The stdin, stdout, and stderr arguments are file names that 
    will be opened and be used to replace the standard file descriptors 
    in sys.stdin, sys.stdout, and sys.stderr. 
    These arguments are optional and default to /dev/null. 
    Note that stderr is opened unbuffered, so 
    if it shares a file with stdout then interleaved output 
    may not appear in the order that you expect. 
    
    References: 
        UNIX Programming FAQ 
            1.7 How do I get my program to act like a daemon? 
                http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16 
 
        Advanced Programming in the Unix Environment 
            W. Richard Stevens, 1992, Addison-Wesley, ISBN 0-201-56317-7. 
    ''' 
    
    '''
    Taking this check out so that the first arg can be sudo
    
    try: 
        statinfo = os.stat(newDaemon[0]) # see if we can stat the file
    except OSError as e:
        sys.stderr.write ("\nERROR, cannot stat file: %s (%d) %s\n\n" % (newDaemon[0], e.errno, e.strerror ) ) 
    '''
 
    # Do first fork. 
    try: 
        pid = os.fork() 
        if pid > 0: 
            os.waitpid(pid, 0)  # wait for the fork otherwise it will be left as a zombie.
            return       # This is where we return to the first parent. 
                         # The rest of the work is done by the children.
    except OSError as e:
        sys.stderr.write ("fork #1 failed: (%d) %s\n" % (e.errno, e.strerror)    ) 
        os._exit(1) 
 
    # Decouple from parent environment. 
    os.chdir("/") 
    os.umask(0) 
    os.setsid() 
 
    # Do second fork. 
    try: 
        pid = os.fork() 
        if pid > 0: 
            sys.exit(0) # Exit second parent. 
    except OSError as e:
        sys.stderr.write ("fork #2 failed: (%d) %s\n" % (e.errno, e.strerror)    ) 
        os._exit(1) 
 
    # Redirect standard file descriptors. 
    si = open(stdin, 'r') 
    so = open(stdout, 'a+') 
    #se = file(stderr, 'a+', 0) this is how it was for python2
    se = open(stderr, 'a+') 
    os.dup2(si.fileno(), sys.stdin.fileno()) 
    os.dup2(so.fileno(), sys.stdout.fileno()) 
    os.dup2(se.fileno(), sys.stderr.fileno()) 
    
    # Time to become whatever process we were meant to be
    try:
        os.execvp(newDaemon[0], newDaemon)
    except OSError as e:
        sys.stderr.write ("New daemon process unable to start: (%d) %s\n" % (e.errno, e.strerror)    ) 
        os._exit(1) 


def total_seconds(td):
    ''' Converts a timedelta to a float representing the number of seconds
    '''
    seconds_duration = (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10.0**6 #
    return seconds_duration
