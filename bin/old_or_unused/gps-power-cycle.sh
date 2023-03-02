#!/bin/bash
#
# Power cycle the gps
#

compTo='USB-Serial Controller D'
for device in $(ls -d /sys/bus/usb/devices/*);
    do
        product=''
        if [ -e $device/product ];
        then
            product=`cat  $device/product`
        fi

        if [ "$product" == "$compTo" ];
        then
            echo 'Found gps, cycling power'
            echo $device
            echo $product
            echo suspend > $device/power/level
            echo 'gps off - sleeping 5 seconds'
            sleep 5
            echo on > $device/power/level
            echo 'gps on'
        fi

    done

