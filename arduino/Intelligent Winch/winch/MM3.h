// MM3.h

#ifndef _MM3_h
#define _MM3_h

#if defined(ARDUINO) && ARDUINO >= 100
	#include "arduino.h"
#else
	#include "WProgram.h"
#endif


// Some constants for the MM3 function register
#define POSPWRUP   ((unsigned int) 0x0001)
#define SATPROT    ((unsigned int) 0x0010)
#define SAVEPOS    ((unsigned int) 0x0020)
#define VELLIMIT   ((unsigned int) 0x0040)
#define ACTIVESTOP ((unsigned int) 0x0080)
#define ENABLEDB   ((unsigned int) 0x0800)
#define VIRTLIMIT  ((unsigned int) 0x2000)
#define DISABLEPID ((unsigned int) 0x4000)
#define FN_REG_STOPPED (String(POSPWRUP | SAVEPOS | VELLIMIT | ACTIVESTOP | ENABLEDB | VIRTLIMIT | DISABLEPID))
#define FN_REG_MOVING  (String(POSPWRUP | SAVEPOS | VELLIMIT | ACTIVESTOP | ENABLEDB | VIRTLIMIT ))


// Status register bits
#define NO_RAISE 0x01
#define NO_LOWER 0x02
#define BRAKE 0x04
#define OVER_CURRENT 0x80
#define OVER_TEMP 0x400

// Speed is measured in counts per 5ms interval
#define SPEED_RANGE (int( float(Motor.getCPR()) * float(Motor.getRPM()) / 12000.0 + 0.5 ))


class MM3Class {

  // values from motor controller
  double m_currPos;           // in revolutions
  int m_currSpd;
  int mSpeedPct;
  int m_currAmps;
  unsigned int m_currStatus;  // status register
  long m_vnlim, m_vplim;      // virtual limits
  
  float m_ampsLimit;
  bool m_stopped;

  long readRegister(String r);
  void writeMM3(String cmd);

public:
  const static float MAX_AMPS;

  void init();

  void readController();

  unsigned int getPTerm() { return readRegister("04"); }
  unsigned int getITerm() { return readRegister("05"); }
  unsigned int getDTerm() { return readRegister("06"); }
  unsigned int getPIDScalar() { return readRegister("08"); }
  unsigned int getVFF() { return readRegister("02"); }
  void setPTerm(unsigned int n);
  void setITerm(unsigned int n);
  void setDTerm(unsigned int n);
  void setPIDScalar(unsigned int n);
  void setVFF(unsigned int n);
  void storeTuning();

  double getCurrPos() { return m_currPos; }
  void setPos(double pos);
  int getCurrSpd() { return m_currSpd; }
  int getCurrAmps() { return m_currAmps; }
  int getTargetSpeed();

  bool isStopped() { return m_stopped; }

  bool isNoRaise()     { return m_currStatus & NO_RAISE; }
  bool isNoLower()     { return m_currStatus & NO_LOWER; }
  bool isBrake()       { return m_currStatus & BRAKE;    }
  bool isOverCurrent() { return m_currStatus & OVER_CURRENT; }
  bool isOverTemp()    { return m_currStatus & OVER_TEMP; }

  long getVirtualNegativeLimit() { return m_vnlim; }
  long getVirtualPositiveLimit() { return m_vplim; }
  void setVirtualNegativeLimit(long v);
  void setVirtualPositiveLimit(long v);

  void moveSetup(int speedPct);     // prepare for a move
  void moveAtSpeed(int spd);        // speed in percent of max rpm
  void moveToPos(double pos);       // absolute position in revolutions
  void moveRelative(double revs);   // relative n revolutions
  void stopMoving();

  float getAmpsLimit() { return m_ampsLimit; }
  void setAmpsLimit(float a);
};

#endif

