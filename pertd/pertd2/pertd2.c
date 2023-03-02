/* Daemon for the Pertelian LCD display.

   This program will horizontally scroll information across the display.

	 Written by Ron Lauzon - 2007
	 I release this code into the Public Domain.
	 Use this at your own risk.
*/

#include <stdio.h>
#include <time.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <ctype.h>
#include <stdlib.h>
#include "fifo.h"
#include "pert_interf.h"

# define BUF_SIZE 512

#ifdef DEBUG
#define CONFIG_FILE_NAME "./pertd2.conf"
#else
#define CONFIG_FILE_NAME "/etc/pertd2.conf"
#endif

/* Commands */
char *command_text[] = {"backlight on",
                    "backlight off",
                    "stop",
                    "line1",
                    "line2",
                    "line3",
                    "line4",
                    "delay time",
                    "char delay",
                    "backlight mgt on",
                    "backlight mgt off",
                    NULL};
enum command_enum {
	backlight_on = 0,
	backlight_off,
	stop,
	line1,
	line2,
	line3,
	line4,
	delay_time_cmd,
	char_delay_cmd,
	backlight_mgt_on,
	backlight_mgt_off,
	error_cmd=999};

/* Config information */
char *fifo_name = NULL;
char *device_name = NULL;
unsigned int delay_time = 0;
int backlight_mgt = 0;

/* Information about the data to display */
char *lines[4]; /* The line text */
int pos[4]; /* The position we are in the line */
time_t refresh_time[4]; /* Time data was last refreshed */
int timeout[4]; /* Number of seconds before we expire the line */
int backlight_status; /* 0 - backlight not on, 1 - backlight on */

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

	return(0);
  }


int is_numeric(char *buffer) {
	int i;

	/* Look through all the chars in the buffer */
	for (i=0; i<strlen(buffer); i++) {
		/* If we find a character that isn't a digit */
		if (!isdigit(buffer[i])) {
				/* It was bad data */
				return(0); /* false - not numeric */
			}	
	}
	/* By the time we get here, all the characters are digits */
	return(1); /* true - numeric */
}

int read_config(char *config_file_name) {
	FILE *config_file;
	char line[1024];
	char *parm;
	char *value;

#ifdef DEBUG
	printf("Opening config file %s\n",config_file_name);
#endif

	char_delay = 1; /* default correctly for old systems */

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
			if (strcmp(line,"fifo_name") == 0) {
				fifo_name = (char *)malloc(strlen(value)+1);
				strcpy(fifo_name,value);
		  }
			if (strcmp(line,"device") == 0) {
				device_name = (char *)malloc(strlen(value)+1);
				strcpy(device_name,value);
      }
			if (strcmp(line,"delay_time") == 0) {
				delay_time=atoi(value);
		  }
			if (strcmp(line,"char_delay") == 0) {
				char_delay=atoi(value);
		  }
			if (strcmp(line,"backlight_mgt") == 0) {
				backlight_mgt=atoi(value);
		  }
		}
		fclose(config_file);
	}

	/* Set defaults for any values not in the config file */
	if (fifo_name == NULL) {
			fifo_name = (char *)malloc(1024);
			strcpy(fifo_name,"/tmp/pertd2.fifo");
	}
	if (device_name == NULL) {
		device_name = (char *)malloc(1024);
		strcpy(device_name,"/dev/ttyUSB0");
		}
	if (delay_time == 0)
		delay_time = 500000; /* 1/2 second (500,000 milliseconds) */
}

int get_command() {
	char *command;
	int i;

	command = read_line();
	if (command == NULL) {
		return(error_cmd); /* No data */
	}

	/* lower case the command */
	for(i=0;i<strlen(command);i++)
		command[i] = tolower(command[i]);

#ifdef DEBUG
	printf("Command:%s\n",command);
#endif

	/* Loop through the commands */
	i = 0;
	while(command_text[i] != NULL) {
		/* If we found the command text */
		if (strcmp(command,command_text[i]) == 0) {
			free(command); /* memory leaks are bad */
#ifdef DEBUG
			printf("Command_num:%d\n",i);
#endif
			/* Return that command number */
   		return(i);
		}
		i++;
	}

	/* If we got here, we didn't find the command
	 * so the data is invalid.  Throw it out. */
	free(command); /* memory leaks are bad */
	return(error_cmd); /* bad data */
}

int get_timeout() {
	char *timeout;
	int i;
	int int_timeout;

	timeout = read_line();
	if (timeout == NULL) {
		return(-1); /* No data */
	}

  /* Validate that the timeout is a number */
	if (!is_numeric(timeout)) {
		/* If it wasn't a digit, it was bad data */
		free(timeout);
		return(-1); /* bad data */
	}

#ifdef DEBUG
	printf("Timeout:%s\n",timeout);
#endif

	/* Convert the buffer into a int and return it */
	int_timeout = atoi(timeout);
	free(timeout);
	return(int_timeout);
}

char *get_line() {
	char *EOD;
	char *current_line, *temp;
	char *line_buffer;
	int current_length;

	/* Get EOD string */
	EOD = read_line();
	if (EOD == NULL) {
		return(NULL); /* no data */
	}

	/* We have data */

	/* Allocate a buffer for the line */
	current_length = 1;
	line_buffer = (char *)malloc(current_length);
	line_buffer[0] = '\0';

	/* Read the next line from the fifo */
	current_line = read_line();

	/* While we didn't hit the end of data marker
   * and we didn't run out of fifo data */
	while ((current_line != NULL)
      && (strcmp(current_line,EOD) != 0)) {
		/* If our buffer is too small */
		if ((strlen(current_line) + strlen(line_buffer)+1) > current_length) {
			/* Allocate new buffer and copy the old data over */
			temp = line_buffer;
			line_buffer = (char *)malloc(current_length+BUF_SIZE);
			memcpy(line_buffer,temp,current_length);
			current_length += BUF_SIZE;
			free(temp);
		}

		/* Add the current line to the buffer */
		if (strlen(line_buffer) > 0)
			strcat(line_buffer," ");
		strcat(line_buffer,current_line);

		free(current_line); /* memory leaks are bad */

		current_line = read_line();
	}

	if (current_line != NULL)
		free(current_line); /* memory leaks are bad */
	free(EOD);
	return(line_buffer);
}

void process_delay_time() {
	char *cur_line;

  /* Get the delay time */
	cur_line = read_line();
#ifdef DEBUG
	printf("Read delay_time:%s\n",cur_line);
#endif

	/* No delay time - exit */
	if (cur_line == NULL)
		return;
	if (strlen(cur_line) == 0)
		return;

	/* The delay time must be a number */
	if (is_numeric(cur_line)) {
		delay_time = atoi(cur_line);
		free(cur_line);
#ifdef DEBUG
		printf("Processed delay_time:%d\n",delay_time);
#endif
		return;
	}

	/* If it's not a number, it's bad data - ignore the command */
}

void process_char_delay() {
	char *cur_line;

  /* Get the delay time */
	cur_line = read_line();

	/* No char delay - exit */
	if (cur_line == NULL)
		return;
	if (strlen(cur_line) == 0)
		return;

	/* The delay time must be a number */
	if (is_numeric(cur_line)) {
		char_delay = atoi(cur_line);
		free(cur_line);
		return;
	}

	/* If it's not a number, it's bad data - ignore the command */
}

void process_line(int line_num) {
	int cur_timeout;
	char *cur_line;
	time_t now;

	time(&now);
	cur_timeout = get_timeout();
	if (cur_timeout < 0) {
		cur_timeout = 0;
	}

	cur_line = get_line();

	if (lines[line_num] != NULL)
		free(lines[line_num]);

	lines[line_num] = cur_line;
	timeout[line_num] = cur_timeout;
	refresh_time[line_num] = now;
}

int data_to_display() {
	int temp;
	int i;
	temp = 0;

	/* Look through all the lines */
	for (i=0; i<4; i++) {
		/* If the line isn't empty */
		if (lines[i] != NULL) {
			if (strlen(lines[i]) > 0) {
				return 1; /* we have data */
			}
		}
	}

	/* We only get here when no lines have data */
	return 0;
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
	pos[lineno]++;

	/* If we went past the end of the line,
	 * start over */
	if (pos[lineno] >= strlen(lines[lineno]))
		pos[lineno] = 0;

	/* Force an end of line */
	temp_line[PERT_DISPLAY_WIDTH] = '\0';
	return(temp_line);
}

int main(int argc, char *argv[]) {
	int stop_indicated;
	int processing_command;
	int i;
	time_t now;

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

#ifdef DEBUG
	printf("Device = %s\n",device_name);
	printf("Fifo = %s\n",fifo_name);
	printf("Delay time = %d\n",delay_time);
	printf("Char Delay time = %d\n",char_delay);
#endif

	/* Initialize arrays */
	time(&now);
	for(i=0;i<4;i++) {
		lines[i] = NULL;
		refresh_time[i] = now;
		timeout[i] = 0;
		pos[i] = 0;
	}

	/* Initialize the Pertelian */
  display_init(device_name);

	/* The backlight is on when the program starts */
	backlight_status = 1;
	backlight(1);

	/* Go daemon */
	if (daemon_init() != 0) {
		fprintf(stderr,"Failed to go daemon\n");
		return(1);
		}

	/* Try to open the fifo */
	if (!open_fifo(fifo_name)) {
		fprintf(stderr,"Error creating FIFO: %s\n",fifo_name);
		return(1);
	}

	/* Loop until we are told to stop */
	stop_indicated = 0;
	while (!stop_indicated) {
	 	time(&now);

		/* Get the command from the fifo */
	  processing_command = 1;
		while (processing_command) {
			switch (get_command()) {
				case backlight_on:
					backlight(1);
					backlight_status = 1;
					break;
				case backlight_off:
					backlight(0);
					backlight_status = 0;
					break;
				case stop:
					stop_indicated = 1;
					break;
				case line1:
					process_line(0);
					break;
				case line2:
					process_line(1);
					break;
				case line3:
					process_line(2);
					break;
				case line4:
					process_line(3);
					break;
				case delay_time_cmd:
					process_delay_time();
					break;
				case char_delay_cmd:
					process_char_delay();
					break;
				case backlight_mgt_on:
					backlight_mgt = 1;
					break;
				case backlight_mgt_off:
					backlight_mgt = 0;
					break;
				default:
					processing_command = 0; /* no command to process */
					break;
			}
		}

#ifdef DEBUG
		printf("main:processed command\n");
#endif

		/* Refresh the display */
		for(i=0;i<4;i++) {
			/* If the line has data */
			if (lines[i] != NULL) {
				/* If we are supposed to time the line out */
				if (timeout[i] > 0) {
					/* If the line is old */
					if (difftime(now,refresh_time[i]) > timeout[i]) {
						/* Get rid of the line */
						free(lines[i]); /* Memory leaks are bad */
						lines[i] = NULL;
					}
				}
			}

			/* Write out the line to the display */
			wrtln(i,fill_line(i,0));
		}

		/* If there was no data to display */
		if (!data_to_display()) {
			/* Let's put the date/time on the display */
			display_date_time();

			/* If the backlight is on,
			 * and backight mgt is on,
			 * turn the backlight off */
			if ((backlight_status == 1)
			&&  (backlight_mgt == 1))	{
				backlight(0);
				backlight_status=0;
			}
		} else {
			/* There was data to display.
			 * If the backlight is off,
			 * and backlight mangement is on,
			 * turn the backlight on */
			if ((backlight_status == 0)
			&&  (backlight_mgt ==1))	{
				backlight(1);
				backlight_status=1;
			}
		}

		/* Pause for a bit */
  	sleep_us(delay_time);
	}

	/* Display a useful message on the Pertelian */
	wrtln(0,"                    ");
	wrtln(1,"pertd daemon stopped");
	wrtln(2,"                    ");
	wrtln(3,"                    ");

	/* Clean up the connect to the Pertelian */
	display_close();

	/* Done - clean up */
	close_fifo(fifo_name);

	return(0);
}
