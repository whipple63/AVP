// 
// 
// 

#include "sdLogger.h"
#include "winch.h"

sdLogger::sdLogger() {
  strncpy(m_cmdFileName, CMD_FOLDER "/" CMD_FILES "00.txt", FN_LEN);
  strncpy(m_outFileName, OUT_FOLDER "/" OUT_FILES "00.txt", FN_LEN);
  strncpy(m_fbFileName, FB_FOLDER "/" FB_FILES "00.txt", FN_LEN);
  strncpy(m_serFileName, SER_FOLDER "/" SER_FILES "00.txt", FN_LEN);
  CMD_SIZE = strlen(m_cmdFileName) - 6;
  OUT_SIZE = strlen(m_outFileName) - 6;
  FB_SIZE = strlen(m_fbFileName) - 6;
  SER_SIZE = strlen(m_serFileName) - 6;

  memset(m_upTimeString, 0, sizeof(m_upTimeString));

  m_sdInitialized = false;
  m_incrementTime = 0;
}

void sdLogger::check_directory_structure() {
  if (!m_sd.exists(CMD_FOLDER)) {
    m_sd.mkdir(CMD_FOLDER, true);
  }
  if (!m_sd.exists(OUT_FOLDER)) {
    m_sd.mkdir(OUT_FOLDER, true);
  }
  if (!m_sd.exists(FB_FOLDER)) {
    m_sd.mkdir(FB_FOLDER, true);
  }
  if (!m_sd.exists(SER_FOLDER)) {
    m_sd.mkdir(SER_FOLDER, true);
  }
}

void sdLogger::init_file_names() {
  if (sizeof(CMD_FOLDER) + sizeof(CMD_FILES) > FN_LEN-8 || sizeof(CMD_FILES) > 6) { Serial.println("Size of base command file name too long"); }
  if (sizeof(OUT_FOLDER) + sizeof(OUT_FILES) > FN_LEN-8 || sizeof(OUT_FILES) > 6) { Serial.println("Size of base output file name too long"); }
  if (sizeof(FB_FOLDER) + sizeof(FB_FILES)   > FN_LEN-8 || sizeof(FB_FILES)  > 6) { Serial.println("Size of base feedback file name too long"); }
  if (sizeof(SER_FOLDER) + sizeof(SER_FILES) > FN_LEN-8 || sizeof(SER_FILES) > 6) { Serial.println("Size of base serial file name too long"); }

  // find the first numbered log file name if one exists
  find_first_filename(CMD_SIZE, m_cmdFileName);
  find_first_filename(OUT_SIZE, m_outFileName);
  find_first_filename(FB_SIZE, m_fbFileName);
  find_first_filename(SER_SIZE, m_serFileName);

  // find the next numbered file name that does not exist
  find_next_filename(CMD_SIZE, m_cmdFileName);
  find_next_filename(OUT_SIZE, m_outFileName);
  find_next_filename(FB_SIZE, m_fbFileName);
  find_next_filename(SER_SIZE, m_serFileName);
}

// finds the first numbered filename that exists
// leaves the file number at 00 if none exist
void sdLogger::find_first_filename(uint8_t fnsize, char *fn) {
  int count = 0;  // don't go forever if there are no files

  // while the files don't exist increment to find one that does
  while (!m_sd.exists(fn)) {
    incr_fn(fnsize, fn);
    if (++count > 99) break;
  }
}

// finds the next numbered file name that does not exist
// if there are 100 files we reset to 0 and remove two
void sdLogger::find_next_filename(uint8_t fnsize, char *fn) {
  while (m_sd.exists(fn)) {       // if the least significant digit is not a nine, increment it
    if (fn[fnsize + 1] != '9') {
      fn[fnsize + 1]++;
    }
    else if (fn[fnsize] != '9') { // else set the lsd to 0 and increment the next digit
      fn[fnsize + 1] = '0';
      fn[fnsize]++;
    }
    else {
      fn[fnsize] = fn[fnsize + 1] = '0';  // reset to file 00
      remove_next_files(fnsize, fn, false);
    }
  }
}

// remove the next two files that exist
void sdLogger::remove_next_files(uint8_t fnsize, char *fn, bool move_ahead) {
  char lfn[FN_LEN];
  strcpy(lfn, fn);  // make a local copy of the filename to manipulate

  if (move_ahead) find_first_filename(fnsize, lfn); // find the first filename that exists starting with this number

  // remove this file and the next one numerically to insure there is a gap in the numbers
  if (m_sd.exists(lfn)) {
    Serial.print("Removing: "); Serial.println(lfn);
    m_sd.remove(lfn);       // remove the file
  }
  incr_fn(fnsize, lfn);   // increment the local file name
  if (m_sd.exists(lfn)) {
    Serial.print("Removing: "); Serial.println(lfn);
    m_sd.remove(lfn);     // remove the file
  }
}

void sdLogger::incr_fn(uint8_t fnsize, char *fn) {
  if (fn[fnsize + 1] != '9') {
    fn[fnsize + 1]++;
  }
  else if (fn[fnsize] != '9') { // else set the lsd to 0 and increment the next digit
    fn[fnsize + 1] = '0';
    fn[fnsize]++;
  }
  else {
    fn[fnsize] = fn[fnsize + 1] = '0';  // reset to file 00
  }
}


float sdLogger::getFreeSpaceMB() {
  uint32_t volFree = m_sd.vol()->freeClusterCount();
  return 0.000512*volFree*m_sd.vol()->blocksPerCluster();
}


void sdLogger::init() {
  pinMode(DISABLE_CHIP_SELECT, OUTPUT);
  digitalWrite(DISABLE_CHIP_SELECT, HIGH);  // disable ethernet - the ethernet libraries should handle this from now on
  pinMode(SD_CHIP_SELECT, OUTPUT);
  digitalWrite(SD_CHIP_SELECT, HIGH);       // deselect sd card as well 

  Serial.print("Initializing Sd card...");
  if (m_sd.cardBegin(SD_CHIP_SELECT, SPI_FULL_SPEED)) {
    Serial.println("Done");

    Serial.print("Initializing Sd file system code...");
    if (m_sd.fsBegin()) {
      m_sdInitialized = true;
      Serial.println("Done");
    }
    else {
      Serial.println("\nFile System initialization failed.\n");
      m_sdInitialized = false;
    }
  }
  else {
    Serial.println("SD card initialization failed.");
    m_sdInitialized = false;
  }

  if (m_sdInitialized) {
    check_directory_structure();
    init_file_names();

    // if the file exists remove it and the next one to leave a gap
    remove_next_files(CMD_SIZE, m_cmdFileName, false);
    remove_next_files(OUT_SIZE, m_outFileName, false);
    remove_next_files(FB_SIZE, m_fbFileName, false);
    remove_next_files(SER_SIZE, m_serFileName, false);

    float fs = getFreeSpaceMB();
    Serial.print("FreeSpace: "); Serial.print(fs); Serial.println(" MB (MB = 1,000,000 bytes)\n");
    if (fs <= FS_THRESH) {
      remove_next_files(CMD_SIZE, m_cmdFileName, true);
      remove_next_files(OUT_SIZE, m_outFileName, true);
      remove_next_files(FB_SIZE, m_fbFileName, true);
      remove_next_files(SER_SIZE, m_serFileName, true);
    }

  char sbuf[100];
  snprintf(sbuf, 100, "Logging to: %s, %s, %s, and %s", m_cmdFileName, m_outFileName, m_fbFileName, m_serFileName);
  println(m_serFileName, &Serial,sbuf, true);

//    m_sd.ls(LS_DATE | LS_SIZE | LS_R);  // print a directory listing
  }
}

void sdLogger::increment_file_names() {
  if (m_sdInitialized) {

    // if it doesn't exist, we never opened it.
    if (m_sd.exists(m_cmdFileName)) incr_fn(CMD_SIZE, m_cmdFileName);
    if (m_sd.exists(m_outFileName)) incr_fn(OUT_SIZE, m_outFileName);
    if (m_sd.exists(m_fbFileName))  incr_fn(FB_SIZE,  m_fbFileName);
    if (m_sd.exists(m_serFileName)) incr_fn(SER_SIZE, m_serFileName);

    // if the file exists remove it and the next one to leave a gap
    remove_next_files(CMD_SIZE, m_cmdFileName, false);
    remove_next_files(OUT_SIZE, m_outFileName, false);
    remove_next_files(FB_SIZE, m_fbFileName, false);
    remove_next_files(SER_SIZE, m_serFileName, false);

    // if we are low on free space, remove the next two files
    float fs = getFreeSpaceMB();
    if (fs <= FS_THRESH) {
      remove_next_files(CMD_SIZE, m_cmdFileName, true);
      remove_next_files(OUT_SIZE, m_outFileName, true);
      remove_next_files(FB_SIZE, m_fbFileName, true);
      remove_next_files(SER_SIZE, m_serFileName, true);
    }

  }
}


//d=days
void sdLogger::incrementIfIntervalHasBeen(float d) {
  if (TimeSince(m_incrementTime) > long(d*24.0*60.0*60.0*1000.0)) {
    increment_file_names();
    m_incrementTime = millis();

    char sbuf[100];
//char sbuf[200];
//snprintf(sbuf, 200, "m_incrementTime: %ld, TimeSince(m_incrementTime): %ld, long(d*24.0*60.0*60.0*1000.0): %ld", m_incrementTime,
//TimeSince(m_incrementTime), long(d*24.0*60.0*60.0*1000.0));
//Serial.println(sbuf);
    snprintf(sbuf, 100, "Logging to: %s, %s, %s, and %s", m_cmdFileName, m_outFileName, m_fbFileName, m_serFileName);
    println(m_serFileName, &Serial, sbuf, true);
  }
}

char * sdLogger::getUpTimeString() {
  unsigned long m = millis();
  unsigned long maxlong = ~0;   // invert all bits
  int days, hours, minutes, seconds, milliseconds;
  double bigtime;
  
  if (m < m_lastUptime) m_uptimeRollovers++;  // the millis counter must have rolled over since the last time we checked

  bigtime = m_uptimeRollovers * double(maxlong) + m;

  milliseconds = int(fmod(bigtime, 1000.0));
  seconds      = int(fmod((bigtime / 1000.0), 60.0));
  minutes      = int(fmod((bigtime / (1000.0 * 60.0)), 60.0));
  hours        = int(fmod((bigtime / (1000.0 * 60.0 * 60.0)), 24.0));
  days         = int(bigtime / (1000.0 * 60.0 * 60.0 * 24.0));

  snprintf(m_upTimeString, UPTIME_SIZE, "%d %02d:%02d:%02d.%03d", days, hours, minutes, seconds, milliseconds);

  m_lastUptime = m;
  return m_upTimeString;
}


//
// print methods for both printing to an object derived from Print class
// and to a file simultaneously.
//

size_t sdLogger::print(char* fn, Print* p, const char *str, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(str);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(str);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, const char *str, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(str);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(str);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::print(char* fn, Print* p, const __FlashStringHelper *str, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(str);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(str);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, const __FlashStringHelper *str, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(str);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(str);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::print(char* fn, Print* p, const String& str, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(str);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(str);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, const String& str, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(str);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(str);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::print(char *fn, Print* p, double val, uint8_t prec, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(val,prec);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(val,prec);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, double val, uint8_t prec, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(val, prec);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(val, prec);
      m_logFile.close();
    }
  }
  return retval;
}


size_t sdLogger::print(char *fn, Print* p, float val, uint8_t prec, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(val, prec);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(val, prec);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, float val, uint8_t prec, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(val, prec);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(val, prec);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::print(char *fn, Print* p, int val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(val, base);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, int val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(val, base);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::print(char *fn, Print* p, unsigned int val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(val, base);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, unsigned int val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(val, base);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::print(char *fn, Print* p, long val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(val, base);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, long val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(val, base);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::print(char *fn, Print* p, unsigned long val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->print(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.print(val, base);
      m_logFile.close();
    }
  }
  return retval;
}

size_t sdLogger::println(char *fn, Print* p, unsigned long val, int base, bool prependUptime) {
  size_t retval = 0;
  if (p) retval = p->println(val, base);    // Print to the stream
  if (fn && m_sdInitialized) {
    if (m_logFile.open(fn, O_CREAT | O_WRITE | O_APPEND)) {
      if (prependUptime) { m_logFile.print(getUpTimeString()); m_logFile.print(" "); }
      retval = m_logFile.println(val, base);
      m_logFile.close();
    }
  }
  return retval;
}


