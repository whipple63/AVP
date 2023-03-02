/*
  tension_and_limit
  Intelligent winch tension and limit switch processor.
  
  Reads the value of the tension sensor as an anaolg input (0-5V), two
  limit switch inputs interpreted as an upper and a lower limit switch, and
  disable lines for the noRaise and noLower condition.  Outputs digital lines
  indicating noRaise and noLower for connection to a motor controller.  High
  and low tension thresholds and onset delays for tension and limit switches
  are programmable.  noRaise is set by high tension or the upper limit switch
  after the onset delay if not disabled.  noLower is set by low tension or the 
  lower limit switch after the onset delay if not disabled.  All logic lines
  are active when low.
  
  High and low tension thresholds and the tension and limit delay values are
  stored in EEPROM and are consistent across restarts.  Delays are either 
  hard-coded or set via the command interface.  Threshold values can be hard
  coded, set via the command interface, or set using a pair of set-now buttons
  that will set the high/low tension threshold to the current value when pressed.
  
  
  Serial Interface
  
  Outputs a string of the following values once per second
  
      Example: 458, 40.78, 46.47, 1, 1, 1, 1, 1, 1
      
    raw analog input value
    percentage of operating range (between low and high thresholds)
    percentage of full range
    no raise digital line  (digital lines are logic 0 active)
    no lower digital line
    high limit switch
    low limit switch
    high threshold (LOW tension)
    low threshold (HIGH tension)
    
    Other information will be output at startup and in response to user commands.
    
    
 Input commands available
 
   Given no numeric (XXX) argument will reply with "variablename: value"
   Sets variable to given numeric value.  Still replies as above.
     hithresh XXX
     lothresh XXX
     tensiondelay XXX
     limitdelay XXX
     reboot
     clearreports
 */
 
#include <EEPROM.h>
#include "ApplicationMonitor.h"

Watchdog::CApplicationMonitor ApplicationMonitor;

// pin definitions
const int analogIn = A0;
const int noLowerOutPin = 3;  // logic low is activated
const int noRaiseOutPin = 2;  // logic low is activated
const int noLowerDisablePin = 5;  // configured with internal pullup resistor - switch to ground to activate
const int noRaiseDisablePin = 4;  // configured with internal pullup resistor - switch to ground to activate
const int limitInHi = 11;    // configured with internal pullup resistor - switch to ground to activate
const int limitInLo = 10;    // configured with internal pullup resistor - switch to ground to activate
const int hiTensionLEDpin = 8;  // logic low is activated
const int loTensionLEDpin = 9;  // logic low is activated
const int loSetButton = A1;  // configured with internal pullup resistor - switch to ground to activate (analog inputs)
const int hiSetButton = A2;  // configured with internal pullup resistor - switch to ground to activate (analog inputs)


// These defaults are superceded by values in EEPROM if they exist
int minVal = 113;    // min and max possible values
int maxVal = 426;
int hiThresh = 350;  // above which the high output is turned on
int loThresh = 150;  // below which the low output is turned on

const int EEpromHiThreshAddr = 101;  // two byte long values to store thresholds
const int EEpromLoThreshAddr = 103;
const int EEpromTDelayAddr = 105;
const int EEpromLDelayAddr = 107;
const int EEpromMaxValAddr = 109;
const int EEpromMinValAddr = 111;

boolean writeHi = false;
boolean writeLo = false;
boolean writeTensionDelay = false;
boolean writeLimitDelay = false;
boolean writeMax = false;
boolean writeMin = false;

int msCounter = 0;         // ms counter for loop timing


unsigned long longPressTime = 3000;
// These defaults are superceded by values in EEPROM if they exist
unsigned long tensionDebounceTime = 500;  // ms delay for hi/lo tension
unsigned long limitDebounceTime = 250;      // ms delay for limit switch

unsigned long tensionTripTime = 0;
unsigned long limitTripTime = 0;
unsigned long buttonPressTime = 0;

String cmdBuf = "";



// the setup routine runs once when you press reset:
void setup() {
  // initialize serial communication at 9600 bits per second:
  Serial.begin(9600);
  
  pinMode(noLowerOutPin, OUTPUT);
  pinMode(noRaiseOutPin, OUTPUT);
  pinMode(hiTensionLEDpin, OUTPUT);
  pinMode(loTensionLEDpin, OUTPUT);
  digitalWrite(noRaiseOutPin, HIGH);
  digitalWrite(noLowerOutPin, HIGH);
  digitalWrite(hiTensionLEDpin, HIGH);
  digitalWrite(loTensionLEDpin, HIGH);
  
  
  pinMode(limitInHi, INPUT_PULLUP);
  pinMode(limitInLo, INPUT_PULLUP);
  pinMode(loSetButton, INPUT_PULLUP);
  pinMode(hiSetButton, INPUT_PULLUP);
  pinMode(noLowerDisablePin, INPUT_PULLUP);
  pinMode(noRaiseDisablePin, INPUT_PULLUP);
  
  Serial.println("");
  Serial.println(F("Intelligent winch tension and limit switch processor."));
  Serial.println("");
  
  
  ApplicationMonitor.Dump(Serial);
  ApplicationMonitor.EnableWatchdog(Watchdog::CApplicationMonitor::Timeout_2s);
  Serial.println("");

  unsigned int eeHi = readEEProm(EEpromHiThreshAddr);
  unsigned int eeLo = readEEProm(EEpromLoThreshAddr);
  
  Serial.print(F("Threshold values from EEPROM for hi and low read as: "));
  Serial.print( eeHi );
  Serial.print(F(", "));
  Serial.println( eeLo );
  
  if (eeHi != 65535) {
    hiThresh = (int) eeHi;
  }
  if (eeLo != 65535) {
    loThresh = (int) eeLo;
  }
  Serial.print(F("Threshold values for hi and low are currently set to: "));
  Serial.print( hiThresh );
  Serial.print(F(", "));
  Serial.println( loThresh );
  
  Serial.println("");

  unsigned int td = readEEProm(EEpromTDelayAddr);
  unsigned int ld = readEEProm(EEpromLDelayAddr);
  
  Serial.print(F("Tension and limit delay times from EEPROM read as: "));
  Serial.print( td );
  Serial.print( ", ");
  Serial.println( ld );
  
  if (td != 65535) {
    tensionDebounceTime = (unsigned long) td;
  }
  if (ld != 65535) {
    limitDebounceTime = (unsigned long) ld;
  }
  Serial.print(F("Tension and limit delay times are currently set to: "));
  Serial.print( tensionDebounceTime );
  Serial.print(F(" ms, "));
  Serial.print( limitDebounceTime );
  Serial.println(F(" ms"));
  Serial.println("");

  
  unsigned int eeMax = readEEProm(EEpromMaxValAddr);
  unsigned int eeMin = readEEProm(EEpromMinValAddr);
  
  Serial.print(F("Threshold values from EEPROM for max and min read as: "));
  Serial.print( eeMax );
  Serial.print(F(", "));
  Serial.print( eeMin );
  Serial.println( "");
  
  if (eeMax != 65535) {
    maxVal = (int) eeMax;
  }
  if (eeMin != 65535) {
    minVal = (int) eeMin;
  }
  Serial.print(F("Threshold values for hi and low are currently set to: "));
  Serial.print( maxVal );
  Serial.print(F(", "));
  Serial.println( minVal );
  
  cmdBuf.reserve(30);  // reserve some space for the command buffer to avoid memory fragmentation
  
  
}

unsigned int readEEProm(int addr) {
  byte b1 = EEPROM.read(addr);
  byte b2 = EEPROM.read(addr+1);
  return (unsigned int) b1 * 256 + (unsigned int) b2;
}

// the loop routine runs over and over again forever:
// Note that high tension is associated with low values from the sensor.
void loop() {  
  ApplicationMonitor.IAmAlive();  // ping the watchdog timer
  ApplicationMonitor.SetData(1);  // any 32 bit value, anywhere in the code
  
  // read the inputs
  int sensorValue = analogRead(analogIn);
  int limitHi = digitalRead(limitInHi);
  int limitLo = digitalRead(limitInLo);
  int noLowerDisable = digitalRead(noLowerDisablePin);
  int noRaiseDisable = digitalRead(noRaiseDisablePin);
  
  
  // Check inputs, using turn-on delays if tripped
  if (sensorValue > hiThresh) {  // This indicates LOW tension
    digitalWrite(loTensionLEDpin, LOW);
    if (tensionTripTime == 0) {
      tensionTripTime = millis();
    }
    // second part of this says if we go too high, set the output without delay
    if ( ((millis() >= tensionTripTime + tensionDebounceTime) || (sensorValue > maxVal * 0.95))
          && noLowerDisable == HIGH) {
      digitalWrite(noLowerOutPin, LOW);
    }
  } else { digitalWrite(loTensionLEDpin, HIGH); }
  
  if (sensorValue < loThresh) {  // This indicates HIGH tension
    digitalWrite(hiTensionLEDpin, LOW);
    if (tensionTripTime == 0) {
      tensionTripTime = millis();
    }
    if ( ((millis() >= tensionTripTime + tensionDebounceTime) || (sensorValue < minVal + maxVal * 0.05))
        && noRaiseDisable == HIGH) {
      digitalWrite(noRaiseOutPin, LOW);
    }
  } else { digitalWrite(hiTensionLEDpin, HIGH); }
  
  if (limitHi==LOW) { // Top limit switch tripped
    if (limitTripTime == 0) {
      limitTripTime = millis();
    }
    if (millis() >= limitTripTime + limitDebounceTime && noRaiseDisable == HIGH) {
      digitalWrite(noRaiseOutPin, LOW);
    }
  }
  
  if (limitLo==LOW) { // Bottom limit switch tripped
    if (limitTripTime == 0) {
      limitTripTime = millis();
    }
    if (millis() >= limitTripTime + limitDebounceTime && noLowerDisable == HIGH) {
      digitalWrite(noLowerOutPin, LOW);
    }
  }
  
  // Clear noLower if conditions are met
  if ( noLowerDisable==LOW || (sensorValue <= hiThresh && limitLo==HIGH) ) {
    digitalWrite(noLowerOutPin, HIGH);
  }
  
  // Clear noRaise if conditions are met
  if ( noRaiseDisable==LOW || (sensorValue >= loThresh && limitHi==HIGH) ) {
    digitalWrite(noRaiseOutPin, HIGH);
  }

  // Only when there are no faults do we reset the delays
  if (sensorValue >= loThresh && sensorValue <= hiThresh
      && limitHi==HIGH && limitLo==HIGH) {  // All clear
    tensionTripTime = 0;
    limitTripTime = 0;
  }    


  // check the serial port for an incoming command to set the threshold value(s)
  // commands will be processed upon receipt of a newline character
  char c = ' ';  // init to anything other than newline
  while (Serial.available()) {
    c = Serial.read();
    cmdBuf += c;
  }
  if (c == '\n') {  // process the line
    Serial.println("Processing command: " + cmdBuf);
    cmdBuf.trim();  // trim off whitespace
    cmdBuf.toLowerCase();  // convert to lower case
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
    }
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
    }
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
    }      
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
    }    
    if (cmdBuf.startsWith(F("reboot"))) {
      ApplicationMonitor.SetData(255);  // indicates a reboot
      Serial.println(F("Rebooting system in 2 seconds."));
      software_Reboot();
    }    
    if (cmdBuf.startsWith(F("clearreports"))) {
      ApplicationMonitor.ClearReports();
      Serial.println(F("Application Monitor Reports Cleared."));
    }    
    cmdBuf = "";
  }

  
  // check the hi and lo set buttons for new threshold values
  // If the low threshold is set to a value higher than the high threshold or
  // vice-versa the system will fail. (It will never reset the delays.)  This might
  // be fixable, but the condition doesn't make sense.
  checkButtonPress(sensorValue);
  /*
  if (digitalRead(loSetButton) == LOW) {
    loThresh = sensorValue;
    writeLo = true;
  }
  if (digitalRead(hiSetButton) == LOW) {
    hiThresh = sensorValue;
    writeHi = true;
  }
  */
  


  //
  // once per second  
  //  output serial data
  //  write thresholds to eeprom if necessary
  //
  if (msCounter == 1000) {
    Serial.print( sensorValue );
    Serial.print(", ");
    // print out the value as percentage of operating range
    Serial.print( 100.0*((float)(sensorValue - loThresh) / (hiThresh - loThresh)) );
    Serial.print(", ");
    // print out the value as percentage of total range
    Serial.print( 100.0*((float)(sensorValue - minVal) / (maxVal - minVal)) );
    Serial.print(", ");
    // print all of the digital values
    Serial.print( digitalRead(noRaiseOutPin) );    
    Serial.print(", ");
    Serial.print( digitalRead(noLowerOutPin) );    
    Serial.print(", ");
    Serial.print( limitHi );    
    Serial.print(", ");
    Serial.print( limitLo );    
    Serial.print(", ");
    Serial.print( !(sensorValue > hiThresh) );    
    Serial.print(", ");
    Serial.print( !(sensorValue < loThresh) );    
    Serial.println("");  // finally send the newline

    // If a write to EEPROM is requested do it here at a slower loop pace
    // so that a whole lot of writes don't happen if the value is unstable
    // while the button is pressed.
    if (writeHi == true) {
      writeEEProm(EEpromHiThreshAddr, hiThresh);
      writeHi = false;
    }
    if (writeLo == true) {
      writeEEProm(EEpromLoThreshAddr, loThresh);
      writeLo = false;
    }
    if (writeTensionDelay == true) {
      writeEEProm(EEpromTDelayAddr, tensionDebounceTime);
      writeTensionDelay = false;
    }
    if (writeLimitDelay == true) {
      writeEEProm(EEpromLDelayAddr, limitDebounceTime);
      writeLimitDelay = false;
    }
    if (writeMax == true) {
      writeEEProm(EEpromMaxValAddr, maxVal);
      writeMax = false;
    }
    if (writeMin == true) {
      writeEEProm(EEpromMinValAddr, minVal);
      writeMin = false;
    }

    msCounter = 0;
  }
  
  delay(1);        // delay in between loops for stability
  msCounter += 1;
}

void writeEEProm(int addr, int val) {
     // Read the value, see if it has changed, and write only if it has.
      byte b1 = EEPROM.read(addr);
      byte b2 = EEPROM.read(addr+1);
      unsigned int v = (unsigned int) b1 * 256 + (unsigned int) b2;
      if ( (int)v != val ) {
        b1 = (byte) (val >> 8);
        b2 = (byte) (val & 0xFF);
        
        Serial.print(F("Writing the following values to EEPROM: "));
        Serial.print( b1 );
        Serial.print( ", ");
        Serial.println( b2 );
        
        EEPROM.write(addr,   b1);
        EEPROM.write(addr+1, b2);
      }
 }

void checkButtonPress(int sensorValue) { 
  // First check the low tension button
  if (digitalRead(loSetButton) == LOW) {
    buttonPressTime = millis();
    while ( digitalRead(loSetButton) == LOW ) {};
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
    while ( digitalRead(hiSetButton) == LOW ) {};
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
  for (int i = 0 ; i < flashCount ; i++ ) {
    digitalWrite(hiTensionLEDpin, HIGH);
    digitalWrite(loTensionLEDpin, HIGH);
    delay(flashDuration);
    digitalWrite(hiTensionLEDpin, LOW);
    digitalWrite(loTensionLEDpin, LOW);
  }
}

void software_Reboot() {
  // since the watchdog timer is enabled, all we do is get stuck and wait
  while(1){}
}

