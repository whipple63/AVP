// broker_util.h

#ifndef _BROKER_UTIL_h
#define _BROKER_UTIL_h

#define S1DEBUG 1

#define MAIN_BUFFER_SIZE 1500

#include <Arduino.h> 
#include "broker_data.h"



uint16_t	printResultStr(char *stat_buff, uint16_t  d_idx);
uint16_t	addMsgTime(char *stat_buff, uint16_t  d_idx, const char * tz, bool has_id);
uint16_t	addMsgId(char *stat_buff, uint16_t  d_idx, const int16_t json_id);

void		printFreeRam(const char * msg);
uint32_t	freeRam();


uint8_t checkSubscriptions(bool datamap[], BrokerData *broker_objs[], const uint8_t broker_obj_count);

#endif

