

// checkIfMoving -- wait a while to see if the winch starts moving
//
// If the winch is not moving when expected, it is an indication of
// a serious error condition.  The system could be mechanically jammed, or
// the encoder may have malfunctioned.  The motor must be stopped.  For example,
// if the encoder pulses are missing, the motor will take off at full speed and never stop.
//
// Check to see if we still have a connection with the encoder by seeing if the
// velocity goes up.
//
void checkIfMoving() {
  int waitTime = 0;
  //  int maxWait = 3000;  // max wait time in ms (ideally less than LOOP_INTERVAL so that feedback stays on schedule)
  int maxWait = 2500;  // max wait time in ms (ideally less than LOOP_INTERVAL so that feedback stays on schedule)
  ApplicationMonitor.SetData(2);  // any 32 bit value, anywhere in the code

  while (waitTime <= maxWait) {
    delay(100);
    waitTime += 100;

    MCtrl.readController();  // read the values
    Serial.print(waitTime); Serial.print(" ms.  "); Serial.print("Check if moving - current speed: "); Serial.println(MCtrl.getCurrSpd());
    if (abs(MCtrl.getCurrSpd()) >= 1) { break; }
    ApplicationMonitor.IAmAlive();  // ping the watchdog timer
  }
  if (abs(MCtrl.getCurrSpd()) < 1) {
    MCtrl.stopMoving();
    sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("ERROR: Speed not increasing. Possibly lost position encoder data or drum not turning."), true);
  }
  ApplicationMonitor.IAmAlive();  // ping the watchdog timer
  ApplicationMonitor.SetData(1);  // any 32 bit value, anywhere in the code
}



boolean isValidNumber(String str){
   boolean isNum=false;
   boolean plusminusFound = false;
   boolean decimalFound = false;
   
   str.trim();  // remove any whitespace
   
   for(byte i=0;i<str.length();i++)
   {
     // plus or minus must be first and there can only be one
     if (isNum==false && decimalFound==false && plusminusFound == false && (str.charAt(i) == '+' || str.charAt(i) == '-') ) {
       plusminusFound = true;
       continue;
     }
     // there can only be one decimal point
     if (decimalFound == false && str.charAt(i) == '.') {
       decimalFound = true;
       continue;
     }
     // everything else must be a digit
     isNum = isDigit(str.charAt(i));
     if(!isNum) return false;
   }
   return isNum;
}


//
// save the current position and the total run time to EEPROM
// will be restored on power-up
//
// NOTE: I cannot get the savepos and/or pospwrup feature of the MM3 controller to work.
// These data will be saved to the Arduino EEPROM instead.
//
void saveState() {
  MCtrl.readController(); // update the position
  EepromAccess.writeEEPromLong(EepromAccess.SAVED_POSITION, long(MCtrl.getCurrPos()*1000));  // save the current position
  delay(4);               // the write takes some time
  Motor.setIdleTime(0L);  // indicate that the state has been saved to keep from auto-saving
  Motor.setMotorTimeDays(Motor.getMotorTimeDays()); // save the total motor run time
}

// return the total uptime in parts
int upHours()   { return int(millis() / 3600000);      }
int upMinutes() { return int((millis() / 60000  ) % 60); }
int upSeconds() { return int((millis() / 1000   ) % 60); }


void software_Reboot() {
  // since the watchdog timer is enabled, all we do is get stuck and wait
  while (1) {}
}

int freeRam()
{
  extern int __heap_start, *__brkval;
  int v;
  return (int)&v - (__brkval == 0 ? (int)&__heap_start : (int)__brkval);
}
