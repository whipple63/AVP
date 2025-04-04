#!/bin/bash
#
set -x

NUMCAMS=1 #for future use

TODAY=`date +%Y%m%d`
HMS=$(date +"_%H%M%S")

# loop for each camera
#for i in 1
for (( i=1; i<=$NUMCAMS; i+=1 ))	
do
	# append cam#/ after each directory operation
	PIC_DIR="/home/pi/cameras/cam"$i"/"

	if [ ! -d "$PIC_DIR$TODAY" ]; then
		mkdir "$PIC_DIR$TODAY"
	fi
	cd "$PIC_DIR$TODAY"

	wget --no-check-certificate --http-user=root --http-password="2C|not2see" https://192.168.1.110/jpg/image.jpg?resolution=2688x1520

	# change to a permanent date named filename
	mv "image.jpg?resolution=2688x1520" $TODAY$HMS".jpg"
done
