// 
// Utilities for Arduino based broker. Would like to move most functions from main ino here and make this a class.
// 

#include "broker_util.h"
#include "broker_data.h"


uint16_t printResultStr(char *stat_buff, uint16_t  d_idx) {
	d_idx += sprintf(stat_buff + d_idx, "{\"result\":{");
	return d_idx;
}

uint16_t addMsgTime(char *stat_buff, uint16_t  d_idx,const char * tz,bool hasID) {
	char msgTime[15];
	setSampleTimeStr(msgTime);
	d_idx += sprintf(stat_buff + d_idx, ",\"message_time\":{\"value\":%s,\"units\":\"%s\"}", msgTime, tz);
	if (!hasID) d_idx += sprintf(stat_buff + d_idx, "}}");
	return d_idx;
}

uint16_t addMsgId(char *stat_buff, uint16_t  d_idx, const int16_t json_id) {
	d_idx += sprintf(stat_buff + d_idx, "},\"id\":%u}", json_id);
	return d_idx;
}


uint32_t freeRam() {
#ifdef __AVR__
	//arduino
	extern int __heap_start, *__brkval;
	int v;
	return (uint32_t)&v - (__brkval == 0 ? (uint32_t)&__heap_start : (uint32_t)__brkval);
#elif defined(__arm__)
	// for Teensy 3.0
	uint32_t stackTop;
	uint32_t heapTop;

	// current position of the stack.
	stackTop = (uint32_t)&stackTop;

	// current position of heap.
	void* hTop = malloc(1);
	heapTop = (uint32_t)hTop;
	free(hTop);

	// The difference is (approximately) the free, available ram.
	return stackTop - heapTop;
#else
	return 0;
#endif
}

void printFreeRam(const char * msg) {
	Serial1.print(F("Free RAM ("));Serial1.print(msg);Serial1.print("):");Serial1.println(freeRam());
}


uint8_t checkSubscriptions(bool datamap[], BrokerData *broker_objs[], const uint8_t broker_obj_count) {
	uint8_t subs = 0;
	for (uint8_t obj_no = 0; obj_no < broker_obj_count; obj_no++) {
		if (broker_objs[obj_no]->subscriptionDue()) {
			datamap[obj_no] = true;
			subs++;
		}
		else datamap[obj_no] = false;
	}
	return subs;
}
