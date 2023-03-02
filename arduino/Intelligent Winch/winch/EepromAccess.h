// EepromAccess.h

#ifndef _EEPROMACCESS_h
#define _EEPROMACCESS_h

#if defined(ARDUINO) && ARDUINO >= 100
#include "arduino.h"
#else
#include "WProgram.h"
#endif

#include <EEPROM.h>

class EepromAccessClass
{
  const static int EEPROM_BASE = 100;

public:

  // EEProm memory addresses in use
  const static int IP              = EEPROM_BASE;
  const static int DNS             = EEPROM_BASE + 4;
  const static int GATE            = EEPROM_BASE + 8;
  const static int SUB             = EEPROM_BASE + 12;
  const static int PORT_BASE       = EEPROM_BASE + 16;
  const static int MOTOR_CPR       = EEPROM_BASE + 20;
  const static int MOTOR_RPM       = EEPROM_BASE + 24;
  const static int MAX_REVOLUTIONS = EEPROM_BASE + 28;
  const static int SAVED_POSITION  = EEPROM_BASE + 32;
  const static int MOTOR_TIME      = EEPROM_BASE + 36;
  const static int FB_PERIOD       = EEPROM_BASE + 40;

  unsigned int readEEPromInt(int addr);
  void writeEEPromInt(int addr, int val);
  unsigned long readEEPromLong(int addr);
  void writeEEPromLong(int addr, long val);
};

#endif

