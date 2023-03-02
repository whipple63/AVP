
unsigned int readEEProm(int addr) {
  byte b1 = EEPROM.read(addr);
  byte b2 = EEPROM.read(addr+1);
  return (unsigned int) b1 * 256 + (unsigned int) b2;
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

