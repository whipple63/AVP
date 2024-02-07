#!/bin/bash


PIC_DIR="/home/pi/webcam/"

TODAY=`date +%Y%m%d`
if [ ! -d "$PIC_DIR$TODAY" ]; then
    mkdir "$PIC_DIR$TODAY"
fi
cd "$PIC_DIR$TODAY"

HM=$(date +"_%H%M")

fswebcam -r 1920x1080 --delay 5 --skip 5 --bottom-banner $PIC_DIR$TODAY/$TODAY$HM.jpg

