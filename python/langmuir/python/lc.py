#!/usr/bin/python
''' Langmuir Camera control
    Creare Camera Object which can return photo objects
'''
from configobj import ConfigObj
from datetime import datetime
import logging
from math import atan,degrees
import os
import subprocess
import sys

# 3rd party
import paramiko
import PIL
import PIL.ExifTags
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont

# Custom
import avpcam_settings as s
sys.path.append(s.AVP_PATH)
import avp_broker
import avp_db

# Some globals
'''
HOME_PATH = '/data/langmuir/'
IMAGEPATH = '{0}images/'.format(HOME_PATH)
JPEGPATH = IMAGEPATH + 'JPEG/'
RAWPATH = IMAGEPATH + 'RAW/'
PPMPATH = IMAGEPATH + 'PPM/'
PATHS = {0:JPEGPATH, # 0 JPEG Basic
         1:JPEGPATH, # 1 JPEG Normal
         2:JPEGPATH, # 2 JPEG Fine
         3:RAWPATH,  # 3 NEF (Raw)
         4:RAWPATH}  # 4 NEF+Basic
GPHOTO2 = '/usr/bin/gphoto2'
DCRAW = '/usr/bin/dcraw'
CONFIG_FILE = AVP_PATH + '/avp.ini'
FILE_NAME_FORMAT = '%Y%m%d_%H%M%S'
CAMERA = "'Nikon DSC D40 (PTP mode)'"
PORT = 'usb:'
CAMERA_SKEW = -10 # this is the difference between the platform heading and the camera heading
SENSOR_WIDTH = 24.0 #mm
'''
     
class Camera(object):
    ''' Camera object
    '''
    FILE_INFO = {0:{'format':'jpg','extension':'b.jpeg'}, # 0 JPEG Basic
                 1:{'format':'jpg','extension':'n.jpeg'}, # 1 JPEG Normal
                 2:{'format':'jpg','extension':'f.jpeg'}, # 2 JPEG Fine
                 3:{'format':'nef','extension':'nef'},    # 3 NEF (Raw)
                 4:{'format':'nef','extension':'j.nef'}}  # 4 NEF+Basic
    def __init__(self):
        self.config_dict = {'settings':{}, 'imgsettings':{}, 'capturesettings':{}}
        # Some of this may be unnecessary in the future if the logger functionality can be moved to a lower level, perhaps in avp_broker?
        logger = logging.getLogger('')
        config = ConfigObj(infile=s.CONFIG_FILE,raise_errors=True)
        FORMAT="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=FORMAT)
        dbh = avp_db.DB_LogHandler(config)
        dbh.setLevel(logging.DEBUG)
        logger.addHandler(dbh)
        # Get configuration
        self.list_config()
        # Set up stuff for wind broker.
        self.wind = avp_broker.Y32500Broker(config)
        
            
    def shutdown(self):
        self.wind.unsubscribe_all()
        self.wind.disconnect()
    def __del__(self):
        self.shutdown()
    
    def list_config(self,db=False):
        command = s.GPHOTO2 + ' --list-config '
        result = do_subprocess(command,shell=False,db=db)
        #commandl = command.split()
        #result = subprocess.Popen(commandl,shell=False,
        #                            cwd = '/tmp',
        #                            stdout=subprocess.PIPE,
        #                            stderr=subprocess.PIPE)
        #result = result.communicate()[0]
        # Now put result in a dictionary, with keys settings, imgsettings, and capturesettings
        for line in result.splitlines():
            line2 = line[6:]
            line_tup = line2.partition('/')
            key = line_tup[0]
            val = line_tup[2]
            try:
                self.config_dict[key][val] = None
            except KeyError,e:
                print e,key,val
        
    def get_all_config(self):
        for data_group, config_type in self.config_dict.items():
            for data_item in config_type.keys():
                print data_item
                # Get data from camera
                result = self.get_config(data_group,data_item)
                # Parse it
                rdict = self.parse_config_results(result)
                # Save it
                self.config_dict[data_group][data_item] = rdict
                
    def parse_config_result(self,get_config_result,db=False):
        ''' Parse result of --get-config and return in in a dictionary
        '''
        rdict = {}
        c_type = None
        for line in get_config_result.splitlines():
            if line.startswith('Label') is True:
                rdict['setting_label'] = line[6:] #Everything after the :
                c_type = None
            elif line.startswith('Type') is True:
                c_type = line[6:]
                rdict['setting_type'] = c_type
            elif line.startswith('Current') is True:
                rdict['setting_current'] = line[9:]
            else:
                # Now handle type specific items
                if c_type == 'RADIO':
                    # Has {'Choice':{1:...}}
                    if line.startswith('Choice') is True:
                        #if db is True: print "Found choice {0}".format(line)
                        if 'setting_choices' not in rdict.keys():
                            rdict['setting_choices'] = {}
                        choice_no = int(line[7:9])
                        rdict['setting_choices'][choice_no] = line[10:]
                    else:
                        print 'Unknown e {0}'.format(line)
                elif c_type == 'TEXT':
                    #should never get here
                    print 'Unknown a {0}'.format(line)
                elif c_type == 'DATE':
                    if line.startswith('Printable') is True:
                        rdict['Printable'] = line[10:]
                    else:
                        print 'Unknown b {0}'.format(line)
                elif c_type == 'TOGGLE':
                    print 'Unknown c {0}'.format(line)
                elif c_type == 'RANGE':
                    # Don't know what these will be
                    linet = line.partition(':')
                    rdict[linet[0]] = linet[2]
                else:
                    print 'Unknown d {0} >{1}<'.format(line,c_type)
        # For RADIO type, we add a numeric setting_value key
        if rdict.get('setting_type',None) == 'RADIO':
            if db is True: print "Attempting to get current RADIO value from {0}".format(rdict)
            rdict['setting_value'] = None # default
            for choice_value,choice in rdict['setting_choices'].items():
                if db is True: print "{0} <--> {1}".format(choice,rdict['setting_current']),
                if choice == rdict['setting_current']:
                    rdict['setting_value'] = choice_value
                    if db is True: print ' match'
                    break
                elif db is True: print ' No match'
                
                    
        return rdict

    def get_config(self,data_group,data_item,db=False):
        ''' Get configuration data for a single value from camera
        '''
        config_item = '{0}/{1}'.format(data_group,data_item)
        command = s.GPHOTO2 + ' --get-config {0}'.format(config_item)
        result =  do_subprocess(command,shell=False,cwd='/tmp')
        if db: print result
        self.config_dict[data_group][data_item] = result
        return result
        
    def set_config(self,data_group,data_item,index,db=False):
        ''' Sets a configuration value for enries with an index
        '''
        config_entry = 'main/{0}/{1}'.format(data_group,data_item)
        command = s.GPHOTO2 + ' --set-config {0}={1}'.format(config_entry,index)
        return do_subprocess(command,shell=False,db=db)
        
    def set_imgquality(self,mode=2,db=False):
        ''' Sets camera mode
        imgsettings/imgquality
            Choice: 0 JPEG Basic
            Choice: 1 JPEG Normal
            Choice: 2 JPEG Fine
            Choice: 3 NEF (Raw)
            Choice: 4 NEF+Basic
        '''
        min = 0
        max = 4
        try:
            if mode >= min and mode <= max:
                return self.set_config('imgsettings','imgquality',mode,db=db)
            else:
                print '{0} is out of rannge {1} - {2}'.format(mode,min,max)
        except Exception,e:
            return 'Exception in set_imgquality: {0}'.format(e)
        
    def set_imgquality_NEF(self):
        ''' Sets camera mode to RAW (nef)
        '''
        return self.set_imgquality(mode=3,db=True)
       
    def set_imgquality_JPEG_fine(self):
        ''' Sets image quality to JPEG fine
        '''
        return self.set_imgquality(mode=2,db=True)

    def get_imgquality(self,db=False):
        ''' Query camera as to its image quality 'imgsettings'
        '''
        data_group = 'imgsettings'
        data_item = 'imgquality'
        # Get data from camera
        result = self.get_config(data_group,data_item,db=db)
        # Parse it
        rdict = self.parse_config_result(result,db=db)
        # Save it
        self.config_dict[data_group][data_item] = rdict
        # Now return the value
        try:
            return self.config_dict[data_group][data_item]['setting_value']
        except KeyError,e:
            if db is True:
                print 'Error getting setting_value from {0}'.format(self.config_dict[data_group][data_item])
            return None
        
    def take_picture(self,outpath=None,shell=False,imgquality=2,db=False):
        ''' Takes a picture
        Needs to notify if camera didn't respond
        returns gphoot2 stdout/stderr and file name
        '''
        camera_imgquality = self.get_imgquality(db=db)
        if imgquality != camera_imgquality:
            if camera_imgquality == None:
                print "Unable to get image quality, possible communications failure"
                return None
            else:
                print "Camera imgquality {0} doesn't match requested {1}".format(camera_imgquality,imgquality)
                self.set_imgquality(mode=imgquality,db=db)
        if outpath is None:
            outpath = s.PATHS[imgquality] 
        outfile = datetime.now().strftime(s.FILE_NAME_FORMAT)
        outfile = '{0}.{1}'.format(outfile, self.FILE_INFO[imgquality]['extension'])
        command = [s.GPHOTO2]
        if db is True:
            command.extend(['--debug', '--debug-logfile', '{0}_debug.txt'.format(outfile)])
        command.extend(['--camera', s.CAMERA])
        command.extend(['--port',s.PORT])
        command.append('--capture-image-and-download')
        command.extend(['--filename','{0}'.format(outfile)])
        if db is True:
            print "Command: {0}".format(command)
            print ' '.join(command)
        if shell is True:
            command = ' '.join(command) # If Shell=True, we want a string
        os.umask(0117)
        
        w_speed_ms = self.wind.wind_speed.value
        w_dir = self.wind.wind_direction.value
        c_dir = self.wind.compass_direction.value
        result = do_subprocess(command,shell=shell,cwd=outpath,db=db)
        '''result = subprocess.Popen(command,shell=shell,
                                    cwd = outpath,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        result = result.communicate()[0]'''
        print result
        new_photo = Photo(file=outfile,path=outpath,type=self.FILE_INFO[imgquality]['format'],
                          w_speed_ms=w_speed_ms, w_dir=w_dir, c_dir=c_dir,
                          instance_note=result,db=db)
        return new_photo
class Photo(object):
    '''
    Note, at 18mm, field of view os 66.721 degrees
    '''
    def __init__(self,file,path,type='jpg',w_speed_ms=None,w_dir=None,c_dir=None,instance_note=None,db=False):
        self.file = file
        self.path = path
        self.path_file = path + file
        self.exif_data = {}
        self.get_exif(db=db)
        self.interpret_exif(db=db)
        self.w_speed_ms = w_speed_ms
        self.w_dir = w_dir
        self.c_dir = c_dir
        self.instance_note = instance_note
        print 'Raw focal length {0}'.format(self.focal_length)
        focal_length = self.focal_length[0]/10.0
        fov = degrees(2 * atan( s.SENSOR_WIDTH/(2 * focal_length) ))
        print 'Calculated focal length {0}'.format(focal_length)
        print 'Calculated field of view {0}'.format(fov)
        self.FOV = 66.7
        self.image = PIL.Image.open(self.path + self.file)
        print "Image info {0}".format(self.image.info.get('exif',{}).keys())
        self.annotate(db=db)
        self.save_image()
    def get_exif(self,db=False):
        ''' Get the exif data from a JPEG or PPM files. NEF not supported. Convert to PPM first.
        '''
        i = PIL.Image.open(self.path_file)
        info = i._getexif()
        for tag, value in info.items():
            decoded = PIL.ExifTags.TAGS.get(tag, tag)
            self.exif_data[decoded] = value
    def interpret_exif(self,db=False):
        # Move exif data we are interested in to class attributes
        self.ISO = self.exif_data.get('ISOSpeedRatings',None)
        self.dt_str = self.exif_data.get('DateTime',None)
        self.metering_mode = self.exif_data.get('MeteringMode',None)
        self.x_resolution = self.exif_data.get('XResolution',None)
        self.exposure_program = self.exif_data.get('ExposureProgram',None)
        self.color_space = self.exif_data.get('ColorSpace',None)
        self.focal_length = self.exif_data.get('FocalLength',None)
        self.exposure_time = self.exif_data.get('ExposureTime',None)
        self.max_aperture_value = self.exif_data.get('MaxApertureValue',None)
        self.y_resolution = self.exif_data.get('YResolution',None)
    def nef_to_ppm(self,outpath=None,thumbnail=False,tiff=False,db=False):
        ''' Converts a NEF file to a PPM and returns a new PPM Photo Object
        '''
        valid_file_types = ('nef',)
        if self.file_type not in valid_file_types:
            print 'This method does not convert {0} files'.format(self.file_type)
            return None
        if outpath is None:
            outpath = PPMPATH
        outfile = self.file[:(len(infile) - 4)] + '.ppm' #
        arguments = ' -c ' # output to stdout
        if tiff is True:
            arguments += ' -T '
        command = s.DCRAW + '{0} {1}{2} > {3}/{4}'.format(arguments,self.path,self.file,outpath,outfile)
        result = do_subprocess(command,shell=True,cwd=outpath,db=db)
        '''result = subprocess.Popen(command,shell=True,
                                    cwd = outpath,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
        result = result.communicate()[0]'''
        new_photo = Photo(outfile,outpath,'ppm')
        return new_photo
    def annotate(self,db=False):
        ''' Add annotations to picture
        '''
        if self.c_dir is None:
            print "Can not mark North when compass direction is unknown"
            return 
        LINE_LEN = .25 # This is the percentage of image height which line should come down from the top
        TICK_LEN = .05
        font_size = 30
        red       = '#ff0000'
        darkred   = '#880000'
        green     = '#0000ff'
        darkgreen = '#000088'
        black     = '#000000'
        font = PIL.ImageFont.truetype("/usr/share/fonts/truetype/ttf-dejavu/DejaVuSansMono.ttf",font_size)
        spacing = 10
        FOV_height = font_size
        compass_height = FOV_height + spacing + font_size
        w_dir_height = compass_height + spacing + (font_size * 2)
        w_spd_height = w_dir_height + spacing + font_size
        draw = PIL.ImageDraw.Draw(self.image)
        # First we want to make North and wind direction. This is complicated by the break in degrees.
        self.FOV = 66.7 # we want to draw a line at north. 
        image_width = self.image.size[0]
        # record these incase they change during analysis
        compass = self.c_dir 
        wind_dir = self.w_dir
        deg_left = compass - (self.FOV/2.0) + s.CAMERA_SKEW
        deg_right = compass + (self.FOV/2.0) + s.CAMERA_SKEW
        if deg_left < 0:
            deg_left += 360.0
        if deg_right > 360.0:
            deg_right -= 360.0
        draw.text((10,FOV_height),'{0}{1}'.format(deg_left,chr(176)),font=font,fill=black)
        draw.text((self.image.size[0] - 150,FOV_height),'{0}{1}'.format(deg_right,chr(176)),font=font,fill=black)
        draw.text((10,compass_height),'AVP Heading = {0}{1} mag.'.format(compass,chr(176)),font=font,fill=red)
        # Draw Ticks and North marker
        tick = round(deg_left,-1)
        if tick < deg_left: # If the first tick is off screen
            tick += 10
        if tick >= 360: # When we get to North
            tick -= 360
        ticks_done = False
        while ticks_done is False:
            if db is True: print 'tick: {0}'.format(tick)
            if tick > deg_left:
                line_loc = ((tick - deg_left)/self.FOV) * image_width
            else:
                line_loc = ((tick - deg_left + 360)/self.FOV) * image_width
            line_start = (line_loc,0)
            if tick == 0: # North
                line_end = (line_loc,self.image.size[1] * LINE_LEN)
                tick_color = red
                tick_label = 'N'
            else: # plain tick
                line_end = (line_loc,self.image.size[1] * TICK_LEN)
                tick_color = darkred
                tick_label = '{0:0}{1}'.format(tick,chr(176))
            draw.line([line_start,line_end],fill=tick_color)
            draw.text((line_loc,line_end[1]),tick_label,font=font,fill=tick_color)
            tick += 10
            if tick >= 360:
                tick -= 360
            if (deg_left > deg_right) and (tick > deg_right) and (tick < deg_left): # contains North
                ticks_done = True
            elif (deg_left < deg_right) and (tick > deg_right):
                ticks_done = True
        if wind_dir is None:
            print "Can not mark wind when direction is unknown"
        else:
            draw.text((10,w_dir_height),'Wind Direction: {0}{1} mag'.format(wind_dir,chr(176)),font=font,fill=green)
            draw.text((10,w_spd_height),'Wind Speed: {0:.1f} m/s'.format(self.w_speed_ms),font=font,fill=green)
            wind_in_view = None
            if deg_right < deg_left: # North is in view
                if wind_dir <= deg_right or wind_dir >= deg_left:
                    wind_in_view = 1
            elif wind_dir <= deg_right and wind_dir >= deg_left: # North not in view
                    wind_in_view = 1
            # Now check reciprocal
            if wind_in_view == None:
                if db is True: print "Now looking for wind reciprocal from {0}".format(wind_dir),
                wind_dir = wind_dir + 180.0
                if wind_dir >= 360.0:
                    wind_dir -= 360.0
                if db is True: print " which is {0}".format(wind_dir)
                if deg_right < deg_left: # North is in view
                    if wind_dir <= deg_right or wind_dir >= deg_left:
                        wind_in_view = 0
                elif wind_dir <= deg_right and wind_dir >= deg_left:
                        wind_in_view = 0
            if wind_in_view is not None:
                if db is True: print " which is {0}".format(wind_dir)
                #print "Compass is {0}, deg_left = {1}, image_width = {2}".format(compass,deg_left,image_width)
                if wind_dir < deg_right: # Not split
                    line_loc = ((deg_right - wind_dir)/self.FOV) * image_width
                else: # Split
                    line_loc = ((wind_dir - deg_left)/self.FOV) * image_width
                line_start = (line_loc,0)
                line_end = (line_loc,self.image.size[1] * LINE_LEN)
                print 'Drawing size is {0}. drawing from {1} to {2}'.format(self.image.size,line_start,line_end)
                if wind_in_view == 1:
                    draw.line([line_start,line_end],fill=green)
                    draw.text((line_loc + 10,(self.image.size[1] * LINE_LEN) - spacing - font_size),'Wind',font=font,fill=green)
                else:
                    draw.line([line_start,line_end],fill=darkgreen)
                    draw.text((line_loc + 10,(self.image.size[1] * LINE_LEN) - spacing - font_size),'Recip Wind',font=font,fill=darkgreen)
            
        del draw
        
        return 1
    def save_image(self,dpi=300,quality=95):
        ''' save altered image
        Note that this strips EXIF data. If this is a problem, look into package python-pyexiv2 which
        can read and write exif data.
        '''
        self.image.save(self.path + self.file,dpi=(dpi,dpi),quality=quality)
    def fix(self):
        ''' Any fixes we can do on the spot
        '''
        pass
   

def do_subprocess(command,shell=False,cwd='/tmp',db=False):
    '''
    Spawns sub process
    If shell is True, command should be a string
    otherwise it should be a list
    '''
    #print command
    #print command.__class__
    if shell is True and command.__class__ == list().__class__:
            command = ' '.join(command) # join list in to a string
    if shell is False and command.__class__ == str().__class__:
            command = command.split() # split string into list
    if db is True: print command
    result = subprocess.Popen(command,shell=shell,
                                cwd = cwd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    return result.communicate()[0]

    
def sftp_file(local_dir, local_file, host, port=22, username=None, password=None, pkey=None,
              key_filename=None, timeout=None, remotepath='/tmp',remove_file=False):
    ''' Send file via sftp
    '''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host,port=port,username=username,password=password)
    except BadHostKeyException,e:
        return e
    except AuthenticationException,e:
        return e
    except SSHException,e:
        return e
    except socket.error,e:
        return e
    ftp = ssh.open_sftp()
    try:
        ftp.chdir(local_dir):
    except IOError,e:
        print "{0} doesn't exist".format(local_dir)
        return e
    put_result = ftp.put(local_file,remotepath + local_file,confirm=True)
    if remove_file is True:
        ftp.remove(local_file)
    ftp.close()

if __name__ == '__main__':
    D40 = Camera()
    #D40.list_config()
    #D40.get_all_config()
    #print D40.config_dict
    new_picture = D40.take_picture(imgquality=2,db=False)
    #print new_picture.file
    D40.shutdown()
    exit()