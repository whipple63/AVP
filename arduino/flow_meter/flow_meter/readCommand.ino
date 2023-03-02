  // check the serial port for an incoming command
  // commands will be processed upon receipt of a newline character
  
void readCommand() {
  
  char c = ' ';  // init to anything other than newline
  while (Serial.available()) {
    c = Serial.read();
    if (c == 8) { // backspace
      cmdBuf = cmdBuf.substring(0, cmdBuf.length()-1);
    } else {
      cmdBuf += c;
    }
  }
  
  if (c == '\n') {  // process the line
  
    if (cmdBuf.length() > 2) {  // if there's only a <cr><lf>, skip this
      cmdBuf.trim();  // trim off whitespace
      cmdBuf.toLowerCase();  // convert to lower case
      Serial.println("Processing command: " + cmdBuf);
      
      if (cmdBuf.startsWith(F("hiworld"))) {
        Serial.println(F("Hello, world!"));
      } else {
        
      if (cmdBuf.startsWith(F("water_off"))) {
        digitalWrite(waterValvePin, HIGH);
      } else {
        
      if (cmdBuf.startsWith(F("water_on"))) {
        digitalWrite(waterValvePin, LOW);
      } else {
               
      if (cmdBuf.startsWith(F("cal"))) {
        // next double is the new value
        if (cmdBuf.substring(4) != "") {
          double d = cmdBuf.substring(4).toDouble();
          if (d > 0) {  // constrain to possible values
              calibrationFactor = d;
              writeEEProm(EEpromCalFactorAddr, (unsigned int) (calibrationFactor * 100));   // stored as 100*value
          }
        }
        Serial.print(F("Calibration Factor: ")); 
        Serial.println(calibrationFactor);
      } else {

      if (cmdBuf.startsWith(F("help")) || cmdBuf.startsWith(F("?"))) {
        Serial.println(F("\nCommands Available:\n"));
        Serial.println(F("    water_off"));
        Serial.println(F("    water_on"));
        Serial.println(F("    cal <Factor>"));
        Serial.println(F("        Hall effect sensor value: 6.15"));
        Serial.println(F("        Vortex sensor value: 16.67"));
        Serial.println(F(""));
      } else {

        Serial.println("Bad command: " + cmdBuf);
      }}}}}
    }
    cmdBuf = "";
  }
}
