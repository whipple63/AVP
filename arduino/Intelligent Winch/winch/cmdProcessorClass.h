// cmdProcessorClass.h

#ifndef _CMDPROCESSORCLASS_h
#define _CMDPROCESSORCLASS_h

#if defined(ARDUINO) && ARDUINO >= 100
	#include "arduino.h"
#else
	#include "WProgram.h"
#endif

#define CMD_BUF_LEN 128

class cmdProcessorClass {
  char cmdBuf[CMD_BUF_LEN];
  double m_target;

public:
  cmdProcessorClass();  // constructor

  void readCommand();
  int parseMove();
};

#endif

