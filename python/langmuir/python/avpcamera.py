#!/usr/bin/python
''' Langmuir Camera control
    Creare Camera Object which can return photo objects
    
    
    NEED TO CHANGE AVERAGES TO VECTORS
    
'''
from configobj import ConfigObj
from datetime import datetime
import errno
import logging
from math import atan,degrees
import os
import subprocess
import sys
import time
import traceback

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
     
class Camera(object):
    ''' Camera object
    '''
    ERROR_STRINGS = ("***",) #"For debugging messages")
    GPHOTO_ERRORS = {
        '0xa002':"Out of Focus",
        '0x200f':"Unknown"}
    def __init__(self,config=None,wind=None,db=False):
        if db is True: print "Instantiating Camera"
        reload(s) # In case settings have changed.
        self.config_dict = {'settings':{}, 'imgsettings':{}, 'capturesettings':{}, 'status':{}, 
                            'other':{}, 'actions':{}}
        # Some of this may be unnecessary in the future if the logger functionality can be moved
        # to a lower level, perhaps in avp_broker?
        LOG_FORMAT="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT)
        self.logger = logging.getLogger(self.__class__.__name__)
        if config is None:
            config = ConfigObj(infile=s.CONFIG_FILE,raise_errors=True)
        dbh = avp_db.DB_LogHandler(config)
        if db is True:
            dbh.setLevel(logging.DEBUG)
            self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(dbh)
        # Get configuration
        result_list_config = self.list_config(db=db)
        if result_list_config is None:
            print "Error: Unable to get configureation listing. Shutting down."
            self.shutdown()
        if wind is None:
            # Set up stuff for wind broker.
            self.wind = avp_broker.Y32500Broker(config)
        else:
            self.wind = wind
        #self.w_speed_ms = self.wind.wind_speed.value
        #self.w_dir = self.wind.wind_direction.value
        #self.c_dir = self.wind.compass_direction.value
    def shutdown(self):
        self.wind.unsubscribe_all()
        self.wind.disconnect()
    def __del__(self):
        self.shutdown()
    def list_config(self,db=False):
        command = s.GPHOTO2 + ' --list-config '
        result = self.do_gphoto(command,shell=False,db=db)
        # Now put result in a dictionary, with keys settings, imgsettings, and capturesettings
        if result is None:
            return result
        for line in result.splitlines():
            line2 = line[6:]
            line_tup = line2.partition('/')
            key = line_tup[0]
            val = line_tup[2]
            try:
                self.config_dict[key][val] = None
            except KeyError,e:
                print "Error {0} in Camera.list_config for {1} and {2}".format(e,key,val)
        return result
    def get_all_config(self):
        for data_group, config_type in self.config_dict.items():
            for data_item in config_type.keys():
                #print data_item
                # Get data from camera
                result = self.get_config(data_group,data_item)
                # Parse it
                rdict = self.parse_config_results(result)
                # Save it if it isn't empty
                if len(rdict) > 0:
                    self.config_dict[data_group][data_item] = rdict
    def parse_config_results(self,get_config_result,db=False):
        ''' Parse result of --get-config and return in in a dictionary
        '''
        rdict = {}
        c_type = None
        try:
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
                            if db is True: print "Found choice {0}".format(line)
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
                    if choice == rdict['setting_current']:
                        rdict['setting_value'] = choice_value
                        break
        except AttributeError: # This happens if we were unable to communicate with the camera.
            pass
        return rdict
    def get_config(self,data_group,data_item,db=False):
        ''' Get configuration data for a single value from camera
        '''
        config_item = '{0}/{1}'.format(data_group,data_item)
        command = s.GPHOTO2 + ' --get-config {0}'.format(config_item)
        get_config_result =  self.do_gphoto(command,shell=False,cwd='/tmp')
        if db: print get_config_result
        self.config_dict[data_group][data_item] = get_config_result
        return get_config_result
    def set_config(self,data_group,data_item,index,db=False):
        ''' Sets a configuration value for enries with an index
        '''
        config_entry = 'main/{0}/{1}'.format(data_group,data_item)
        command = s.GPHOTO2 + ' --set-config {0}={1}'.format(config_entry,index)
        set_config_result =  self.do_gphoto(command,shell=False,cwd='/tmp')
        if db: print set_config_result
        confirm_result = self.get_config(data_group,data_item,db=db)
        return (set_config_result,confirm_result)
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
                print '{0} is out of range {1} - {2}'.format(mode,min,max)
        except Exception,e:
            print 'Error: Exception in set_imgquality: {0}'.format(e)
    def set_imgquality_NEF(self):
        ''' Sets camera mode to RAW (nef)
        '''
        return self.set_imgquality(mode=3,db=False)
    def set_imgquality_JPEG_fine(self):
        ''' Sets image quality to JPEG fine
        '''
        return self.set_imgquality(mode=2,db=False)
    def get_imgquality(self,value=True,db=False):
        ''' Query camera as to its image quality 'imgsettings'
        '''
        data_group = 'imgsettings'
        data_item = 'imgquality'
        # Get data from camera
        result = self.get_config(data_group,data_item,db=db)
        # Parse it
        rdict = self.parse_config_results(result,db=db)
        # Save it if not empty
        if len(rdict) > 0:
            self.config_dict[data_group][data_item] = rdict
            # Now return the value
            try:
                if value is True:
                    return self.config_dict[data_group][data_item]['setting_value']
                else:
                    return self.config_dict[data_group][data_item]['setting_current']
            except KeyError,e:
                print 'KeyError in get_imgquality for {0},{1} from {2}'.format(data_group,data_item, self.config_dict[data_group][data_item])
                #print 'Error getting setting_value for {0},{1} from {2}'.format(data_group,data_item, self.config_dict)
                # These are just some typical values.
                if value is True:
                    return 2
                else:
                    return 'JPEG Fine'
        return None
    def get_ais(self,db=True):
        ''' Get current Aperture, ISO and speed data
        '''
        data_items = (('capturesettings','f-number'),
            ('imgsettings','iso'),
            ('capturesettings','exptime'))
        results = {}
        for data_item in data_items:
            get_config_result = self.get_config(*data_item,db=db)
            if db is True: print "get_config_result: {0}".format(get_config_result)
            rdict = self.parse_config_results(get_config_result,db=db)
            if db is True: print "rdict: {0}".format(rdict)
            # Save it if not empty
            if len(rdict) > 0:
                self.config_dict[data_item[0]][data_item[1]] = rdict
                results["{0}".format(data_item[1])] = rdict.get('setting_current','Error, no current settings available')
        return results
    def set_iso(self,db=False):
        ''' This will set ISO to the best setting for the current conditions.
        We are assuming that we can read aperture and exptime but not set them.
        Returns None if it is too dark to take a picture and a {} otherwise
        '''
        self.get_ais(db=db)
        iso_raised = False
        try:
            if self.config_dict.get('capturesettings',{}).get('f-number',{}).get('setting_value',None) == 0:
                # This should mean our aperture is wide open which will not happen in bright light at any ISO
                while True:
                    if float(self.config_dict['capturesettings']['exptime']['setting_current']) < s.MAX_EXPTIME:
                        # So we're at max Aperture and our shutter speed is too slow, so try increasing ISO
                        if int(self.config_dict['imgsettings']['iso']['setting_current']) >= s.MAX_ISO:
                            # ISO is as high as we are willing to set it.
                            print "Too Dark: ISO {iso_v}:{iso}, EXP {exp_v}:{exp}, F-N {fn_v}:{fn}".format(
                                   iso = self.config_dict['imgsettings']['iso']['setting_current'],
                                   iso_v = self.config_dict['imgsettings']['iso']['setting_value'],
                                   exp = self.config_dict['capturesettings']['exptime']['setting_current'],
                                   exp_v = self.config_dict['capturesettings']['exptime']['setting_value'],
                                   fn = self.config_dict['capturesettings']['f-number']['setting_current'],
                                   fn_v = self.config_dict['capturesettings']['f-number']['setting_value'])
                            return None
                        else:
                            # Increase ISO
                            new_iso_index = int(self.config_dict['imgsettings']['iso']['setting_value']) + 1
                            print "Increasing ISO from {0}:{1} to index {2}".format(
                                   self.config_dict['imgsettings']['iso']['setting_value'],
                                   self.config_dict['imgsettings']['iso']['setting_current'],
                                   new_iso_index)
                            self.set_config('imgsettings','iso',new_iso_index,db=db)
                            iso_raised = True
                            time.sleep(1) # Not sure if we need this
                            self.get_ais(db=db)
                    else:
                        #We're wide open, but our exposure time is still fast enough
                        return {'A':self.config_dict['capturesettings']['f-number']['setting_current'],
                                'I':self.config_dict['imgsettings']['iso']['setting_current'],
                                'S':self.config_dict['capturesettings']['exptime']['setting_current']}
            else:
                print "Aperture not wide open {0}:{1}".format(
                        self.config_dict['capturesettings']['f-number']['setting_value'],
                        self.config_dict['capturesettings']['f-number']['setting_current'])
        except KeyError,e:
            print "Key Error: {e} on {c_d}".format(e=e,c_d=self.config_dict)
            return None
        if iso_raised is False:  # Now let's make sure we're not stopped down all the way either   
            while self.f_stop_maxed() is True: # We are stopped all the way down. Perhaps ISO is too high. 
                iso_val = int(self.config_dict['imgsettings']['iso']['setting_value'])
                if iso_val == 0:
                    # Our ISO is already at the minimum
                    print "ISO at minimum {0}".format(self.config_dict['imgsettings']['iso']['setting_current'])
                    break
                else:
                    # Decrease ISO
                    new_iso_index = iso_val - 1
                    print "Decreasing ISO index from {iso_v}:{iso} to index {iso_v2}".format(
                            iso_v=iso_val,
                            iso=self.config_dict['imgsettings']['iso']['setting_current'],
                            iso_v2=new_iso_index)
                    self.set_config('imgsettings','iso',new_iso_index,db=db)
                    time.sleep(1) # Not sure if we need this
                    self.get_ais(db=db)
        return {'A':self.config_dict['capturesettings']['f-number']['setting_current'],
                'I':self.config_dict['imgsettings']['iso']['setting_current'],
                'S':self.config_dict['capturesettings']['exptime'].get('setting_current',None)}
    def f_stop_maxed(self):
        ''' Check to see if f-stop is at it's maxiumum value
            Current: f/9
            Choice: 0 f/3.5
            Choice: 1 f/4
            Choice: 2 f/4.5
            Choice: 3 f/5
            Choice: 4 f/5.6
            Choice: 5 f/6.3
            Choice: 6 f/7.1
            Choice: 7 f/8
            Choice: 8 f/9
            Choice: 9 f/10
            Choice: 10 f/11
            Choice: 11 f/13
            Choice: 12 f/14
            Choice: 13 f/16
            Choice: 14 f/18
            Choice: 15 f/20
            Choice: 16 f/22
        '''
        f_stop = self.config_dict['capturesettings']['f-number']['setting_value']
        f_stop_max = max(self.config_dict['capturesettings']['f-number']['setting_choices'])
        if f_stop == f_stop_max:
            return True
        else:
            return False
    def take_picture(self,imgquality=None,outpath=None,shell=False,log_exif=False,db=False):
        ''' Takes a picture
        If imgquality is not specified, current camera setting is used.
        If outpath is not specified, default for the imgquality will be used.
        
        Needs to notify if camera didn't respond
        May want to call set_iso to check if there is enough light
        Returns Photo() instance
        '''
        camera_imgquality = self.get_imgquality(db=db)
        if imgquality is None:
            print "No picture quality specified, using {0}:{1}".format(camera_imgquality,
                self.config_dict.get('imgsettings',{}).get('imgquality',{}).get('setting_current','unknown'))
            imgquality = camera_imgquality
        elif imgquality != camera_imgquality:
            if camera_imgquality == None:
                print "Unable to get image quality, possible communications failure"
                return None
            else:
                print "Camera imgquality {0} doesn't match requested {1}".format(camera_imgquality,imgquality)
                self.set_imgquality(mode=imgquality,db=db)
        if outpath is None:
            outpath = s.IMAGEPATH + s.PATHS[imgquality] 
        outfile = datetime.now().strftime(s.FILE_NAME_FORMAT)
        outfile = '{0}.{1}'.format(outfile, s.FILE_INFO[imgquality]['extension'])
        command = [s.GPHOTO2]
        if db is True:
            command.extend(['--debug', '--debug-logfile', '{0}_debug.txt'.format(outfile)])
        command.extend(['--camera', s.CAMERA])
        command.extend(['--port',s.PORT])
        command.append('--capture-image-and-download')
        command.extend(['--filename','{0}'.format(outfile)])
        if shell is True:
            command = ' '.join(command) # If Shell=True, we want a string
        if db is True:
            print "Command: {0}".format(command)
        # Record these naow as they may change while processing the picture
        wind_speed = self.wind.wind_speed.value
        gphoto2_result = self.do_gphoto(command,shell=shell,cwd=outpath,db=db)
        if gphoto2_result is None:
            return None
        if db is True:
            print "{0} result:\n{1}".format(s.GPHOTO2,gphoto2_result)
            print "INSTANTIATING NEW PHOTO {0}".format(outfile)
        new_photo = Photo(file=outfile,path=outpath,imgquality=imgquality,
                          wind_speed=wind_speed, 
                          aw_spd=self.wind.average_wind_speed.value,
                          w_dir=self.wind.wind_direction.value, c_dir=self.wind.compass_direction.value,
                          instance_note=gphoto2_result,log_exif=log_exif,db=db)
        return new_photo
    def do_gphoto(self,command,shell=False,cwd='/tmp',db=False):
        gphoto2_result = do_subprocess(command,shell=shell,cwd=cwd,db=db)
        error = False
        for line in gphoto2_result.splitlines():
            for error_string in self.ERROR_STRINGS:
                #print "Looking for '{0}' in '{1}'".format(error_string,line)
                if error_string in line:
                    if error is False: print "ERROR: in command '{0}'".format(command) # print once
                    print line
                    error = True
        if error is True:
            return None 
        else:
            return gphoto2_result
            
class Photo(object):
    '''
    Note, at 18mm, field of view is 66.721 degrees
    '''
    def __init__(self,file,path,imgquality=2,wind_speed=None,aw_spd=None,w_dir=None,c_dir=None,instance_note=None,log_exif=False,db=False):
        '''
        '''
        if db is True: print "Instantiating Photo"
        self.file = file
        self.path = path
        self.path_file = path + file
        self.imgquality=imgquality
        self.exif_data = {}
        self.get_exif(db=db)
        if log_exif is True:
            self.log_exif(db=db)
        self.interpret_exif(db=db)
        # Some information for annotating the picture
        self.wind_speed = wind_speed
        self.aw_spd = aw_spd
        self.w_dir = w_dir
        self.c_dir = c_dir
        self.instance_note = instance_note
        focal_length = self.focal_length[0]/10.0
        self.fov = degrees(2 * atan( s.SENSOR_WIDTH/(2 * focal_length) ))
        if db is True: print 'Calculated field of view {0}'.format(self.fov)
        #self.fov = 66.7 # At 18mm
        self.image = PIL.Image.open(self.path + self.file)
        #print "Image info {0}".format(self.image.info.get('exif',{}).keys())
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
        if ( db ): print "Focal length from EXIF is {0}".format(self.focal_length)
    def log_exif(self,db=False):
        ''' Log exif data to file in same directory as image.
        '''
        log_file_name = self.path_file.rpartition('.')[0] + '.exif' # Strip extension and add '.exif'
        with open(log_file_name,'w') as log_file:
            log_file.write('EXIF data dump\n\n')
            for key,value in self.exif_data.items():
                if len(str(value)) < 200: # Exclude long lines
                    log_file.write('{0} = {1}\n'.format(key,value))
        if db is True: print "Logged exif data to {0}".format(log_file_name)
    def nef_to_ppm(self,outpath=None,thumbnail=False,tiff=False,db=False):
        ''' Converts a NEF file to a PPM and returns a new PPM Photo Object
        '''
        valid_file_types = ('nef',)
        if self.file_type not in valid_file_types:
            print 'This method does not convert {0} files'.format(self.file_type)
            return None
        if outpath is None:
            outpath = IMAGEPATH + PPMPATH
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
        '''
        red       = '#ff0000'
        darkred   = '#880000'
        green     = '#0000ff'
        darkgreen = '#000088'
        black     = '#000000'
        '''
        font = PIL.ImageFont.truetype(s.font,font_size)
        spacing = 10
        FOV_height = font_size
        compass_height = FOV_height + spacing + font_size
        w_dir_height = compass_height + spacing + (font_size * 2)
        w_spd_height = w_dir_height + spacing + font_size
        image_width = self.image.size[0]
        draw = PIL.ImageDraw.Draw(self.image)
        # Save these so we can manipulate them later
        compass = self.c_dir 
        wind_dir = self.w_dir
        deg_left = compass - (self.fov/2.0) + s.CAMERA_SKEW
        deg_right = compass + (self.fov/2.0) + s.CAMERA_SKEW
        if deg_left < 0.0:
            deg_left += 360.0
        elif deg_left > 360:
            deg_left -= 360.0
        if deg_right > 360.0:
            deg_right -= 360.0
        elif deg_right < 0.0:
            deg_right += 360.0
        # First we want to make North and wind direction. This is complicated by the break in degrees.
        # record these incase they change during analysis
        draw.text((10,FOV_height),'{0:.0f}{1}'.format(deg_left,chr(176)),font=font,fill=s.black) # Label left edge
        draw.text((self.image.size[0] - 75,FOV_height),'{0:.0f}{1}'.format(deg_right,chr(176)),font=font,fill=s.black) #Label Right Edge
        draw.text((10,compass_height),'AVP Heading = {0:.0f}{1} mag.'.format(compass,chr(176)),font=font,fill=s.red) #Heading value
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
                line_loc = ((tick - deg_left)/self.fov) * image_width
            else:
                line_loc = ((tick - deg_left + 360)/self.fov) * image_width
            line_start = (line_loc,0)
            if tick == 0: # North
                line_end = (line_loc,self.image.size[1] * LINE_LEN)
                tick_color = s.red
                tick_label = 'N'
            else: # plain tick
                line_end = (line_loc,self.image.size[1] * TICK_LEN)
                tick_color = s.darkred
                tick_label = '{0:.0f}{1}'.format(tick,chr(176))
            draw.line([line_start,line_end],fill=tick_color)
            draw.text((line_loc,line_end[1]),tick_label,font=font,fill=tick_color)
            tick += 10
            if tick >= 360:
                tick -= 360
                #tick -= 360
            if (deg_left > deg_right) and (tick > deg_right) and (tick < deg_left): # contains North
                ticks_done = True
            elif (deg_left < deg_right) and (tick > deg_right):
                ticks_done = True
        if wind_dir is None:
            print "Can not mark wind when direction is unknown"
        else:
            draw.text((10,w_dir_height),'Wind Direction: {0:.0f}{1} mag'.format(wind_dir,chr(176)),font=font,fill=s.green)
            if self.wind_speed is not None:
                draw.text((10,w_spd_height),'Wind Speed: {0:.1f} m/s'.format(self.wind_speed),font=font,fill=s.green)
            if self.aw_spd is not None:
                w_spd_height += spacing + font_size
                draw.text((10,w_spd_height),'Avg. Wind Speed: {0:.1f} m/s'.format(self.aw_spd),font=font,fill=s.green)
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
                if db is True: print "Compass is {0}, deg_left = {1}, image_width = {2}".format(compass,deg_left,image_width)
                if wind_dir < deg_right: # Not split
                    line_loc = ((self.fov - (deg_right - wind_dir))/self.fov) * image_width
                else: # Split
                    line_loc = ((wind_dir - deg_left)/self.fov) * image_width
                line_start = (line_loc,0)
                line_end = (line_loc,self.image.size[1] * LINE_LEN)
                if db is True: print 'Drawing size is {0}. drawing from {1} to {2}'.format(self.image.size,line_start,line_end)
                if wind_in_view == 1:
                    draw.line([line_start,line_end],fill=s.green)
                    draw.text((line_loc + 10,(self.image.size[1] * LINE_LEN) - spacing - font_size),'Wind',font=font,fill=s.green)
                else:
                    draw.line([line_start,line_end],fill=s.darkgreen)
                    draw.text((line_loc + 10,(self.image.size[1] * LINE_LEN) - spacing - font_size),'Recip Wind',font=font,fill=s.darkgreen)
            
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
                                stderr=subprocess.STDOUT)
    result = result.communicate()[0]
    if db is True: print "do_subpreocess() result: {0}".format(result)
    return result
    
def sftp_file(local_path, local_file, host, port=22, username=None, password=None, priv_key=None,
              key_filename=None, timeout=None, remotepath='/tmp',remove_file=False,db=False):
    ''' Send file via sftp
    '''
    local_path_full = local_path + local_file
    remote_path_full = remotepath + local_file
    if db is True: print "transfering {0} to {1}:{2}".format(local_path_full,host,remote_path_full)
    ssh = paramiko.SSHClient()
    if db is False:
        logger = paramiko.util.logging.getLogger()
        logger.setLevel(logging.INFO)
    #ssh.set_missing_host_policy(paramiko.AutoAddPolicy()) # No need unless we change hosts.
    try:
        pkey = paramiko.RSAKey(filename=priv_key)
        ssh.load_system_host_keys()
        ssh.connect(host, port=port, username=username, password=password, pkey=pkey, 
            key_filename=key_filename,timeout=timeout)
        sftp = ssh.open_sftp()
        try:
            sftp.stat(remotepath)
        except IOError,e:
            if e.errno == errno.ENOENT: # Missing directory
                sftp.mkdir(path=remotepath)
            else:
                logger.error("Couldn't stat({0}), e".format(remotepath,e))
                return 0
        put_result = sftp.put(localpath=local_path_full, remotepath=remote_path_full)
        if db is True: print "Put result: {0}".format(put_result)
        if remove_file is True:
            # Delete local file
            if db is True: print "Removing {0}".format(local_path_full)
            os.remove(local_path_full)
    except paramiko.BadHostKeyException,e:
        print "Error BadHostKeyException:{0}".format(e)
    except paramiko.AuthenticationException,e:
        print "Error AuthenticationException:{0}".format(e)
    except paramiko.SSHException,e:
        print "Error SSHException:{0}".format(e)
    finally:
        ssh.close()
        del(ssh)
        return 1
        
def reset_port(db=False):
    ''' Reset the usb port
    '''
    lsusb_command = '/usr/bin/lsusb'
    lsusb_result = do_subprocess(lsusb_command,shell=False,db=db)
    # The result will be something like 'Bus 001 Device 006: ID 04b0:0414 Nikon Corp.'
    
    for line in lsusb_result.splitlines():
        if 'Nikon' in line:
            if db is True: print "Found {line}".format(line=line)
            line = line.split()
            usb_id_1 = line[1]
            usb_id_2 = line[3][:3] # Get rid of trailing ':'
            break
    try:
        usbreset_command = '/data/langmuir/bin/usbreset /dev/bus/usb/{0}/{1}'.format(usb_id_1,usb_id_2)
        if db is True:
            print "Resetting usb port with {cmd}".format(cmd=usbreset_command)
        do_subprocess(usbreset_command,shell=True,db=db)
    except Exception,e:
        print "Error: in reset_port {0} from ".format(e)
    

if __name__ == '__main__':
    D40 = Camera(db=True)
    #D40.list_config()
    #D40.get_all_config()
    #print D40.config_dict
    try:
        new_picture = D40.take_picture(imgquality=2,log_exif=True,db=True)
        # Now transfer the picture
        remotepath = '/home2/avp/Camera_Images/JPEG/' # THIS NEEDS TO BE MORE DYNAMIC
        remotepath = s.REMOTE_PATH + s.PATHS.get(new_picture.imgquality,'')
        sftp_file(new_picture.path,new_picture.file,s.IMAGE_HOST,username=s.IMAGE_HOST_USER,
            priv_key=s.PRIV_KEY, remotepath=remotepath,remove_file=True)
    except Exception,e:
        print "Error: Overall exception {0}".format(e)
        traceback.print_exc()   
    finally:
        D40.shutdown()
        exit()
