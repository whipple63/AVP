/*
Liquid flow rate sensor adapted from -DIYhacking.com Arvind Sanjeev

Measure liquid/water flow rate. 
Connect Vcc and Gnd of sensor to arduino, and the signal line to arduino digital pin 2.
 */
#include <EEPROM.h>

#define SWVERSION "1.1"

const int EEpromCalFactorAddr = 101;  // two byte long values to store

byte sensorPin       = 2;
byte waterValvePin   = 13;

// The hall-effect flow sensor outputs approximately XX pulses per second per
// litre/minute of flow.
//double calibrationFactor = 6.15;

// The vortex flow sensor outputs approximately XX pulses per second per
// litre/minute of flow.
double calibrationFactor = 4.3;

volatile byte pulseCount;  

double flowRate;   // each in l/min
double totalFlow;
double prevTotal;

unsigned long oldTime;

String cmdBuf = "";

void setup()
{
  Serial.begin(9600);       // Initialize a serial connection for reporting values to the host

  pinMode(sensorPin, INPUT);
  digitalWrite(sensorPin, HIGH);

  pinMode(waterValvePin, OUTPUT);
  digitalWrite(waterValvePin, LOW);

  Serial.println("");
  Serial.println(F("Flow meter and water valve processor."));
  Serial.print("Software version "); Serial.println(SWVERSION);
  Serial.println("");
  

  unsigned int eeCal = readEEProm(EEpromCalFactorAddr);
  if (eeCal != 65535) { // if not uninitialized
    calibrationFactor = (double) eeCal / 100.0;    // Stored in EEPROM as 100*value
  }
  Serial.print(F("Calibration factor value read from EEPROM (or default) set to: "));
  Serial.println( calibrationFactor );

  
  pulseCount        = 0;
  flowRate          = 0.0;
  totalFlow         = 0.0;
  prevTotal         = 0.0;
  oldTime           = 0;

  // The flow sensor is connected to pin 2 which uses interrupt 0.
  // Configured to trigger on a FALLING state change (transition from HIGH
  // state to LOW state)
  attachInterrupt(digitalPinToInterrupt(sensorPin), pulseCounter, FALLING);
}

/**
 * Main program loop
 */
void loop()
{
  unsigned long loop_time = millis() - oldTime;   // this should work for millis rollover events as well
    
  if ( loop_time >= 1000 )    // Only process counters once per second
  { 
    // Because this loop may not complete in exactly 1 second intervals we calculate
    // the number of milliseconds that have passed since the last execution and use
    // that to scale the output. We also apply the calibrationFactor to scale the output
    // based on the number of pulses per second per units of measure (litres/minute in
    // this case) coming from the sensor.
    flowRate = ((1000.0 / loop_time) * pulseCount) / calibrationFactor;   // l/min
    totalFlow += flowRate * (loop_time * (1.0/60000.0));    // liters
    
    pulseCount = 0;     // Reset the pulse counter so we can start incrementing again
    oldTime = millis(); // Note the time this processing pass was executed
    
    unsigned int frac;
    Serial.print(int(flowRate));        // Print the integer part of the variable
    Serial.print(".");                  // Print the decimal point
    frac = (flowRate - int(flowRate)) * 10;   // Determine the fractional part. The 10 multiplier gives us 1 decimal place.
    Serial.print(frac, DEC) ;           // Print the fractional part of the variable

    Serial.print("   ");

    Serial.print(int(totalFlow));       // Print the integer part of the variable
    Serial.print(".");                  // Print the decimal point
    frac = (totalFlow - int(totalFlow)) * 1000;   // Determine the fractional part. The 1000 multiplier gives us 3 decimal place.
    Serial.print(frac, DEC) ;           // Print the fractional part of the variable
    
    Serial.println();   
  }

  // look for a command on the serial port  
  readCommand();
  
  delay(1);
}

/*
Insterrupt Service Routine
 */
void pulseCounter()
{
  pulseCount++; // Increment the pulse counter
}
