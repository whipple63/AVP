import piplates.DAQCplate as dp
import time
print("Power cycle the modem in 10 seconds")
time.sleep(10)
print("Powering modem down now")
dp.setDOUTbit(0,0)
time.sleep(15)
dp.clrDOUTbit(0,0)
