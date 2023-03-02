/*
  tension_and_limit
  Intelligent winch tension and limit switch processor.
  
  This version modified for the Smart Tension 3.0 board
  
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
    high threshold
    low threshold
    
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
 
#include <Wire.h>
#include <EEPROM.h>
#include "ApplicationMonitor.h"
#include <Adafruit_ADS1015.h>
#include "Adafruit_LEDBackpack.h"
#include "Adafruit_GFX.h"
#include <math.h>
#include "RunningAverage.h"

Watchdog::CApplicationMonitor ApplicationMonitor;
Adafruit_ADS1015 ads;     /* Use this for the 12-bit version */
Adafruit_24bargraph bar = Adafruit_24bargraph();

#define SWVERSION "1.0"

// pin definitions
const int analogIn = A0;
const int noLowerOutPin = 10;  // logic low is activated
const int noRaiseOutPin = 9;   // logic low is activated
const int noLowerDisablePin = 3;  // configured with internal pullup resistor - switch to ground to activate
const int noRaiseDisablePin = 2;  // configured with internal pullup resistor - switch to ground to activate
const int limitInHi = 7;    // configured with internal pullup resistor - switch to ground to activate MADE UP UNUSED INPUTS SO SOFTWARE WILL COMPILE
const int limitInLo = 8;    // configured with internal pullup resistor - switch to ground to activate MADE UP UNUSED INPUTS SO SOFTWARE WILL COMPILE
const int hiTensionLEDpin = 11;  // logic low is activated
const int loTensionLEDpin = 12;  // logic low is activated
const int loSetButton = 5;  // configured with internal pullup resistor - switch to ground to activate
const int hiSetButton = 4;  // configured with internal pullup resistor - switch to ground to activate


// These defaults are superceded by values in EEPROM if they exist
int minVal = 159;    // min and max possible values
int maxVal = 1550;
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

unsigned long msStartTime = 0;         // ms counter for loop timing
unsigned long LEDStartTime = 0;
unsigned long LEDonTime = 600000;      // in ms

unsigned long longPressTime = 3000;

// These defaults are superceded by values in EEPROM if they exist
unsigned long tensionDebounceTime = 500;  // ms delay for hi/lo tension
unsigned long limitDebounceTime = 250;      // ms delay for limit switch
#define AVGLEN 25  // how many sensor readings to average
RunningAverage sensorValues(AVGLEN);

unsigned long tensionTripTime = 0;
unsigned long limitTripTime = 0;
unsigned long buttonPressTime = 0;

int bar_array[24];  // to hole the colors of the bar graph display

String cmdBuf = "";



// the setup routine runs once when you press reset:
void setup() {
  // initialize serial communication at 9600 bits per second:
  Serial.begin(9600);

  // initialize the adc chip
  ads.setGain(GAIN_TWOTHIRDS);  // 2/3x gain +/- 6.144V  1 bit = 3mV      0.1875mV (default)  
  ads.begin();
  
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
  Serial.print("Software version "); Serial.println(SWVERSION);
  Serial.println("");
  
  bar.begin(0x70);  // pass in the address for the LED bar
  play_with_lights();  // pretty lights
  LEDStartTime = millis();
  
  ApplicationMonitor.Dump(Serial);
  ApplicationMonitor.EnableWatchdog(Watchdog::CApplicationMonitor::Timeout_2s);
  Serial.println("");

  unsigned int eeHi = readEEProm(EEpromHiThreshAddr);
  unsigned int eeLo = readEEProm(EEpromLoThreshAddr);
  
//  Serial.print(F("Threshold values from EEPROM for hi and low read as: "));
//  Serial.print( eeHi );
//  Serial.print(F(", "));
//  Serial.println( eeLo );
  
  if (eeHi != 65535) {
    hiThresh = (int) eeHi;
  }
  if (eeLo != 65535) {
    loThresh = (int) eeLo;
  }
  Serial.print(F("Threshold values read from EEPROM (or default) for hi and low are currently set to: "));
  Serial.print( hiThresh );
  Serial.print(F(", "));
  Serial.println( loThresh );
  
  Serial.println("");

  unsigned int td = readEEProm(EEpromTDelayAddr);
  unsigned int ld = readEEProm(EEpromLDelayAddr);
  
//  Serial.print(F("Tension and limit delay times from EEPROM read as: "));
//  Serial.print( td );
//  Serial.print( ", ");
//  Serial.println( ld );
  
  if (td != 65535) {
    tensionDebounceTime = (unsigned long) td;
  }
  if (ld != 65535) {
    limitDebounceTime = (unsigned long) ld;
  }
  Serial.print(F("Tension and limit delay times read from EEPROM (or default) are currently set to: "));
  Serial.print( tensionDebounceTime );
  Serial.print(F(" ms, "));
  Serial.print( limitDebounceTime );
  Serial.println(F(" ms"));
  Serial.println("");

  
  unsigned int eeMax = readEEProm(EEpromMaxValAddr);
  unsigned int eeMin = readEEProm(EEpromMinValAddr);
  
//  Serial.print(F("Max values from EEPROM for max and min read as: "));
//  Serial.print( eeMax );
//  Serial.print(F(", "));
//  Serial.print( eeMin );
//  Serial.println( "");
  
  if (eeMax != 65535) {
    maxVal = (int) eeMax;
  }
  if (eeMin != 65535) {
    minVal = (int) eeMin;
  }
  Serial.print(F("Max values for hi and low read from EEPROM (or default) are currently set to: "));
  Serial.print( maxVal );
  Serial.print(F(", "));
  Serial.println( minVal );
  
  cmdBuf.reserve(30);  // reserve some space for the command buffer to avoid memory fragmentation  
  sensorValues.clear();
}


// the loop routine runs over and over again forever:
void loop() {  
  ApplicationMonitor.IAmAlive();  // ping the watchdog timer
  ApplicationMonitor.SetData(1);  // any 32 bit value, anywhere in the code
  
  // read the inputs
  sensorValues.addValue(ads.readADC_SingleEnded(0));
  int sensorValue = sensorValues.getAverage();
  int limitHi = digitalRead(limitInHi);
  int limitLo = digitalRead(limitInLo);
  int noLowerDisable = digitalRead(noLowerDisablePin);
  int noRaiseDisable = digitalRead(noRaiseDisablePin);
  
  
  // Check inputs, using turn-on delays if tripped
  if (sensorValue > hiThresh) {  // This indicates high tension
    digitalWrite(hiTensionLEDpin, LOW);
    if (tensionTripTime == 0) {
      tensionTripTime = millis();
    }
    // second part of this says if we go too high, set the output without delay
    if ( ((millis() >= tensionTripTime + tensionDebounceTime) || (sensorValue > maxVal * 0.95))
          && noRaiseDisable == HIGH) {
      digitalWrite(noRaiseOutPin, LOW);
    }
  } else { digitalWrite(hiTensionLEDpin, HIGH); }
  
  if (sensorValue < loThresh) {  // This indicates low tension
    digitalWrite(loTensionLEDpin, LOW);
    if (tensionTripTime == 0) {
      tensionTripTime = millis();
    }
    if ( ((millis() >= tensionTripTime + tensionDebounceTime) || (sensorValue < minVal + maxVal * 0.05))
        && noLowerDisable == HIGH) {
      digitalWrite(noLowerOutPin, LOW);
    }
  } else { digitalWrite(loTensionLEDpin, HIGH); }
  
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
  if ( noLowerDisable==LOW || (sensorValue >= loThresh && limitLo==HIGH) ) {
    digitalWrite(noLowerOutPin, HIGH);
  }
  
  // Clear noRaise if conditions are met
  if ( noRaiseDisable==LOW || (sensorValue <= hiThresh && limitHi==HIGH) ) {
    digitalWrite(noRaiseOutPin, HIGH);
  }

  // Only when there are no faults do we reset the delays
  if (sensorValue >= loThresh && sensorValue <= hiThresh
      && limitHi==HIGH && limitLo==HIGH) {  // All clear
    tensionTripTime = 0;
    limitTripTime = 0;
  } else {
    LEDStartTime = millis();  // if there has been a fault of any kind turn on the LED bar
  }

  set_bar(sensorValue);  // set the LED bar showing current tension

  // look for a command on the serial port  
  readCommand();
  
  // check the hi and lo set buttons for new threshold values
  // If the low threshold is set to a value higher than the high threshold or
  // vice-versa the system will fail. (It will never reset the delays.)  This might
  // be fixable, but the condition doesn't make sense.
  checkButtonPress(sensorValue);

  //
  // once per second  
  //  output serial data
  //  write thresholds to eeprom if necessary
  //
  if ( (millis() - msStartTime) >= 1000) {
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

    msStartTime = millis();
  }
  
  delay(1);        // delay in between loops for stability
}

