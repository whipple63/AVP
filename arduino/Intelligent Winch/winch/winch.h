
#ifndef _WINCH_h
#define _WINCH_h

#if defined(ARDUINO) && ARDUINO >= 100
#include "arduino.h"
#else
#include "WProgram.h"
#endif


//
// Defines
//
#define SWVERSION "1.3"

// up and down buttons
#define UP_BUTTON_PIN 6
#define DOWN_BUTTON_PIN 5
#define NUM_OF_SPEEDS 5			  // num of speeds to increment through after a button press
#define TIME_PER_SPEED 3000		// ms


#define TimeSince(t1) ((long)((unsigned long)millis()-(unsigned long)t1))
#define LOOP_INTERVAL ((unsigned long)1000L) // in ms



//
// Global Classes
//
#include "sdLogger.h"
extern sdLogger sd;

#include "ApplicationMonitor.h"
extern CApplicationMonitor ApplicationMonitor;

#include "EepromAccess.h"
extern EepromAccessClass EepromAccess;

#include "EthernetClass.h"
extern EthernetSupport Ethernet1;

#include "MotorClass.h"
extern MotorClass Motor;

#include "MM3.h"
extern MM3Class MCtrl;

#include "cmdProcessorClass.h"
extern cmdProcessorClass cmdProc;

#include "PositionFeedbackClass.h"
extern PositionFeedbackClass posFB;


//
// Function prototypes
//
void checkIfMoving();
boolean isValidNumber(String str);
void saveState();
void software_Reboot();
int upHours(), upMinutes(), upSeconds();


#endif
