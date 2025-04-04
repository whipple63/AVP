#!/bin/bash
set -x

PIC_DIR="/mnt/nas/phillipsisland/cameras/cam1/"
WEBPIC_DIR="/mnt/nas/phillipsisland/cameras/cam1/"

YESTERDAY=`date --date="-1 day" +%Y%m%d`
TODAY=`date +%Y%m%d`

if [ ! -d "$PIC_DIR$YESTERDAY" ]; then
    mkdir "$PIC_DIR$YESTERDAY"
fi
cd "$PIC_DIR$YESTERDAY"

timeout -s 2 119s lftp sftp://pi:ims6841@phillipsisland.dyndns.org -p 7888 -e "mirror --only-newer -v /home/pi/cameras/cam1/$YESTERDAY/ .; bye"


if [ ! -d "$PIC_DIR$TODAY" ]; then
    mkdir "$PIC_DIR$TODAY"
fi
cd "$PIC_DIR$TODAY"

timeout -s 2 119s lftp sftp://pi:ims6841@phillipsisland.dyndns.org -p 7888 -e "mirror --only-newer -v /home/pi/cameras/cam1/$TODAY/ .; bye"

LATESTIMAGE=`ls -t $PIC_DIR$TODAY/*.jpg | head -1`
cp $LATESTIMAGE $WEBPIC_DIR"latest.jpg"
