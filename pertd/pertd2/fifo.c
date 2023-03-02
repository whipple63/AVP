#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <string.h>
#include <ctype.h>
#include <stdlib.h>

#define BUF_SIZE 512
char buffer[BUF_SIZE];
char *bufp=buffer;
int n = 0;
int fifo_fd;

int get_one_char() {
	/* If the buffer is empty */
	if (n <= 0) {
		/* Get some stuff */
		n = read(fifo_fd,buffer,BUF_SIZE);

		/* If we got some stuff */
		if (n > 0) {
			/* Point back to the start of the buffer */
			bufp = buffer;
		} else { /* we didn't get any stuff */
			return(EOF);
		}
	}
	n--; /* Decrement the number of chars in the buffer */
	return(*bufp++);
}

char *read_line() {
	char *line, *temp_line;
	int current_max_line;
	int i;
	int char_read;

#ifdef DEBUG
  printf("read_line - start\n");
#endif

	/* Any data in the fifo? */
	char_read = get_one_char();

	/* No. */
	if (char_read == EOF) {
		return(NULL); /* No data */
	}
	if (char_read == 0) {
		return(NULL); /* No data */
	}

	/* We have data */

	/* Allocate some memory to put the line */
	current_max_line = BUF_SIZE;
	line = (char *)malloc(current_max_line);
	i = 0;

  /* While we didn't hit the end of line */
	while((char_read != '\n')
     && (char_read != EOF)
 		 && (char_read != 0)) {

		/* If our buffer is too small */
		if (i >= current_max_line) {
			/* Reallocate it */
			temp_line = line;
			line = (char *)malloc(current_max_line+BUF_SIZE);
			memcpy(line,temp_line,current_max_line);
			current_max_line+=BUF_SIZE;
			free(temp_line);
		}

		/* Put the new character into the line */
		line[i] = char_read;

		/* Get the next character */
		i++;
		char_read = get_one_char();
		}
	line[i] = '\0'; /* terminate the string */

#ifdef DEBUG
  printf("read_line: line=%s\n",line);
#endif

	return(line);
}

void close_fifo(char *fifo_file_name) {
  /* If we opened it, close it */
  if (fifo_fd >= 0) {
    close(fifo_fd);
    }

#ifdef DEBUG
  printf("FIFO closed:%s\n",fifo_file_name);
#endif

  /* We are done - clean up */
  unlink(fifo_file_name);

#ifdef DEBUG
  printf("FIFO deleted\n");
#endif
}

int open_fifo(char *fifo_file_name) {
  /* Make the fifo */
  if (mkfifo(fifo_file_name,O_RDWR|O_CREAT|O_NOCTTY) != 0) {
    fprintf(stderr,"Error creating FIFO: %s\n",fifo_file_name);
    return(0);
  }

#ifdef DEBUG
  printf("FIFO created\n");
#endif

  /* Set the permissions on the fifo
     so that everyone can write to it
     but only owner can read from it. */
  if (chmod(fifo_file_name,S_IWUSR|S_IRUSR|S_IWGRP|S_IWOTH) < 0) {
    fprintf(stderr,"Unable to change permissions on FIFO\n");
		close_fifo(fifo_file_name);
    return(0);
    }

  /* Open the fifo for reading */
  if ((fifo_fd=open(fifo_file_name,O_RDONLY|O_NONBLOCK)) < 0) {
    fprintf(stderr,"Error opening FIFO for reading\n");
		close_fifo(fifo_file_name);
    return(0);
    }

#ifdef DEBUG
  printf("FIFO opened\n");
#endif

	return(1);
}
