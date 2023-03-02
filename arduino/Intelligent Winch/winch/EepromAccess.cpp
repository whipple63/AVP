// 
// 
// 

#include "EepromAccess.h"
#include "winch.h"

unsigned int EepromAccessClass::readEEPromInt(int addr) {
  byte b1 = EEPROM.read(addr);
  byte b2 = EEPROM.read(addr + 1);
  return (unsigned int)b1 * 256 + (unsigned int)b2;
}

void EepromAccessClass::writeEEPromInt(int addr, int val) {
  // Read the value, see if it has changed, and write only if it has.
  byte b1 = EEPROM.read(addr);
  byte b2 = EEPROM.read(addr + 1);
  unsigned int v = (unsigned int)b1 * 256 + (unsigned int)b2;
  if ((int)v != val) {
    b1 = (byte)(val >> 8);
    b2 = (byte)(val & 0xFF);

    sd.print(sd.getSerFileName(), &Serial, F("Writing the following values to EEPROM: "), true);
    sd.println(sd.getSerFileName(), &Serial, String(b1) + ", " + String(b2), false);

    EEPROM.write(addr, b1);
    EEPROM.write(addr + 1, b2);
  }
}

unsigned long EepromAccessClass::readEEPromLong(int addr) {
  byte b[4];
  unsigned long retval = 0;

  for (int i = 0; i<4; i++) {
    b[i] = EEPROM.read(addr + i);
    retval += (unsigned long)b[i] << (24 - i * 8);
  }
  return retval;
}

void EepromAccessClass::writeEEPromLong(int addr, long val) {
  // Read the value, see if it has changed, and write only if it has.
  byte b[4];
  unsigned long v = readEEPromLong(addr);

  //  Serial.print("Storing value: ");
  //  Serial.println(val);
  //  Serial.print("Read from EEProm: ");
  //  Serial.println(v);

  if ((long)v != val) {
    sd.print(sd.getSerFileName(), &Serial, F("Writing the following values to EEPROM: "), true);
    for (int i = 0; i<4; i++) {
      b[i] = (byte)((val >> (24 - i * 8)) & 0xFF);
      sd.print(sd.getSerFileName(), &Serial, String(b[i]) + ", ", false);
      EEPROM.write(addr + i, b[i]);
    }
    sd.println(sd.getSerFileName(), &Serial, "", false);
  }
}

