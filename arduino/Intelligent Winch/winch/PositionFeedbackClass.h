// PositionFeedbackClass.h

#ifndef _POSITIONFEEDBACKCLASS_h
#define _POSITIONFEEDBACKCLASS_h

#if defined(ARDUINO) && ARDUINO >= 100
	#include "arduino.h"
#else
	#include "WProgram.h"
#endif


// Distance the winch can turn between feedback error checks.  This should  be ste to both a
// long enough travel distance to measure payload movement in the correct direction in waves
// etc, and a short enough distance to keep the cable from coming off in case the payload
// has stopped moving.
#define FB_DIST 0.25

#define POS_BUF_LEN 32

class PositionFeedbackClass {

  double m_moveTarget;

  int m_fb_max_speed;
  int m_fb_delta;
  long m_fb_period;   // stored in ms
  float m_fbPos;
  bool m_recentPosFeedback, m_movingUpWithFeedback, m_movingDownWithFeedback;
  unsigned long m_posFbTime;

  float m_oldPosFb = 0.0;
  unsigned long m_oldPosFbTime = 0;

  // create a string variable for temporary use (will allocate space in setup)
  char posBuf[POS_BUF_LEN];

public:
  PositionFeedbackClass();  // constructor

  void setMoveTarget(double t) { m_moveTarget = t; }
  double getMoveTarget() { return m_moveTarget; }

  float getFeedbackPeriod() { return float(m_fb_period) / 1000.0; }
  void setFeedbackPeriod(float p_seconds);

  int getFeedbackMaxSpeed() { return m_fb_max_speed; }
  void setFeedbackMaxSpeed();

  void setFeedbackDelta(int speed_percent);

  float getFeedbackPosition() { return m_fbPos; }

  bool haveRecentPositionFeedback();
  bool movingUpWithFeedback() { return m_movingDownWithFeedback; }
  void setMovingUpWithFeedback(bool b) { m_movingUpWithFeedback = b; }
  bool movingDownWithFeedback() { return m_movingDownWithFeedback; }
  void setMovingDownWithFeedback(bool b) { m_movingDownWithFeedback = b; }

  void readPos();
};

#endif

