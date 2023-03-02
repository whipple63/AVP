/* This is an example of how to write a program that sends commands to 
 * the pertd2 deamon */
#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>

int main() {
	FILE *fifo;
	char *fifo_name = "/tmp/pertd2.fifo";
	struct stat fifo_stat;

	/* Let's get some info on the fifo */
	if (stat(fifo_name,&fifo_stat) != 0) {
		printf("Unable to stat %s\n",fifo_name);
		/* If we can't stat the fifo, it's not there - we are done */
		return(1);
	}

	/* At this point, you can further interrigate the stat struct of the
	 * fifo to see if you can write to it, etc.  Such code is left to
	 * you do to as an exercise 8-) */

	/* Since the fifo exists, let's open it */
	if ((fifo = fopen(fifo_name,"a")) == 0) {
		printf("Unable to open %s\n",fifo_name);
		/* Obviously, we can't write to it if we can't open it.
		 * Note that we do need to check for existance first.  If the 
		 * file doesn't exist, the fopen will create it, which will
		 * cause problems when pertd2 starts up. */
		return(1);
	}

	/* We can use 1 big printf to print the command */
	fprintf(fifo,"line4\n30\n==EOD==\nThis is line 4\n==EOD==\n");

	/* Or we can do it with several printf's */
	fprintf(fifo,"line2\n");
	fprintf(fifo,"30\n");
	fprintf(fifo,"==EOD==\n");
	fprintf(fifo,"This is line 2\n");
	fprintf(fifo,"==EOD==\n");

  /* Or by using fputs */
	fputs("line3\n",fifo);
	fputs("30\n",fifo);
	fputs("==EOD==\n",fifo);
	fputs("This is line 3\n",fifo);
	fputs("==EOD==\n",fifo);

	fputs("line1\n",fifo);
	fputs("0\n",fifo);
	fputs("==EOD==\n",fifo);
	fputs("This is a really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("really, really, really,\n",fifo);
	fputs("long line\n",fifo);
	fputs("==EOD==\n",fifo);

	fclose(fifo);
}
