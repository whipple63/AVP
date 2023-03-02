/* Daemon for the Pertelian LCD display.

   This program will horizontally scroll information across the display.

	 Written by Ron Lauzon - 2006
	 I release this code into the Public Domain.
	 Use this at your own risk.

	Modifications and new features coded by Pred S. Bundalo
	Sat Nov 18 00:16:27 CST 2006
	Modifications and new features coded by Ron Lauzon
	Mon Mar 26 09:45:00 EST 2007

*/
#include <stdio.h>
#include <time.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <signal.h>
#include "pert_interf.h"

#define MAX_DATA_LINE 1024

#ifdef DEBUG
#define CONFIG_FILE_NAME "./pertd.conf"
#else
#define CONFIG_FILE_NAME "/etc/pertd.conf"
#endif

char *refresh_file_name = NULL;
char *pid_file_name = NULL;
char *stop_file_name = NULL;
char *backlighton_file_name = NULL;
char *backlightoff_file_name = NULL;
char *data_file_name[4] = {NULL,NULL,NULL,NULL};
char *device_name = NULL;
double refresh_time = 0.0;
unsigned int delay_time = 0;

int pos[4];
time_t last_mod_time[4];
char *lines[4];
time_t last_refresh_time;
struct stat stat_buf;
int vertical_mode;
int backlight_mgt;
int backlight_on;

/* This routine puts the program into "daemon" mode.
 * i.e. it disconnects from the current session so that
 * it's not automatically killed when the user logs off.
 */
int daemon_init() {
	pid_t pid;
	FILE *pidfile;

#ifdef DEBUG
	return(0); /* Don't go daemon in debug mode */
#endif
	/* Fork off 8-) */
	if ( (pid=fork()) < 0)
		return(-1);  /* If error - leave */
	else if (pid != 0)
		exit(0);     /* parent exits */

	/* Child continues */

	/* Become session leader */
	setsid();

	/* Write the PID to a file. */
	pid = getpid();
	if ((pidfile = fopen(pid_file_name,"w")) != NULL) {
		fprintf(pidfile,"%d\n",pid);
		fclose(pidfile);
	} else {
		fprintf(stderr,"Couldn't open PID file %s for write.\n",pid_file_name);
	}

	return(0);
  }

/* Returns non-zero if the data file changed */
int data_file_changed(int lineno, off_t *file_size) {

	/* Try to stat the file */
	if (stat(data_file_name[lineno],&stat_buf) == 0) {
		/* If the last mod time for the file has changed */
		if (stat_buf.st_mtime != last_mod_time[lineno]) {
			/* Remember the last mod time */
			last_mod_time[lineno] = stat_buf.st_mtime;
			/* Send back the file size */
			*file_size = stat_buf.st_size;
			/* and return that the file changed */
			return(1);
		} else {
			/* Return that the file has not changed */
			return(0);
		}
	}
  else {
    /* We couldn't stat the file.  Assume it changed. */
		last_mod_time[lineno] = 0;
		return(1);
  }
}

/*
 * Resets last refresh time to 0, forcing a refresh on the next
 * loop cycle.
 */
void schedule_dataread() {
	last_refresh_time = 0;
}


/* Returns non-zero if it's time to refresh the data to 
 * be displayed.
 */
int refresh_time_hit() {
	time_t now;
#ifdef DEBUG
	printf("checking refresh time\n");
#endif

	/* What time is it now? */
	now = time(NULL);

	/* If the number of seconds since the last refresh is
	 * more than the refresh time (in seconds)... */
	if (difftime(now,last_refresh_time) > refresh_time) {
		last_refresh_time = now; /* reset the last refresh time */
		return 1; /* return true */
		}
	else
		return 0; /* return false */
	}

int read_config(char *config_file_name) {
	FILE *config_file;
	char line[1024];
	char *parm;
	char *value;

	char_delay = 1; /* default correctly for old systems */
	backlight_mgt = 0; /* Don't do backlight management */

	/* Try to open the config file */
	if ((config_file = fopen(config_file_name,"r")) != NULL) {
		/* Read lines from the config file */
		while(fgets(line,1024,config_file) != NULL) {

			/* Trim the new line */
			line[strlen(line)-1] = '\0';

			/* If comment, ignore */
			if (line[0] == '#')
				continue;
 			/* If no = in the string, ignore */
			if (strchr(line,'=') == NULL)
				continue;

			/* We found a parm/value pair.  Point to the value. */
			value=strchr(line,'=');
			value[0] = '\0';
			value++;

			/* Now, process the parm */
			if (strcmp(line,"pidfile") == 0) {
				pid_file_name = (char *)malloc(strlen(value)+1);
				strcpy(pid_file_name,value);
		        }
			if (strcmp(line,"refresh_file_name") == 0) {
				refresh_file_name = (char *)malloc(strlen(value)+1);
				strcpy(refresh_file_name,value);
		        }
			if (strcmp(line,"stop_file_name") == 0) {
				stop_file_name = (char *)malloc(strlen(value)+1);
				strcpy(stop_file_name,value);
		        }
			if (strcmp(line,"backlighton_file_name") == 0) {
				backlighton_file_name = (char *)malloc(strlen(value)+1);
				strcpy(backlighton_file_name,value);
		        }
			if (strcmp(line,"backlightoff_file_name") == 0) {
				backlightoff_file_name = (char *)malloc(strlen(value)+1);
				strcpy(backlightoff_file_name,value);
		        }
			if (strcmp(line,"data_file_1") == 0) {
				data_file_name[0] = (char *)malloc(strlen(value)+1);
				strcpy((data_file_name[0]),value);
		        }
			if (strcmp(line,"data_file_2") == 0) {
				data_file_name[1] = (char *)malloc(strlen(value)+1);
				strcpy((data_file_name[1]),value);
        		}
			if (strcmp(line,"data_file_3") == 0) {
				data_file_name[2] = (char *)malloc(strlen(value)+1);
				strcpy((data_file_name[2]),value);
        		}
			if (strcmp(line,"data_file_4") == 0) {
				data_file_name[3] = (char *)malloc(strlen(value)+1);
				strcpy((data_file_name[3]),value);
        		}
			if (strcmp(line,"device") == 0) {
				device_name = (char *)malloc(strlen(value)+1);
				strcpy(device_name,value);
        		}
			if (strcmp(line,"refresh_time") == 0) {
				refresh_time=atof(value);
        		}
			if (strcmp(line,"delay_time") == 0) {
				delay_time=atoi(value);
		        }
			if (strcmp(line,"char_delay") == 0) {
				char_delay=atoi(value);
		        }
			if (strcmp(line,"backlightmgt") == 0) {
				backlight_mgt=atoi(value);
		        }
			}
			fclose(config_file);
		}

		/* Set defaults for any values not in the config file */
		if (refresh_file_name == NULL) {
			refresh_file_name = (char *)malloc(1024);
			strcpy(refresh_file_name,"pertrefresh");
			}
		if (stop_file_name == NULL) {
			stop_file_name = (char *)malloc(1024);
			strcpy(stop_file_name,"pertstop");
			}
		if (backlighton_file_name == NULL) {
			backlighton_file_name = (char *)malloc(1024);
			strcpy(backlighton_file_name,"backlighton");
			}
		if (backlightoff_file_name == NULL) {
			backlightoff_file_name = (char *)malloc(1024);
			strcpy(backlightoff_file_name,"backlightoff");
			}
		if (data_file_name[0] == NULL) {
			data_file_name[0] = (char *)malloc(1024);
			strcpy((data_file_name[0]),"pert1");
			}
		if (data_file_name[1] == NULL) {
			data_file_name[1] = (char *)malloc(1024);
			strcpy((data_file_name[1]),"pert2");
			}
		if (data_file_name[2] == NULL) {
			data_file_name[2] = (char *)malloc(1024);
			strcpy((data_file_name[2]),"pert3");
			}
		if (data_file_name[3] == NULL) {
			data_file_name[3] = (char *)malloc(1024);
			strcpy((data_file_name[3]),"pert4");
			}
		if (device_name == NULL) {
			device_name = (char *)malloc(1024);
			strcpy(device_name,"/dev/ttyUSB0");
			}
		if (refresh_time == 0.0)
			refresh_time = 60.0; /* One minute */
		if (delay_time == 0)
			delay_time = 500000; /* 1/2 second (500,000 milliseconds) */
	}

int refresh_indicated() {
#ifdef DEBUG
	printf("checking refresh\n");
#endif
	if (stat(refresh_file_name,&stat_buf) == 0) {
		unlink(refresh_file_name);
		return 1;
	} else {
		return 0;
	}
}

int stop_indicated() {
	FILE *stop_file;
#ifdef DEBUG
	printf("checking stop\n");
#endif
	if ((stop_file = fopen(stop_file_name,"r")) == NULL)
		return 0;
	else {
  	fclose(stop_file);
		unlink(stop_file_name);
	  return 1;
		}
}

int backlighton_indicated() {
	FILE *backlight_file;
#ifdef DEBUG
	printf("checking backlight on\n");
#endif
	if ((backlight_file = fopen(backlighton_file_name,"r")) == NULL) {
		return 0;
	  }
	else {
  	fclose(backlight_file);
		unlink(backlighton_file_name);
	  return 1;
		}
}

int backlightoff_indicated() {
	FILE *backlight_file;
#ifdef DEBUG
	printf("checking backlight off\n");
#endif
	if ((backlight_file = fopen(backlightoff_file_name,"r")) == NULL) {
		return 0;
		}
	else {
  	fclose(backlight_file);
		unlink(backlightoff_file_name);
	  return 1;
		}
}

void read_data() {
	int i;
	char *line;
	FILE *data_file;
	off_t file_size;
	size_t data_read;
	char *nl;

#ifdef DEBUG
	printf("reading data\n");
#endif

	/* For each display line */
	for(i=0; i<4; i++) {

		/* If the data file time stamp changed */
		if (data_file_changed(i,&file_size)) {

#ifdef DEBUG
			printf("Data file %s changed. size=%d\n",data_file_name[i],file_size);
#endif

			/* Dispose of the old line */
			if (lines[i] != NULL)
				free((lines[i]));

			/* If the file is empty */
			if (file_size == 0) {
					lines[i] = NULL; /* indicate that there is no data */

			} else {
				/* Allocate a new line large enough
				 * to hold the data plus the seperator
				 * plus the end of string */
				line = (char *)malloc(file_size + 4);

				/* Try to open the data file for this line */
				if ((data_file=fopen(data_file_name[i],"r")) != NULL) {

					/* Try to read the whole file */
					data_read = fread(line,sizeof(char),file_size,data_file);

#ifdef DEBUG
					printf("Read %d bytes\n",data_read);
#endif

					/* If no data was read... */
					if (data_read == 0) {
						free(line); /* memory leaks are bad */
						lines[i] = NULL; /* Indicate no data */
					}
					else {
						/* If the file had data in it... */

						/* Force an end string - just to be sure */
						line[data_read] = '\0';

						/* Trim the new line off the end */
						if (line[strlen(line)-1] = '\n')
							line[strlen(line)-1] = '\0';

						/* Remove the new lines from the middle
						 * of the data */
						while ((nl = strchr(line,'\n')) != NULL)
							*nl = ' ';

						/* Put the seperator onto the end of the data
						 * IFF we must scroll.  */
						if( strlen(line) > PERT_DISPLAY_WIDTH )
							strcat(line," - ");

						/* Set the display line to all this stuff */
						lines[i] = line;

#ifdef DEBUG
      			printf("%d:%s\n",i,lines[i]);
#endif
					}

				/* Close the file since we opened it */
				fclose(data_file);
 				}
			else {
				/* If we couldn't open the file, force the pointer to NULL
			 	 * so that we know there's no data for this line */
				lines[i] = NULL;
				free(line); /* memory leaks are bad */
				}	
			}
		}
	}
}

/* Copy over PERT_DISPLAY_WIDTH chars of data into line - wrapping around 
 * when at the end of the data */
char *fill_line(int lineno,int offset) {
	static char temp_line[21];
	int i;
	int temp_pos;

	/* If the line contains no data */
	if (lines[lineno] == NULL) {
        /* If we are on the first line */
        if (lineno == 0) {
            /* No data to display - return blanks to clear line */
				    memset(temp_line,' ',PERT_DISPLAY_WIDTH);
            temp_line[PERT_DISPLAY_WIDTH] = '\0';
				    return(temp_line);
        } else {
            /* Try to fill with some of the previous line */
            return(fill_line(lineno-1,offset + PERT_DISPLAY_WIDTH));
        }
	}
	if (strlen(lines[lineno]) == 0) {
        /* If we are on the first line */
        if (lineno == 0) {
            /* No data to display - return blanks to clear line */
				    memset(temp_line,' ',PERT_DISPLAY_WIDTH);
            temp_line[PERT_DISPLAY_WIDTH] = '\0';
				    return(temp_line);
        } else {
            /* Try to fill with some of the previous line */
            return(fill_line(lineno-1,offset + PERT_DISPLAY_WIDTH));
        }
	}

	/* If there are PERT_DISPLAY_WIDTH or less chars to display */
	if (strlen(lines[lineno]) < 21) {
		/* If this is the first time called */
   	if (offset == 0) {
				/* Return the line and pad with blanks */
		    strcpy(temp_line,(lines[lineno]));
		    for (i=strlen(lines[lineno]); i<PERT_DISPLAY_WIDTH; i++)
			    temp_line[i] = ' ';
		    temp_line[PERT_DISPLAY_WIDTH] = '\0';
		    return(temp_line);
		} else { /* not the first time called - return blanks */
        /* No data to display - return blanks to clear line */
		    memset(temp_line,' ',PERT_DISPLAY_WIDTH);
        temp_line[PERT_DISPLAY_WIDTH] = '\0';
		    return(temp_line);
        }
		}

    /* If there's not enough data to display */
    if (strlen(lines[lineno]) <= offset) {
        /* No data to display - return blanks to clear line */
        memset(temp_line,' ',PERT_DISPLAY_WIDTH);
        temp_line[PERT_DISPLAY_WIDTH] = '\0';
        return(temp_line);
    }
        
	/* If there are more than PERT_DISPLAY_WIDTH chars to display,
	 * display PERT_DISPLAY_WIDTH starting at the last position
	 * displayed */
	temp_pos = pos[lineno] + offset;
	while (temp_pos > strlen(lines[lineno]))
		temp_pos = temp_pos - strlen(lines[lineno]);
	if (temp_pos < 0)
		temp_pos = 0;

	/* For each char in the temp line */
	for (i=0; i<PERT_DISPLAY_WIDTH; i++) {
		/* If we are pointing beyond the original line,
		 * start over at the beginning */
		if (temp_pos >= strlen(lines[lineno]))
			temp_pos = 0;
			/* Copy over 1 char from the original line */
      temp_line[i] = lines[lineno][temp_pos];
			temp_pos++;
	}

	/* Increment where we start */
  /*if (offset == 0) { */
		pos[lineno]++;

		/* If we went past the end of the line,
		 * start over */
		if (pos[lineno] >= strlen(lines[lineno]))
			pos[lineno] = 0;
	/*} */

	/* Force an end of line */
	temp_line[PERT_DISPLAY_WIDTH] = '\0';
	return(temp_line);
}

/* Copy over PERT_DISPLAY_WIDTH chars of data into line - wrapping around 
 * when at the end of the data */
char *fill_vert_line(int lineno) {
	static char temp_line[21];
	int i;
	int temp_pos;

	/* If the line contains no data */
	if (lines[0] == NULL) {
		/* Return blanks to clear line */
		memset(temp_line,' ',PERT_DISPLAY_WIDTH);
		temp_line[PERT_DISPLAY_WIDTH] = '\0';
		return(temp_line);
	}
	if (strlen(lines[0]) == 0) {
		/* Return blanks to clear line */
		memset(temp_line,' ',PERT_DISPLAY_WIDTH);
		temp_line[PERT_DISPLAY_WIDTH] = '\0';
		return(temp_line);
	}

	/* Where do we start for this line? */
	temp_pos = pos[0] + lineno * PERT_DISPLAY_WIDTH;
#ifdef DEBUG
  printf("temp_pos = %d:%d\n",temp_pos,strlen(lines[0]));
#endif

	/* If we are past the data, blank */
	if (temp_pos > strlen(lines[0])) {
		/* Return blanks to clear line */
		memset(temp_line,' ',PERT_DISPLAY_WIDTH);
		temp_line[PERT_DISPLAY_WIDTH] = '\0';
		return(temp_line);
	}

	/* For each char in the temp line */
	for (i=0; i<PERT_DISPLAY_WIDTH; i++) {
		/* If we are pointing beyond the original line,
		 * start over at the beginning */
		if (temp_pos >= strlen(lines[0])) {
      temp_line[i] = ' ';
		} else {
			/* Copy over 1 char from the original line */
      temp_line[i] = lines[0][temp_pos];
		}
		temp_pos++;
	}

	/* Force an end of line */
	temp_line[PERT_DISPLAY_WIDTH] = '\0';
	return(temp_line);
}

int inVerticalMode() {
	int temp;
	int i;

	return 0; /* Turn off this feature for now */

	/* Special case - line 1 must be filled in.
	 * If it's not, we aren't in vert mode */
	if (lines[0] == NULL) {
		return 0;
	}
	if (strlen(lines[0]) == 0) {
		return 0;
	}

	/* The rest of the lines must be empty */
	temp = 0;
	/* Look through the rest of the lines */
	for (i=1; i<4; i++) {
		/* If the line isn't null */
		if (lines[i] != NULL) {
			/* And it's not empty */
			if (strlen(lines[i]) > 0) {
				/* Count this line */
				temp = temp + 1;
			}
		}
	}

	/* If we found at least 1 line that has data */
	if (temp > 0) {
		return 0; /* not vert mode */
	} else {
		return 1; /* vert mode */
	}
}

int dataToDisplay() {
	int temp;
	int i;
	temp = 0;

	/* Look through all the lines */
	for (i=0; i<4; i++) {
		/* If the line isn't empty */
		if (lines[i] != NULL) {
			if (strlen(lines[i]) > 0) {
#ifdef DEBUG
			  printf("dataToDisplay: line %d\n",i);
#endif
				return 1; /* we have data */
			}
		}
	}

#ifdef DEBUG
  printf("dataToDisplay: no lines\n");
#endif
	/* We only get here when no lines have data */
	return 0;
}

void backlight_management() {
	/* If backlight management isn't on, we are done */
	if (!backlight_mgt) {
		return;
	}

#ifdef DEBUG
	printf("Doing backlight management\n");
#endif

	/* If there is no data to display */
	if (!dataToDisplay()) {
		/* If the backlight is on */
		if (backlight_on) {
			/* Turn the backlight off */
			backlight(0);
			backlight_on = 0;
		}
	} else { /* there is data to display */
		/* If the backlight is not on */
		if (!backlight_on) {
			/* Turn it on */
			backlight(1);
			backlight_on = 1;
		}
	}
}

void display_date_time() {
	time_t now_t;
	struct tm *now_tm;
	char line2[PERT_DISPLAY_WIDTH+1], line3[PERT_DISPLAY_WIDTH+1];

	/* First we need to get the current time */
	now_t = time(NULL);

	/* Now, we need to convert the time_t to something useful */
	now_tm = localtime(&now_t);

	/* Format the date/time into a date line and a time line */
	/* DDD MMM DD, YYYY - 16 chars pad 4 spaces */
	strftime(line2,PERT_DISPLAY_WIDTH+1,"  %a %b %d, %Y  ",now_tm);
	/* HH:MM:SS - 8 chars - pad 12 spaces */
	strftime(line3,PERT_DISPLAY_WIDTH+1,"      %T      ",now_tm);
	line2[PERT_DISPLAY_WIDTH] = '\0';
	line3[PERT_DISPLAY_WIDTH] = '\0';

#ifdef DEBUG
	printf("line2= %s\n",line2);
	printf("line3= %s\n",line3);
#endif

	/* Put the lines on the display */
	wrtln(1,line2);
	wrtln(2,line3);
}

int main(int argc, char *argv[]) {
	int lineno;
	char temp_line[21];
	int i;

	/* Set up a signal handler for SIGUSR1 to check data file
	 * timestamps immediately. */
	signal(SIGUSR1, schedule_dataread);

	/* Read config file */
	if (argc > 1) {
		/* We have an argument - try to read the config file
		 * using that argument */
	  if (!read_config(argv[1])) {
			/* If we failed - try to read the default config file */
	  	read_config(CONFIG_FILE_NAME);
		}
	} else {
		/* No parm - use default config file */
	  read_config(CONFIG_FILE_NAME);
	}

	/* On start up, assume horizontal mode */
  vertical_mode = 0;

	/* Go daemon */
	if (daemon_init() != 0) {
		fprintf(stderr,"Failed to go daemon\n");
		exit(1);
		}

#ifdef DEBUG
	printf("Stop file name = %s\n",stop_file_name);
	printf("Backlight on name = %s\n",backlighton_file_name);
	printf("Backlight off name = %s\n",backlightoff_file_name);
	printf("Data 1 = %s\n",(data_file_name[0]));
	printf("Data 2 = %s\n",(data_file_name[1]));
	printf("Data 3 = %s\n",(data_file_name[2]));
	printf("Data 4 = %s\n",(data_file_name[3]));
	printf("Device = %s\n",device_name);
	printf("Refresh time = %f\n",refresh_time);
	printf("Delay time = %d\n",delay_time);
	printf("Char Delay time = %d\n",char_delay);
	printf("Backlight mgt = %d\n",backlight_mgt);
#endif

	/* Initialize the Pertelian */
  display_init(device_name);

	/* The backlight is on when the program starts */
	backlight_on = 1;
	backlight(1);

	/* Set the last refresh to effectively never */
	last_refresh_time = 0;

	/* Initialize the display information */
	for (lineno = 0; lineno < 4; lineno++) {
		pos[lineno] = 0;
		last_mod_time[lineno] = 0;
		lines[lineno] = NULL;
    }

top_of_loop: /* infinite loop */

	/* If the user wants the daemon to stop... */
	if (stop_indicated()) {
		/* Display a useful message on the Pertelian */
		wrtln(0,"                    ");
		wrtln(1,"pertd daemon stopped");
		wrtln(2,"                    ");
		wrtln(3,"                    ");

		/* Clean up the connect to the Pertelian */
		display_close();

		/* Exit the daemon gracefully */
		return(0);
		}

	if (backlighton_indicated()) {
		backlight(1);
		backlight_on = 1;
		}

	if (backlightoff_indicated()) {
		backlight(0);
		backlight_on = 0;
		}

	if (refresh_indicated()) {
		schedule_dataread();
		}

	if (refresh_time_hit()) {
		read_data();
		backlight_management();
		}

	/* Check to see if vertical display mode */
	if (inVerticalMode()) {
#ifdef DEBUG
		printf("Vertical mode\n");
#endif
		/* Vertical display mode */
		if (!vertical_mode) { /* First time in vert mode */
			pos[0] = 0;
			vertical_mode = 1;
		}
		/* For each display line... */
		for (lineno = 0; lineno < 4; lineno++) {
			wrtln(lineno,fill_vert_line(lineno));
		}
		/* Move the display window down 1 line */
		pos[0] = pos[0] + PERT_DISPLAY_WIDTH;

		/* If we've moved past the end of the data */
		if ((pos[0] + PERT_DISPLAY_WIDTH*2) > strlen(lines[0])) {
			pos[0] = 0;
		}

		/* Special case - there's not enough data to fill the display */
		if (strlen(lines[0]) <= PERT_DISPLAY_WIDTH*4) {
			pos[0] = 0; /* don't move */
		}

	} else {
#ifdef DEBUG
		printf("Horizontal mode\n");
#endif
		/* Horizontal display mode */
		vertical_mode = 0;

		/* For each display line... */
		for (lineno = 0; lineno < 4; lineno++) {
			wrtln(lineno,fill_line(lineno,0));
			}
	}

	/* If there was no data to display */
	if (!dataToDisplay()) {
		/* Let's put the date/time on the display */
		display_date_time();
	}

	/* Pause for a bit */
  sleep_us(delay_time);

	goto top_of_loop;

	/* Note that this line never is executed.  But I like to have
	 * it here anyway */
	return(0);
}
