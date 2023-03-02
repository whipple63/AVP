// MotorClass.h

#ifndef _MOTORCLASS_h
#define _MOTORCLASS_h

#if defined(ARDUINO) && ARDUINO >= 100
	#include "arduino.h"
#else
	#include "WProgram.h"
#endif

#include "EepromAccess.h"
extern EepromAccessClass EepromAccess;

// MM3 Motor controller is constrained by a signed 4-byte integer for pulse counting (31 bits)
#define ABSOLUTE_MAX_REVOLUTIONS ((pow(2, 31) / getCPR()) - 0.1)

class MotorClass {
  unsigned long m_motor_cpr;          // actually 4*counts per rev - the mm3 multiplies counts by 4
  float m_motor_rpm;
  double m_maxRevolutions;
  unsigned long m_idle_time;          // time the motor went idle; zero also flags not to save the state
  unsigned long m_motor_run_time;     // the time when the motor begins running in millis
  unsigned long m_motor_time;         // total run time in seconds

public:
  MotorClass();  // initializer

  unsigned long getCPR() { return m_motor_cpr; }
  void setCPR(unsigned long n);

  float getRPM() { return m_motor_rpm; }
  void setRPM(float f);

  double getMaxRevolutions() { return m_maxRevolutions; }
  void setMaxRevolutions(double m);

  float getMotorTimeDays() { return float(m_motor_time / (60.0*60.0*24.0)); }
  void setMotorTimeDays(float mdays);

  unsigned long getIdleTime() { return m_idle_time; }
  void setIdleTime(unsigned long t) { m_idle_time = t; }

  void setMotorRunTime(unsigned long t) { m_motor_run_time = t; }
  void incrMotorTime();

};


#endif

