// sdLogger.h

#ifndef _SDLOGGER_h
#define _SDLOGGER_h

#if defined(ARDUINO) && ARDUINO >= 100
	#include "arduino.h"
#else
	#include "WProgram.h"
#endif

#include <SPI.h>
#include <SdFat.h>

#define CMD_FOLDER "Command"
#define OUT_FOLDER "Output"
#define FB_FOLDER "Feedback"
#define SER_FOLDER "Serial"

// Log file base names.  Must be six characters or less.
#define CMD_FILES "cmd_"
#define OUT_FILES "out_"
#define FB_FILES "fb_"
#define SER_FILES "ser_"

// File name length including path
#define FN_LEN 26
#define UPTIME_SIZE 16

class sdLogger {
  const uint8_t SD_CHIP_SELECT = 4;
  const int8_t DISABLE_CHIP_SELECT = 10;

  const uint8_t FS_THRESH = 10; // free space threshold in megabytes

  unsigned long m_lastUptime = 0;
  unsigned int m_uptimeRollovers = 0;
  char m_upTimeString[UPTIME_SIZE];  // a string representing the system uptime

  char m_cmdFileName[FN_LEN];
  char m_outFileName[FN_LEN];
  char m_fbFileName[FN_LEN];
  char m_serFileName[FN_LEN];
  uint8_t CMD_SIZE;
  uint8_t OUT_SIZE;
  uint8_t FB_SIZE;
  uint8_t SER_SIZE;

  unsigned long m_incrementTime = 0;

  SdFile m_logFile; // a place to hold file info while it is open

  SdFat m_sd;
  bool m_sdInitialized = false;

  void check_directory_structure();
  void init_file_names();
  void find_first_filename(uint8_t fnsize, char *fn);
  void find_next_filename(uint8_t fnsize, char *fn);
  void remove_next_files(uint8_t fnsize, char *fn, bool move_ahead);
  void incr_fn(uint8_t fnsize, char *fn);               // increment the filename
  float getFreeSpaceMB();

public:
  sdLogger();

  void init();
  void increment_file_names();
  void incrementIfIntervalHasBeen(float d); //d=days

  char *getUpTimeString();

  char *getCmdFileName() { return m_cmdFileName; }
  char *getOutFileName() { return m_outFileName; }
  char *getFbFileName() { return m_fbFileName; }
  char *getSerFileName() { return m_serFileName; }


  //
  // The print functions take as arguments one of the log files as an enum value
  // and a pointer to an object that inherits from abstract class Print.  This can
  // be one of ther Serial ports or an Ethernet client etc.  Either argument can also be NULL
  // which will log only to the other.
  //
  // For efficiency, calls should be as complete as possible since the log files will
  // be opened, written to, and closed each time.  For that reason, single char print
  // has been removed.  (Easily added if it becomes necessary)
  //

  size_t print(char *fn, Print* p, const char *str, bool prependUptime = false);
  size_t print(char *fn, Print* p, const __FlashStringHelper *str, bool prependUptime = false);
  size_t print(char *fn, Print* p, const String& str, bool prependUptime = false);
  size_t print(char *fn, Print* p, double val, uint8_t prec = 2, bool prependUptime = false);
  size_t print(char *fn, Print* p, float val, uint8_t prec = 2, bool prependUptime = false);
  size_t print(char *fn, Print* p, int val, int base = DEC, bool prependUptime = false);
  size_t print(char *fn, Print* p, unsigned int val, int base = DEC, bool prependUptime = false);
  size_t print(char *fn, Print* p, long val, int base = DEC, bool prependUptime = false);
  size_t print(char *fn, Print* p, unsigned long val, int base = DEC, bool prependUptime = false);

  size_t println(char *fn, Print* p, const char *str, bool prependUptime = false);
  size_t println(char *fn, Print* p, const __FlashStringHelper *str, bool prependUptime = false);
  size_t println(char *fn, Print* p, const String& str, bool prependUptime = false);
  size_t println(char *fn, Print* p, double val, uint8_t prec = 2, bool prependUptime = false);
  size_t println(char *fn, Print* p, float val, uint8_t prec = 2, bool prependUptime = false);
  size_t println(char *fn, Print* p, int val, int base = DEC, bool prependUptime = false);
  size_t println(char *fn, Print* p, unsigned int val, int base = DEC, bool prependUptime = false);
  size_t println(char *fn, Print* p, long val, int base = DEC, bool prependUptime = false);
  size_t println(char *fn, Print* p, unsigned long val, int base = DEC, bool prependUptime = false);

};

#endif

