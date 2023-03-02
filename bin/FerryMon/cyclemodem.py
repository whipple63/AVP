from gpiozero import LED
from time import sleep

modem_relay = LED(17)

print("Power cycle the modem in 10 seconds")
sleep(10)
print("Powering modem down now")

modem_relay.on()
sleep(15)
modem_relay.off()
