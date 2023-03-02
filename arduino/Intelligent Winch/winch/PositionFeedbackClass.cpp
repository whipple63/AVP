// 
// 
// 

#include "PositionFeedbackClass.h"
#include "winch.h"

PositionFeedbackClass::PositionFeedbackClass() {
  m_fb_period = float(EepromAccess.readEEPromLong(EepromAccess.FB_PERIOD));  // do not divide by 1000 - keep in ms.

  setFeedbackMaxSpeed();

  m_movingDownWithFeedback = false;
  m_movingDownWithFeedback = false;
  m_recentPosFeedback = false;

  m_posFbTime = 0;
  m_fb_delta = 0;
  m_fbPos = 0;
}

void PositionFeedbackClass::setFeedbackPeriod(float p_seconds) {
    m_fb_period = p_seconds * 1000.0;
    EepromAccess.writeEEPromLong(EepromAccess.FB_PERIOD, long(m_fb_period));
}

void PositionFeedbackClass::setFeedbackMaxSpeed() {
  m_fb_max_speed = 100 * (60000.0 / ((1 / FB_DIST)*(float)m_fb_period)) / Motor.getRPM();
  if (m_fb_max_speed > 100) { m_fb_max_speed = 100; }  // limit to 100 percent  
}

void PositionFeedbackClass::setFeedbackDelta(int speed_percent) {
  m_fb_delta = float(FB_DIST * 60000.0) / (((float)speed_percent / 100)*Motor.getRPM());  // ms per FB_DIST revolutions
}


bool PositionFeedbackClass::haveRecentPositionFeedback() {
  if (TimeSince(m_posFbTime) >= (long)(2.5*m_fb_period)) {
    m_recentPosFeedback = false;
  }
  return m_recentPosFeedback;
}


// check the Ethernet port for an incoming position.
// positions will be processed upon receipt of a newline character
void PositionFeedbackClass::readPos() {
  char c = ' ';  // init to anything other than newline

  int i = 0;
  while (Ethernet1.getPosClient().available()) {
    c = Ethernet1.getPosClient().read();
    posBuf[i++] = c;
  }

  if (c == '\n') {  // process the line
    sd.print(sd.getFbFileName(), NULL, posBuf, true);
//    Serial.print("Processing position: "); Serial.print(posBuf);
    if (isValidNumber(posBuf)) {
      // Input a floating point number as a position
      m_fbPos = atof(posBuf);
      m_recentPosFeedback = true;
      m_posFbTime = (unsigned long)millis();
//      Serial.print("Pos: "); Serial.print(m_fbPos);

      // 
      // check for stop conditions
      //
      if (m_movingUpWithFeedback == true) {
        if (double(m_fbPos) <= m_moveTarget) { MCtrl.stopMoving(); }

        // Check to see that the feedback indicates moving up
        // by differencing observations at least FB_DELTA apart.
        if ((m_posFbTime - m_oldPosFbTime) > (unsigned long)(2 * m_fb_delta)) { // consider this the first observation
          m_oldPosFb = m_fbPos;
          m_oldPosFbTime = m_posFbTime;
        }
        else {
          if ((m_posFbTime - m_oldPosFbTime) > (unsigned long)m_fb_delta) {  // time to compare
            if (m_fbPos >= m_oldPosFb) {
              MCtrl.stopMoving();
              sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to position feedback value not decreasing during up move."), true);
            }
            m_oldPosFb = m_fbPos;
            m_oldPosFbTime = m_posFbTime;
          }
        }
      }

      if (m_movingDownWithFeedback == true) {
        if (double(m_fbPos) >= m_moveTarget) { MCtrl.stopMoving(); }

        // Check to see that the feedback indicates moving down
        // by differencing observations at least FB_DELTA apart.
        if ((m_posFbTime - m_oldPosFbTime) > (unsigned long)(2 * m_fb_delta)) { // consider this the first observation
          m_oldPosFb = m_fbPos;
          m_oldPosFbTime = m_posFbTime;
        }
        else {
          if ((m_posFbTime - m_oldPosFbTime) > (unsigned long)m_fb_delta) {  // time to compare
            if (m_fbPos <= m_oldPosFb) {
              MCtrl.stopMoving();
              sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to position feedback value not increasing during down move."), true);
            }
            m_oldPosFb = m_fbPos;
            m_oldPosFbTime = m_posFbTime;
          }
        }
      }

//      sd.print(sd.getSerFileName(), &Serial, F("Latest position: "), true);
//      sd.println(sd.getSerFileName(), &Serial, m_fbPos, 6u, false);
    }

    memset(posBuf, 0, POS_BUF_LEN);  // clear the buffer after processing
  }

}
