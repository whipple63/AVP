#!/usr/bin/expect -f

# Used to turn off computer and prevent watchdog from restarting
# This script logs in to modem, and turns off power relay to controller.
# This will turn off processor and it won't recover!

#exp_internal 1 this turns on debugging

#
# This version is for the bluetree modem
#
set timeout 20

spawn telnet 192.168.0.1 6070
expect "password:"
send "ims6841\r";
expect "PASS"
send "at+bdoset=do1,1\r"
#send "at+bdoset?\r"
expect "OK"
