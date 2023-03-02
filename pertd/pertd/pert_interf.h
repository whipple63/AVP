#define PERTD_VERSION 2007030500
#define PERT_DISPLAY_WIDTH 20
void wrtln(int row, char *p);
void display_init(char *device_name);
void display_close();
void backlight(int on);
extern int char_delay;
