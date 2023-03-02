pertd2:	pertd2.o pert_interf.o sleep_us.o fifo.o
	cc	pertd2.o pert_interf.o sleep_us.o fifo.o -o pertd2

debug:	pertd2.c pert_interf.o sleep_us.o fifo.o
	cc -DDEBUG -c -o fifo.o fifo.c
	cc -DDEBUG -c -o sleep_us.o sleep_us.c
	cc -DDEBUG -c -o pert_interf.o pert_interf.c
	cc -DDEBUG -c -o pertd2.o pertd2.c
	cc	pertd2.o pert_interf.o sleep_us.o fifo.o -o pertd2

pert_interf.o: pert_interf.c
	cc    -c -o pert_interf.o pert_interf.c

pertd2.o: pertd2.c pert_interf.h sleep_us.h fifo.h
	cc    -c -o pertd2.o pertd2.c

sleep_us.o: sleep_us.c
	cc    -c -o sleep_us.o sleep_us.c

fifo.o: fifo.c
	cc    -c -o fifo.o fifo.c
