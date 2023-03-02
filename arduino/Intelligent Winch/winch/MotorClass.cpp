// 
// keeps properties associated with the motor and encoder
// 

#include "MotorClass.h"

MotorClass::MotorClass() {
  m_motor_run_time = 0;
  m_idle_time = 0L;
  m_motor_cpr = EepromAccess.readEEPromLong(EepromAccess.MOTOR_CPR);
  m_motor_rpm = float(EepromAccess.readEEPromLong(EepromAccess.MOTOR_RPM)) / 1000.0;
  m_motor_time = (unsigned long)EepromAccess.readEEPromLong(EepromAccess.MOTOR_TIME);

  // Motor controller is constrained by a signed 4-byte integer for pulse counting (31 bits)
  m_maxRevolutions = double(EepromAccess.readEEPromLong(EepromAccess.MAX_REVOLUTIONS)) / 1000.0;
  if (m_maxRevolutions > ABSOLUTE_MAX_REVOLUTIONS) { m_maxRevolutions = ABSOLUTE_MAX_REVOLUTIONS; }  // can happen when uninitialized
}

void MotorClass::setMotorTimeDays(float mdays) {
  m_motor_time = mdays *60.0*60.0*24.0;
  EepromAccess.writeEEPromLong(EepromAccess.MOTOR_TIME, m_motor_time);
}

void MotorClass::incrMotorTime() {
  m_motor_time += (millis() - m_motor_run_time) / 1000;   // add to motor time in seconds
}

void MotorClass::setCPR(unsigned long n) { 
  m_motor_cpr = n; 
  EepromAccess.writeEEPromLong(EepromAccess.MOTOR_CPR, m_motor_cpr);
}

void MotorClass::setRPM(float f) {
  m_motor_rpm = f;
  EepromAccess.writeEEPromLong(EepromAccess.MOTOR_RPM, long(m_motor_rpm * 1000));  // Store as a long multiplied by 1000
}

void MotorClass::setMaxRevolutions(double m) {
  if (m > ABSOLUTE_MAX_REVOLUTIONS) { m = ABSOLUTE_MAX_REVOLUTIONS; }  // can't go over ABSOLUTE_MAX_REVOLUTIONS
  m_maxRevolutions = m;
  EepromAccess.writeEEPromLong(EepromAccess.MAX_REVOLUTIONS, long(m_maxRevolutions * 1000));  // Store as a long multiplied by 1000

}