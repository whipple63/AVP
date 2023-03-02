import datetime as dt
# Scheduler variables
START_TIME = dt.time(6,00)
END_TIME = dt.time(18,00)
FREQUENCY = dt.timedelta(minutes=15)
# Misc
MINWIND = 2.5 #m/s
MAXWIND = 99 #m/s


# Global constants
AVP_PATH = '/home/avp/py/AVP3/src/'
HOME_PATH = '/data/langmuir/'
IMAGEPATH = '{0}images/'.format(HOME_PATH)
JPEGPATH = 'JPEG/'
RAWPATH = 'RAW/'
PPMPATH = 'PPM/'

# Dictionary to look up where to save file based on file type
PATHS = {0:JPEGPATH, # 0 JPEG Basic
         1:JPEGPATH, # 1 JPEG Normal
         2:JPEGPATH, # 2 JPEG Fine
         3:RAWPATH,  # 3 NEF (Raw)
         4:RAWPATH}  # 4 NEF+Basic
FILE_INFO = {0:{'format':'jpg','extension':'b.jpeg'}, # 0 JPEG Basic
             1:{'format':'jpg','extension':'n.jpeg'}, # 1 JPEG Normal
             2:{'format':'jpg','extension':'f.jpeg'}, # 2 JPEG Fine
             3:{'format':'nef','extension':'nef'},    # 3 NEF (Raw)
             4:{'format':'nef','extension':'j.nef'}}  # 4 NEF+Basic
         
PRIV_KEY = '{0}.ssh/langmuir_key'.format(HOME_PATH)
IMAGE_HOST = 'wave.ims.unc.edu'
IMAGE_HOST_USER = 'avp'
REMOTE_PATH = '/home2/avp/Camera_Images/'

GPHOTO2 = '/usr/bin/gphoto2'
DCRAW = '/usr/bin/dcraw'
CONFIG_FILE = AVP_PATH + 'avp.ini'
FILE_NAME_FORMAT = '%Y%m%d_%H%M%S'


# Camera Specific
CAMERA = "'Nikon DSC D40 (PTP mode)'"
SENSOR_WIDTH = 24.0 #24mm for Nikon DX
PORT = 'usb:'
CAMERA_SKEW = 180 # this is the difference between the platform heading and the camera heading in degrees
MAX_EXPTIME = (1.0 / 30.0)
ISO_INDEX = {0: 200, 1: '400', 2: '800', 3: '1600', 4: '3200'}
MAX_ISO = 1600
APERTURE_INDEX = {0: 'f/3.5', 1: ' f/22', 2: 'f/4.5', 3: 'f/5', 4: 'f/5.6', 5: 'f/6.3', 6: 'f/7.1', 7: 'f/8', 8: 'f/9', 9: 'f/10'}

# Colors

red       = '#ff0000'
darkred   = '#880000'
green     = '#0000ff'
darkgreen = '#000088'
black     = '#000000'
font = "/usr/share/fonts/truetype/ttf-dejavu/DejaVuSansMono.ttf"

class StandardResponses:
    ''' Response codes from camera. Not used yet.
    '''
    UNDEFINED                               = 0x2000
    OK                                      = 0x2001
    GENERAL_ERROR                           = 0x2002
    SESSION_NOT_OPEN                        = 0x2003
    INVALID_TRANSACTION_ID                  = 0x2004
    OPERATION_NOT_SUPPORTED                 = 0x2005
    PARAMETER_NOT_SUPPORTED                 = 0x2006
    INCOMPLETE_TRANSFER                     = 0x2007
    INVALID_STORAGE_ID                      = 0x2008
    INVALID_OBJECT_HANDLE                   = 0x2009
    DEVICE_PROP_NOT_SUPPORTED               = 0x200a
    INVALID_OBJECT_FORMAT_CODE              = 0x200b
    STORE_FULL                              = 0x200c
    OBJECT_WRITE_PROTECTED                  = 0x200d
    STORE_READ_ONLY                         = 0x200e
    ACCESS_DENIED                           = 0x200f
    NO_THUMBNAIL_PRESENT                    = 0x2010
    SELF_TEST_FAILED                        = 0x2011
    PARTIAL_DELETION                        = 0x2012
    STORE_NOT_AVAILABLE                     = 0x2013
    SPECIFICATION_BY_FORMAT_NOT_SUPPORTED   = 0x2014
    NO_VALID_OBJECT_INFO                    = 0x2015
    INVALID_CODE_FORMAT                     = 0x2016
    UNKNOWN_VENDOR_CODE                     = 0x2017
    CAPTURE_ALREADY_TERMINATED              = 0x2018
    DEVICE_BUSY                             = 0x2019
    INVALID_PARENT_OBJECT                   = 0x201a
    INVALID_DEVICE_PROP_FORMAT              = 0x201b
    INVALID_DEVICE_PROP_VALUE               = 0x201c
    INVALID_PARAMETER                       = 0x201d
    SESSION_ALREADY_OPEN                    = 0x201e
    TRANSACTION_CANCELLED                   = 0x201f
    SPECIFICATION_OF_DESTINATION_UNSUPPORTED= 0x2020
