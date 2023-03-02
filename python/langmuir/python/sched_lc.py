'''
Takes care of scheduling and recording Langmuir pictures
'''

#built in
from configobj import ConfigObj
import datetime as dt
import logging
import sys
import time
#3rd party
#import psycopg2
# Custom. May need to set PATH
import avpcam_settings as s
sys.path.append(s.AVP_PATH)
import avp_db
from avp_broker import Y32500Broker as WindBroker
import avpcamera # langmuir camera control stuff

db = False # debug mode
config = ConfigObj(infile=s.CONFIG_FILE,raise_errors=True)


# Some of this may be unnecessary in the future if the logger functionality can be moved
# to a lower level, perhaps in avp_broker?
LOG_FORMAT="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger('sched_lc')
dbh = avp_db.DB_LogHandler(config)
if db is True:
    dbh.setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
logger.addHandler(dbh)
        
        
# Schedule loop
while True:
    skip_pic = False
    new_picture = None
    # Check time
    now =  dt.datetime.now().time()
    if now < s.START_TIME or now > s.END_TIME:
        logger.debug('Time out of Range')
        # We should sleep until s.START_TIME
        time.sleep(s.FREQUENCY.seconds)
        continue # Since we have yet to instantiate D40
    # We need a camera for the next few checks, so instantiate it
    reload(s) # In case settings have changed.
    # Set up stuff for wind broker.
    wind = WindBroker(config)
    avpcamera.reset_port(db=False)
    D40 = avpcamera.Camera(config=config,wind=wind,db=False)
    # Check wind
    aw_spd = wind.average_wind_speed.value
    if aw_spd is None:
        skip_pic = True
        print "No wind data, skipping picture"
    if aw_spd < avpcamera.s.MINWIND or aw_spd > avpcamera.s.MAXWIND:
        print "Wind speed of {0} m/s is out of range {1} - {2}".format(aw_spd,avpcamera.s.MINWIND,avpcamera.s.MAXWIND)
        skip_pic = True
    # Set ISO and see if we have enough light.
    if skip_pic is False:
        iso_result = D40.set_iso(db=False)
        if iso_result is None:
            # Too dark
            print "Too dark or Error setting ISO {0}".format(D40.get_ais(db=False))
            skip_pic = True
        elif True: # db=True: # RYAN
            print "Aperture is {ape}, ISO is {iso} Shutter Speed is {spd}".format(
                    ape=iso_result.get('A','Unknown'),
                    iso=iso_result.get('I','Unknown'),
                    spd=iso_result.get('S','Unknown'))
    if skip_pic is True:
        D40.shutdown()
    else:
        now = dt.datetime.now()
        new_picture = D40.take_picture(imgquality=2,log_exif=True,db=False)
        if new_picture is not None:
            # Now transfer the picture
            remotepath = avpcamera.s.REMOTE_PATH
            remotepath += avpcamera.s.PATHS.get(new_picture.imgquality,'') # usually adds 'JPEG/'
            remotepath += "{year}{month:02}/".format(year=now.year,month=now.month)
            avpcamera.sftp_file(new_picture.path,
                new_picture.file,
                avpcamera.s.IMAGE_HOST,
                username=avpcamera.s.IMAGE_HOST_USER,
                priv_key=avpcamera.s.PRIV_KEY,
                remotepath=remotepath,remove_file=True)
        D40.shutdown()
        
    # Now sleep
    if new_picture is not None:
        sleep_time = s.FREQUENCY.seconds
    else:
        sleep_time = 60
    print "Cycle Done, sleeping {0} seconds".format(sleep_time)
    time.sleep(sleep_time)