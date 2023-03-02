KERNELVERSION=$(shell uname -r)
DEST=/lib/modules/$(KERNELVERSION)/kernel/drivers/watchdog

obj-m := w83627hf_wdt.o

all:
	make -C /usr/src/linux-headers-$(KERNELVERSION) M=$(PWD) modules

install:
	cp --backup=t w83627hf_wdt.ko $(DEST)

