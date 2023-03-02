There are two versions of pertd, the original, and an enhanced pertd2 version.

pertd2 has:
- Added SIGUSR1 trapping.  When received, schedules data file re-scan.
- Added pidfile configuration option
- PID is logged to pidfile, enabling "kill -USR1 `cat pidfile`"
- The " - " end/start separator is used only if the input line width
  is > the display width.  I.e., only if scrolling.
- Added refresh_file_name config option
- When the file specified by refresh_file_name is created, pertd will
  schedule a data file re-scan.
- Added PERTD_VERSION #define in pert_interf.h
- Created a constant for the LCD screen width and substituted that
  wherever the width was hardcoded.