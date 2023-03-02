// 
// Code to control the Solutions Cubed Motion Mind 3 motor controller
// 

#include "MM3.h"
#include "winch.h"

// class level variables
const float MM3Class::MAX_AMPS = 14.0; // amps cannot exceed this value


void MM3Class::init() {
  sd.print(sd.getSerFileName(), &Serial, "MotionMind 3 Firmware Version: ", true);
  sd.println(sd.getSerFileName(), &Serial, (unsigned int) readRegister("17"));

  m_currPos = float(EepromAccess.readEEPromLong(EepromAccess.SAVED_POSITION)) / 1000.0;
  setPos(m_currPos);

  m_ampsLimit = MAX_AMPS;
  m_stopped = true;

  // Set up all of the registers and values in the motor controller
  writeMM3(F("W01 01 1023"));       // velocitylimit
  writeMM3("W01 03 " + FN_REG_STOPPED);      // function register
  writeMM3(F("W01 07 1"));          // address
  writeMM3(F("W01 09 10"));         // timer
  writeMM3(F("W01 10 1152"));       // rcmax
  writeMM3(F("W01 11 576"));        // rcmon
  writeMM3(F("W01 12 15"));         // rcband
//  setVirtualNegativeLimit(m_vnlim);  Done when max revolutions is read and/or set
//  setVirtualPositiveLimit(m_vplim);
  writeMM3(F("W01 25 0"));          // pwmlimit (can't move when zero)
//  writeMM3(F("W01 26 250"));        // deadband 250 is for when encoder is on drum
  writeMM3(F("W01 26 50"));         // deadband
  setAmpsLimit(m_ampsLimit);        // ampslimit (in 20 mA increments)
  writeMM3(F("W01 30 0"));          // function2 register

  readController();  // to init values like status, amps, speed
}


void MM3Class::moveSetup(int speedPct) {
  char s[30];
  int tt;

  mSpeedPct = speedPct;

  setAmpsLimit(m_ampsLimit);
  writeMM3("W01 25 1023");              // set pwm limit to max value
  writeMM3("W01 03 " + FN_REG_MOVING);  // change function register value to enable pid

  tt = map(speedPct, 0, 100, 0, SPEED_RANGE);
  snprintf(s, 30, "W01 01 %d", tt);
  writeMM3(s);                          // set velocity limit

  m_stopped = false;
  Motor.setIdleTime(0L);                // indicate that we are not idle
  Motor.setMotorRunTime(millis());      // save a time stamp for when we started running
}

void MM3Class::setPTerm(unsigned int n) {
  char s[30];
  snprintf(s, 30, "W01 04 %d", n);
  writeMM3(s); 
}

void MM3Class::setITerm(unsigned int n) {
  char s[30];
  snprintf(s, 30, "W01 05 %d", n);
  writeMM3(s);
}

void MM3Class::setDTerm(unsigned int n) {
  char s[30];
  snprintf(s, 30, "W01 06 %d", n);
  writeMM3(s);
}

void MM3Class::setPIDScalar(unsigned int n) {
  char s[30];
  snprintf(s, 30, "W01 08 %d", n);
  writeMM3(s);
}

void MM3Class::setVFF(unsigned int n) {
  char s[30];
  snprintf(s, 30, "W01 02 %d", n);
  writeMM3(s);
}

// until tuning parameters are stored, they are temporary
void MM3Class::storeTuning() {
  writeMM3("S01 04 " + String(getPTerm()     ) );
  writeMM3("S01 05 " + String(getITerm()     ) );
  writeMM3("S01 06 " + String(getDTerm()     ) );
  writeMM3("S01 08 " + String(getPIDScalar() ) );
  writeMM3("S01 02 " + String(getVFF()       ) );
}

void MM3Class::setPos(double pos) {
  char s[30];
  m_currPos = pos;
  snprintf(s, 30, "W01 00 %ld", long(pos * Motor.getCPR()));
  writeMM3(s);  // tell the motor controller that this is the current position
}

void MM3Class::setVirtualNegativeLimit(long v) { 
  char s[30];
  m_vnlim = v;
  snprintf(s, 30, "W01 23 %ld", m_vnlim);
  writeMM3(s);      // vnlimit
}

void MM3Class::setVirtualPositiveLimit(long v) { 
  char s[30];
  m_vplim = v;
  snprintf(s, 30, "W01 24 %ld", m_vplim);
  writeMM3(s);      // vplimit
}

// positive is down and negative is up
void MM3Class::moveAtSpeed(int pct) {
  char s[30];
  mSpeedPct = pct;
  int spd = map(pct, 0, 100, 0, SPEED_RANGE);
  snprintf(s, 30, "V01 %d", spd);
  writeMM3(s);
}

// measured in revolutions
void MM3Class::moveToPos(double pos) {
  char s[30];
  long counts = long(pos * double(Motor.getCPR()) + 0.5);  // +0.5 to round since long() truncates
  snprintf(s, 30, "P01 %ld", counts);
  writeMM3(s);
}

// measured in revolutions
void MM3Class::moveRelative(double revs) {
  char s[30];
  long counts = long(revs * double(Motor.getCPR()) + 0.5);  // +0.5 to round since long() truncates
  snprintf(s, 30, "M01 %ld", counts);
  writeMM3(s);
}

void MM3Class::setAmpsLimit(float a) {
  char s[30];
  m_ampsLimit = a;
  int t = int((a / 0.02) + 0.5);  // since int truncates, adding 0.5 beforehand rounds
  if (t == 0) { t = 1; }          // since 0 disables the amps limit, small numbers get set to 1
  snprintf(s, 30, "W01 28 %d", t);
  writeMM3(s);                    // set amps limit
}


void MM3Class::stopMoving() {
  writeMM3("W01 03 " + FN_REG_STOPPED); // function register 
  writeMM3("W01 01 0");                 // velocitylimit to 0
  writeMM3("W01 25 0");                 // pwmlimit (can't move when zero)
  if(!m_stopped) Motor.incrMotorTime(); // accumulate motor run time in seconds
  Motor.setIdleTime(millis());          // set the idle time to when we last stopped.
  m_stopped = true;
  posFB.setMovingUpWithFeedback(false);         // reset the flag (if it had been set)
  posFB.setMovingDownWithFeedback(false);       // reset the flag (if it had been set)

  sd.print(sd.getSerFileName(), &Serial, F("Total motor run time: "), true);
  sd.print(sd.getSerFileName(), &Serial, Motor.getMotorTimeDays(), 4u, false);
  sd.println(sd.getSerFileName(), &Serial, F(" Days."), false);
}


boolean badRead;  // true if readRegister fails

// The old way that read all registers at one time for some reason
// caused a slight hiccup in the velocity of the motor.  This way 
// works smoothly.
void MM3Class::readController() {
  long l;
  int i;
  unsigned int ui;

  l = (long)readRegister("00");
  // Sanity check that the current position is within the virtual limits
  if ( abs(l) > getVirtualPositiveLimit() ) {
    sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("WARNING - Current position is out of range.  This should never happen."), true);
    sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("WARNING - Resetting current position to previous value."), true);
    sd.println(sd.getSerFileName(), &Serial, F("WARNING - Current position is out of range.  This should never happen."), true);
    sd.println(sd.getSerFileName(), &Serial, F("WARNING - Resetting current position to previous value."), true);
    sd.println(sd.getSerFileName(), &Serial, "", true);
    setPos(m_currPos);
    badRead = true; // don't use
  }
  if (badRead == false) { m_currPos = double(l) / Motor.getCPR(); }

  i = map((int)readRegister("14"), 0, SPEED_RANGE, 0, 100);
  if (badRead == false) { m_currSpd = i; }

  i = (int)readRegister("29");
  if (badRead == false) { m_currAmps = i; }

  ui = (unsigned int)readRegister("16");
  if (badRead == false) { m_currStatus = ui; }
}

int MM3Class::getTargetSpeed() {
  return mSpeedPct;
}


long MM3Class::readRegister(String r) {
  char rcvBuf[256] = "";
  int bytesRead;
  String cmd = "R01 " + r;

  Serial3.println(cmd);
  bytesRead = Serial3.readBytesUntil('\n', rcvBuf, 256);
  if (bytesRead == 0) {
    badRead = true;
    sd.println(sd.getSerFileName(), &Serial, "ERROR Timed out waiting for response from: " + cmd, true);
  }
  else {
    badRead = false;
  }

  // parse the response from this command
//  Serial.print("readRegister returning: "); Serial.println( atol(strchr(rcvBuf, '=')+1) );
  return atol(strchr(rcvBuf, '=')+1);
}


void MM3Class::writeMM3(String cmd) {
  char rcvBuf[16] = "";
  int bytesRead;

  Serial3.println(cmd);
  bytesRead = Serial3.readBytesUntil('\n', rcvBuf, 16);
  String rb = String(rcvBuf);  // create a String out of the receive buffer
  if (bytesRead == 0) {
    sd.println(sd.getSerFileName(), &Serial, "ERROR Timed out waiting for response from: " + cmd, true);
  }
  if (!rb.startsWith("OK")) {
    sd.println(sd.getSerFileName(), &Serial, "ERROR Bad response of: " + rb + " from command: " + cmd, true);
  }
  // debugging output
  sd.println(sd.getSerFileName(), &Serial, "Response of: " + rb + " from command: " + cmd, true);
}



