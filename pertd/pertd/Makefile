pertd:	pertd.o pert_interf.o sleep_us.o
	cc	pertd.o pert_interf.o sleep_us.o -o pertd

debug:	pertd.c pert_interf.o sleep_us.o
	cc  -DDEBUG  -c -o pertd.o pertd.c
	cc	pertd.o pert_interf.o sleep_us.o -o pertd

pert_interf.o: pert_interf.c
	cc    -c -o pert_interf.o pert_interf.c

pertd.o: pertd.c pert_interf.h sleep_us.h
	cc    -c -o pertd.o pertd.c

sleep_us.o: sleep_us.c
	cc    -c -o sleep_us.o sleep_us.c
