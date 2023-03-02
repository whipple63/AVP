  // check the serial port for an incoming command to set the threshold value(s)
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

      if (cmdBuf.startsWith(F("hithresh"))) {
        // next int is the new threshold value
        if (cmdBuf.substring(9) != "") {
          int i = cmdBuf.substring(9).toInt();
          if (i > minVal && i < maxVal) {  // constrain to possible values
            hiThresh = i;
            writeHi = true;
          }
        }
        Serial.print(F("hiThresh: ")); 
        Serial.println(hiThresh);
      } else {
    
      if (cmdBuf.startsWith(F("lothresh"))) {
        // next int is the new threshold value
        if (cmdBuf.substring(9) != "") {
          int i = cmdBuf.substring(9).toInt();
          if (i > minVal && i < maxVal) {  // constrain to possible values
            loThresh = i;
            writeLo = true;
          }
        }
        Serial.print(F("loThresh: "));
        Serial.println(loThresh);
      } else {
        
      if (cmdBuf.startsWith(F("tensiondelay"))) {
        // next int is the new value
        if (cmdBuf.substring(13) != "") {
          int i = cmdBuf.substring(13).toInt();
          if (i >= 0 && i < 10000) {  // constrain values
            tensionDebounceTime = i;
            writeTensionDelay = true;
          }
        }
        Serial.print(F("tensionDelay: "));
        Serial.println(tensionDebounceTime);
      } else {
        
      if (cmdBuf.startsWith(F("limitdelay"))) {
        // next int is the new value
        if (cmdBuf.substring(11) != "") {
          int i = cmdBuf.substring(11).toInt();
          if (i >= 0 && i < 10000) {  // constrain values
            limitDebounceTime = i;
            writeLimitDelay = true;
          }
        }
        Serial.print(F("limitDelay: "));
        Serial.println(limitDebounceTime);
      } else {
        
      if (cmdBuf.startsWith(F("reboot"))) {
        ApplicationMonitor.SetData(255);  // indicates a reboot
        Serial.println(F("Rebooting system in 2 seconds."));
        software_Reboot();
      } else {
        
      if (cmdBuf.startsWith(F("clearreports"))) {
        ApplicationMonitor.ClearReports();
        Serial.println(F("Application Monitor Reports Cleared."));
      } else {
        
      if (cmdBuf.startsWith(F("ver"))) {
        Serial.println(SWVERSION);
      } else {
        
      if (cmdBuf.startsWith(F("help")) || cmdBuf.startsWith(F("?"))) {
        Serial.println(F("\nCommands Available:\n"));
        Serial.println(F("    hithresh xxx"));
        Serial.println(F("    lothresh xxx"));
        Serial.println(F("    tensiondelay xxx"));
        Serial.println(F("    limitdelay xxx"));
        Serial.println(F("    reboot"));
        Serial.println(F("    clearreports"));
        Serial.println(F("    ver"));
        Serial.println(F(""));
      } else {

        Serial.println("Bad command: " + cmdBuf);
      }}}}}}}}}
    }
    cmdBuf = "";
  }
}
