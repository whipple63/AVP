
void checkButtonPress(int sensorValue) { 
  // First check the low tension button
  if (digitalRead(loSetButton) == LOW) {
    buttonPressTime = millis();
    while ( digitalRead(loSetButton) == LOW ) {delay(100);   ApplicationMonitor.IAmAlive();};
    if ( millis() - buttonPressTime < longPressTime ) {
      loThresh = sensorValue;
      writeLo = true;
      flashLEDs(1,250);
    }
    else { // Long Press
      minVal = sensorValue;
      writeMin = true;
      flashLEDs(4,250);
    }
  }
  // Now check High Tension Button
  if (digitalRead(hiSetButton) == LOW) {
    buttonPressTime = millis();
    while ( digitalRead(hiSetButton) == LOW ) {delay(100);   ApplicationMonitor.IAmAlive();};
    if ( millis() - buttonPressTime < longPressTime ) {
      hiThresh = sensorValue;
      writeHi = true;
      flashLEDs(1,250);
    }
    else { // Long Press
      maxVal = sensorValue;
      writeMax = true;
      flashLEDs(4,250);
    }
  }
}
 
void flashLEDs(unsigned int flashCount, unsigned int flashDuration) {
  bar.blinkRate(1);
  bar.writeDisplay();
  for (int i = 0 ; i < flashCount ; i++ ) {
    digitalWrite(hiTensionLEDpin, HIGH);
    digitalWrite(loTensionLEDpin, HIGH);
    delay(flashDuration);
    ApplicationMonitor.IAmAlive();
    digitalWrite(hiTensionLEDpin, LOW);
    digitalWrite(loTensionLEDpin, LOW);
    delay(flashDuration);
    ApplicationMonitor.IAmAlive();
  }
  digitalWrite(hiTensionLEDpin, HIGH);
  digitalWrite(loTensionLEDpin, HIGH);
  delay(flashDuration);
  ApplicationMonitor.IAmAlive();
  bar.blinkRate(0);
  bar.writeDisplay();
}

void software_Reboot() {
  // since the watchdog timer is enabled, all we do is get stuck and wait
  while(1){}
}

