#include <stdio.h>
#include <sys/types.h>
#include <sys/time.h>
#include <stddef.h>

/* From Advanced Programming in the Unix Environment
 * by W. Richard Stevens. */

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
