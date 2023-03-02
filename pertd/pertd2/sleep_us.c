#include <stdio.h>
#include <sys/types.h>
#include <sys/time.h>
#include <stddef.h>

/* From Advanced Programming in the Unix Environment
 * by W. Richard Stevens. */

/* Sleep for a number of microseconds */
void sleep_us1(unsigned int nusecs) {
	usleep(nusecs);
}

void sleep_us(unsigned int nusecs) {
	struct timeval tval;

	/* If we don't need to sleep then leave */
	if (nusecs < 1) {
		return;
	}

	tval.tv_sec = nusecs / 1000000L;
	tval.tv_usec = nusecs % 1000000L;
	select(0,NULL, NULL, NULL, &tval);
}

void sleep_us_loop(unsigned int nusecs) {
	volatile int i;
	for (i = 0; i < nusecs*200; i++) {
		}
}

void sleep_us_ns(unsigned int nusecs) {
	struct timespec tval;
	/* Input is number of microseconds.
	 * 1 second = 1000000 microseconds.
	 * 1 second = 1000000000 nanoseconds
	 */
	tval.tv_sec = nusecs / 1000000L;
	/* Note that nsec = microseconds */
	tval.tv_nsec = nusecs % 1000000L;
	/* So we need to conert it to nanoseconds */
	tval.tv_nsec = tval.tv_nsec * 1000;
	nanosleep(&tval,&tval);
}
