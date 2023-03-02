/*
 * Code from:
 * A small demo program to show how to drive the Pertelian X2040 USB LCD
 * display from Linux.
 *
 * Note that this comes without any warranty. 
 * This worked fine for me, and I am unaware of any problem, but if this
 * program causes a problem to you or your hardware you are on your own and
 * I will not be liable for damages in any way.
 * If this is not acceptable to you, you are not allowed to use this program.
 *
 * Otherwise you are free to use this program as you see fit provided that
 * - you do not pretent having written this yourself
 * - changes you make are clearly identified as such
 *
 * Information on how to program the device mainly came from
 * http://pertelian.com/index.php?option=com_content&task=view&id=27&Itemid=33
 * and some small local experiments
 *
 *   Frans Meulenbroeks 
 */

#include <stdio.h>
#include <time.h>
#include <string.h>
#include <stdlib.h>
#include <fcntl.h>
#include <termios.h>
#include <unistd.h>
#include "sleep_us.h"

/* Ron Lauzon - 7/16/2006
 * Changed DELAY to mean milliseconds and removed the delay()
 * function.  I replaced it with a sleep_us for DELAY microseconds.
 * A 1 ms pause seems sufficient.  No pause will generate garbled
 * output on the display */

/* Ron Lauzon - 3/14/2007
 * Changed the device interface to use file handles instead of FILE.
 * This allows me to set serial port attributes (like speed).
 */

/* DELAY is constant used to generate some delay. 
 * You might want to tweak it for your hardware.
 * If the value is too small some or all of the data is going to be garbled
 * or the initialisation will fail.
 * If the value is too large you'll have to wait quite a while....
 */
/*#define DELAY 1 */

int pert_fd; /* file descriptor to the Pertelian */
unsigned int char_delay;

const static unsigned char rowoffset[4] =
	{ 0x80, 0x80+0x40, 0x80 + 0x14, 0x80 + 0x40 + 0x14 };
/* offsets to address the various rows. 
 * the addressing structure is a little bit odd. actually row 3 is a
 * continuation of row 1 and row4 of row2
 */

/*
 * delay
 *     This function introduces some delay. After writing a character to 
 *     the display one needs to wait a short while. This is achieved by the 
 *     code below. Actually there are two different delays for the device
 *     but this code does not make the distinction.
 */
/*void delay(int n) {
	volatile int i;
	for (i = 0; i < n; i++) {
		}
	} */

/*
 * wrtch
 *     This function writes a character byte to the device
 */
void wrtch(char c) {
	if (write(pert_fd,&c,1) != 1)
		fprintf(stderr,"Error writing to pert: %s\n",c);
	tcdrain(pert_fd);
	sleep_us(char_delay);
	}

/*
 * putcode
 *  This function writes a code byte to the device
 */
void putcode(char code) {
	wrtch((char)0xfe);
	wrtch(code);
	sleep_us(char_delay);
	}

/*
 * wrt
 *     This function writes a character string to the device (0 terminated)
 *     it writes the data to whereever the cursor is pointing
 */
void wrt(char *p) {
	while(*p) {
		wrtch(*p);
		p++;
		}
	}

/*
 * wrtln
 *     This function writes a character string to a specific row
 */
void wrtln(int row, char *p) {
	putcode(rowoffset[row]);
	wrt(p);
	}

/* display_init - initialize the Pertelian */
void display_init(char *device_name) {
	struct termios term;

	pert_fd = open(device_name, O_WRONLY | O_NONBLOCK);
	if (pert_fd < 0) {
		fprintf(stderr, "Cannot open device %s for writing !\n", device_name);
		exit(EXIT_FAILURE);
		}

	/* Get the tty config */
  if (tcgetattr(pert_fd,&term) < 0) {
		fprintf(stderr,"Unable to get terminal attributes\n");
		exit(EXIT_FAILURE);
	}

	/* set the terminal attributes */
	term.c_cflag = CRTSCTS | CS8 | CLOCAL | CREAD;
	term.c_iflag = ICRNL | IGNPAR;
	term.c_oflag = 0;
	term.c_lflag = 0;
	term.c_cc[VMIN] = 1;
	term.c_cc[CTIME] = 0;
	cfsetispeed(&term,B38400);
	cfsetospeed(&term,B38400);

	/* Flush any trash on the line */
	tcflush(pert_fd,TCIFLUSH);

	/* Sent the new attributes to the port */
	if (tcsetattr(pert_fd,TCSANOW,&term) < 0) {
		fprintf(stderr,"Unable to set terminal attributes\n");
		exit(EXIT_FAILURE);
	}

	/* We are connected - now set up the Pertelian */
	putcode(0x38); /* initialise display (8 bit interface, shift to right */
	putcode(0x06); /* cursor move direction to the right, no automatic shift */
	putcode(0x10); /* move cursor on data write */
	putcode(0x0c); /* cursor off */
	putcode(0x01); /* clear display */
	}

void display_close() {
	close(pert_fd);
	}

void backlight(int on) {
	if (on)
		putcode(0x03); /* backlight on (3 = on, 2 = off) */
	else
		putcode(0x02);
}
