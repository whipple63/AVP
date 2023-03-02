#Used to initialize socat processes
port=$1
device=$2
/usr/bin/socat tcp-l:$port,reuseaddr,fork file:/dev/$device,nonblock,echo=0,raw,icrnl=0,igncr=0,waitlock=/run/lock/socat.$device.lockman &