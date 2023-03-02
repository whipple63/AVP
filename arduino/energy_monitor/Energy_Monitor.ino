/* Energy Monitor

Reads current values from ADS1015
Channel, function
0, Load current
1, Charge Current
2, Battery Voltage (through divider)
3, Vcc (nominal 5v)

Commuincates via JSON-RPC

Data Values:
Voltage
Vcc
Current_Load
Current_Charge
Power_Load
Power_Charge
Energy_Load
Energy_Charge
Assumes all values are "subscribed" so sends this out periodically:

Accepts the following inputs:
{"method:"set","params":{"Energy_load":<integer>}}
{"method:"set","params":{"Energy_charge":<integer>}}
where integer will usually be 0 and set at the start of every day.
{"method:"status","params":{"data":[<list of Data Values]}}
{"method":list_data,"params",{}} - Returns list of data values with units and type (RO or RW)
{"method":"initialize","params":{}} - Resets all counters and min/max values. TYpically called once per day.

Expects, but ignores the following methods:
"subscribe" - We assume everything is subscribed
"unsubscribe"
"tokenAcquire", "tokenForceAcquire", "tokenRelease", "tokenOwner" - Only one data client, no tokens used at this level.
"power" - doesn't really apply
"suspend", "resume", - is there any point?
"restart", "shutdown" - may not apply in this environment
"broker_status" - no point

TO DO
	- Make resistor values setable and store them in EEPROM.
*/

//#include <RingBufferDMA.h>
//#include <RingBuffer.h>

#define S1DEBUG 1
#define EM_VERSION 0.76




//#define ACS715_25_mV_per_A 55.0 // This is from the datasheet with Vcc = 3.3v

// Default values of voltage dividers
#define V_DIV_LOW	 4220.0
#define V_DIV_HIGH  19100.0
#define BROKER_MIN_UPDATE_RATE_MS 2000
#define MAIN_BUFFER_SIZE 1500
#define TOKEN_OWN_SIZE 40


#include "broker_util.h"
#include "E_Mon.h"
#include "broker_data.h"
#include <ADC_Module.h>
#include <ADC.h>
#include <TimeLib.h>
#include <aJSON.h>

// define constants
const uint16_t VCC = 3300; // in mV
const uint8_t ADC_CHANNEL_LOAD_CURRENT		= PIN_A0;	// (14) ADC0_SE5b
const uint8_t ADC_CHANNEL_CHARGE_CURRENT	= PIN_A1;	// (15) ADC0_SE14
const uint8_t ADC_CHANNEL_VOLTAGE			= PIN_A2;	// (16) ADC0_SE8/ADC1_SE8
const int8_t F_PIN_LOAD				= 10;
const int8_t F_PIN_CHARGE			= 9;
const uint16_t LOOP_DELAY_TIME_MS = 2000;	// Time in ms to wait between sampling loops.
const uint8_t BROKERDATA_OBJECTS = 11;
const char TZ[] = "UTC"; // Time zone is forced to UTC for now.

// Define Objects
ADC adc = ADC(); // Teensy adc object

// Someday we might load all this from EEPROM so that the code can be as generic as possible.
StaticData	volt_div_low("V_div_low", "Ohms", V_DIV_LOW,7,2);
StaticData	volt_div_high("V_div_high", "Ohms", V_DIV_HIGH,7,2);
VoltageData v_batt("Voltage", adc, ADC_CHANNEL_VOLTAGE, volt_div_high.getValue(), volt_div_low.getValue(),6,3);
CurrentData	current_l("Load_Current", adc, ADC_CHANNEL_LOAD_CURRENT, ACS722_10U, F_PIN_LOAD, VCC,6,3);
CurrentData	current_c("Charge_Current", adc, ADC_CHANNEL_CHARGE_CURRENT, ACS711_25B, F_PIN_CHARGE, VCC,6,3);
PowerData	power_l("Load_Power", current_l, v_batt,7,3);
PowerData	power_c("Charge_Power", current_c, v_batt,7,3);
EnergyData	energy_l("Load_Energy", power_l,10,3);
EnergyData	energy_c("Charge_Energy", power_c,10,3);
TimeData	date_sys("Date_UTC",true,8,0);
TimeData	time_sys("Time_UTC",false,6,0);
// Now an array to hold above objects as their base class.
BrokerData *brokerobjs[BROKERDATA_OBJECTS];


// Global variables
int16_t	json_id = 0;
bool status_verbose = true; // true is default.
bool data_map[BROKERDATA_OBJECTS]; // Used to mark broker objects we are interested in.
char broker_start_time[] = "20000101120000"; // Holds start time
char in_buffer[MAIN_BUFFER_SIZE]; // Holds incoming data
uint16_t	in_buffer_idx = 0;
char token_owner[TOKEN_OWN_SIZE]; // Holds current Token owner

// Constants
const char ON_NEW[] = "on_new";
const char ON_CHANGE[] = "on_change";

const uint8_t JSON_REQUEST_COUNT = 12; // How many different request types are there.
enum json_r_t {
	BROKER_STATUS = 0,
	BROKER_SUBSCRIBE = 1,
	BROKER_UNSUBSCRIBE = 2,
	BROKER_SET = 3,
	BROKER_LIST_DATA = 4,
	BROKER_RESET = 5,
	BROKER_B_STATUS = 6,
	BROKER_TOK_ACQ = 7,
	BROKER_TOK_FACK = 8,
	BROKER_TOK_REL = 9,
	BROKER_TOK_OWN = 10,
	BROKER_ERROR = 11
};
const char *REQUEST_STRINGS[JSON_REQUEST_COUNT] = { "status","subscribe","unsubscribe","set","list_data","reset","broker_status","tokenAcquire","tokenForceAcquire","tokenRelease","tokenOwner",""};

#ifdef __cplusplus
extern "C" {
#endif
	void startup_early_hook() {
		WDOG_TOVALL = 10000; // time in ms between resets. 10000 = 10 seconds
		WDOG_TOVALH = 0;
		WDOG_PRESC = 0; // prescaler
		WDOG_STCTRLH = (WDOG_STCTRLH_ALLOWUPDATE | WDOG_STCTRLH_WDOGEN); // Enable WDG
	}
#ifdef __cplusplus
}
#endif

void setup() {
	startup_early_hook(); // Watchdog
	// set the Time library to use Teensy 3.0's RTC to keep time
	setSyncProvider(getTeensy3Time);
	Serial.begin(57600);	//USB
	if (S1DEBUG) Serial1.begin(57600);
	// Some delay when starting up serial.
	uint32_t ulngStart = millis();
	while (true) {
		uint32_t ulngDiff = millis() - ulngStart;
		Serial.print(F("."));
		delay(100);
		if (ulngDiff > 5000) break;
	}
	if (S1DEBUG) {
		Serial1.print("UNC-IMS Power Monitor "); Serial1.println(EM_VERSION);
		Serial.print("UNC-IMS Power Monitor "); Serial.println(EM_VERSION);
		WatchdogReset();
		Serial1.print("Reading charge current on pin:"); Serial1.println(ADC_CHANNEL_CHARGE_CURRENT);
		Serial1.print("Reading load current on pin: "); Serial1.println(ADC_CHANNEL_LOAD_CURRENT);
		Serial1.print("Reading voltage current on pin: "); Serial1.println(ADC_CHANNEL_VOLTAGE);
	}
	//Set up Analog input pins
	pinMode(ADC_CHANNEL_CHARGE_CURRENT, INPUT);
	pinMode(ADC_CHANNEL_LOAD_CURRENT, INPUT);
	pinMode(ADC_CHANNEL_VOLTAGE, INPUT);
	pinMode(LED_BUILTIN, OUTPUT); // May use this
	adc.setReference(ADC_REFERENCE::REF_3V3, ADC_0);
	adc.setAveraging(16); //Set the number of averages. Can be 0, 4, 8, 16 or 32.
	adc.setResolution(16); //the number of bits of resolution. For single-ended measurements: 8, 10, 12 or 16 bits.
	adc.setConversionSpeed(ADC_CONVERSION_SPEED::HIGH_SPEED_16BITS); // change the conversion speed
	adc.setSamplingSpeed(ADC_SAMPLING_SPEED::MED_SPEED); // change the sampling speed
	WatchdogReset();
	if (timeStatus() != timeSet) {
		if (S1DEBUG)  Serial1.println("Unable to sync with the RTC");
	}
	else {
		// NEED TO SET Date_UTS and Time_UTC here.
		double date_to_set = (year() * 10000) + (month() * 100) + day();
		date_sys.setData(date_to_set);
		date_to_set = (hour() * 10000) + (minute() * 100) + second();
		time_sys.setData(date_to_set);
		if (S1DEBUG) {
			Serial1.println("RTC has set the system time to:");
			Serial1.print(date_sys.getData()); Serial1.print("    ");
			Serial1.print(time_sys.getData()); Serial1.println();
		}
	}
	// Add parameter objects to brokerobjs[]
	brokerobjs[0] = &v_batt;
	brokerobjs[1] = &current_l;
	brokerobjs[2] = &current_c;
	brokerobjs[3] = &power_l;
	brokerobjs[4] = &power_c;
	brokerobjs[5] = &energy_l;
	brokerobjs[6] = &energy_c;
	brokerobjs[7] = &volt_div_low;
	brokerobjs[8] = &volt_div_high;
	brokerobjs[9] = &date_sys;
	brokerobjs[10] = &time_sys;
	if (S1DEBUG) Serial1.println("setup almost done");
	setSampleTimeStr(broker_start_time);
	if (S1DEBUG) Serial1.println("setup done");
	WatchdogReset();
}

void loop()
{
	static char in_buffer[MAIN_BUFFER_SIZE]; // Holds incoming data
	static uint16_t	in_buffer_idx = 0;
	static int16_t bracket_count = 0; // Keep track of JSON brackets. Beware brackets in quotes.
	WatchdogReset();
	// Process incoming messages
	if (processInput(in_buffer, in_buffer_idx, bracket_count)) {
		aJsonObject *serial_msg = aJson.parse(in_buffer);
		processJson(serial_msg);
		in_buffer_idx = 0;
		bracket_count = 0;
	}
	WatchdogReset();
	// Retreive new data from RTC
	date_sys.getData();
	time_sys.getData();
	// Retreive new data from ADC
	v_batt.getData();
	current_l.getData();
	current_c.getData();
	// Integrate new values
	power_l.getData();
	power_c.getData();
	energy_l.getData();
	energy_c.getData();
	WatchdogReset();
	// See what subscriptions are up
	if (checkSubscriptions(data_map, brokerobjs, BROKERDATA_OBJECTS) > 0) {
		processSubscriptions(data_map, brokerobjs, BROKERDATA_OBJECTS);
	}
	WatchdogReset();
	delay(LOOP_DELAY_TIME_MS); // MAY BE WORTH LOOKING IN TO LOWERING POWER CONSUMPTION HERE
}

void processSubscriptions(const bool datamap[], BrokerData *broker_objs[], const uint8_t broker_obj_count) {
	/* Based on settings in data_map, generates a subscrition message
	Currently uses aJson to generate message, but this may be un-necessary
	*/

	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "{\"method\":\"subscription\",");
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"params\":{");
	bool first = true;
	for (uint8_t obj_no = 0; obj_no < broker_obj_count; obj_no++) {
		if (datamap[obj_no] == true) {
			broker_objs[obj_no]->getData(); // Update values
			char dataStr[20];	// HOLDS A STRING REPRESENTING A SINGLE VALUE
			if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",");
			else first = false;
			out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"%s\":{", broker_objs[obj_no]->getName());
			broker_objs[obj_no]->dataToStr(dataStr);
			out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"value\":%s", dataStr);
			if (broker_objs[obj_no]->isVerbose()) {
				out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"units\":\"%s\"", broker_objs[obj_no]->getUnit());
				// Only report min and max if they exist
				double min_d = broker_objs[obj_no]->getMin();
				double max_d = broker_objs[obj_no]->getMax();
				if (min_d == min_d) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"min\":\"%f\"", min_d);
				if (max_d == max_d) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"max\":\"%f\"", max_d);
				out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"sample_time\":\"%s\"", broker_objs[obj_no]->getSplTimeStr());
			}
			out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "}"); // Close out this parameter
		}
	}
	out_buffer_idx = addMsgTime(out_buffer, out_buffer_idx, ::TZ,false);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
	//printFreeRam("pSub end");
}

bool processInput(char in_buffer[], uint16_t &in_buffer_idx, int16_t &b_count) {
	/* Adds characters to in_buffer, increments in_buffer_idx, and keeps track of curly brackets
	returns true if complete message found. Message is complete when:
		-found } and bracket count == 0
		-found CR or LF and in_buffer_idx is > 0 
	*/
	bool found_msg_end = false;
	while (Serial.available() && found_msg_end == false) {
		char in_char = Serial.read();
		/*
		switch (in_char) {
			case '{':
				b_count++;
				in_buffer[in_buffer_idx] = in_char;
				in_buffer_idx++;
				break;
			case '}':
				b_count--;
				in_buffer[in_buffer_idx] = in_char;
				in_buffer_idx++;
				if ( b_count == 0 ) found_msg_end = true;
				break;
			case '\r': // Pass through
			case '\n':
				if (in_buffer_idx > 0) found_msg_end = true;
				break;
			default:
				in_buffer[in_buffer_idx] = in_char;
				in_buffer_idx++;
		}
		*/
		if (in_char == '{') b_count++;
		if (in_char == '}') {
			b_count--;
			if (b_count == 0) found_msg_end = true;
		}
		if (in_char == '\r' || in_char == '\n') {
			if (in_buffer_idx > 0 ) found_msg_end = true;
			// Don't add CR of LF to in_buffer
		}
		else if (in_char) {
			in_buffer[in_buffer_idx] = in_char;
			in_buffer_idx++;
			in_buffer[in_buffer_idx] = 0; // So we end with a null
		}
	}
	if (found_msg_end ) {
		if (b_count != 0) {
			// This is an error
			if (S1DEBUG) Serial1.println("Error: Bracket Mismatch");
			in_buffer_idx = 0;
			b_count = 0;
			found_msg_end = false;
		}
		else if (S1DEBUG) {
			Serial1.print("Found JSON message:");
			Serial1.println(in_buffer);
		}
	}
	return found_msg_end;
}

void processJson(aJsonObject *serial_msg) {
	/* processes JSON message in serial_msg*/
	if (serial_msg != NULL) {
		char *aJsonPtr = aJson.print(serial_msg);
		free(aJsonPtr); // So we don't have a memory leak
		// DEBUG END
		uint8_t message_type;
		message_type = getMessageType(&serial_msg, &json_id, ::JSON_REQUEST_COUNT);
		//printFreeRam("pSer gMT");
		//printFreeRam("pSer 1");
		switch (message_type) {
			case (BROKER_STATUS): // Get status of items listed in jsonrpc_params
				if (processStatus(serial_msg, &::status_verbose, ::brokerobjs, BROKERDATA_OBJECTS)) {
					//printFreeRam("pSer status");
					generateStatusMessage();
				}
				break;
			case (BROKER_SUBSCRIBE):
				processBrokerSubscribe(serial_msg);
				//printFreeRam("pSer sub");
				break;
			case (BROKER_UNSUBSCRIBE):
				processBrokerUnubscribe(serial_msg);
				break;
			case (BROKER_SET):
				processSet(serial_msg);
				break;
			case (BROKER_LIST_DATA):
				processListData();
				break;
			case (BROKER_RESET):
				processReset(serial_msg);
				break;
			case (BROKER_B_STATUS):
				processBrokerStatus();
				break;
			case (BROKER_TOK_ACQ):
				processBrokerTokenAck(serial_msg,false);
				break;
			case (BROKER_TOK_FACK):
				processBrokerTokenAck(serial_msg,true);
				break;
			case (BROKER_TOK_REL):
				processBrokerTokenRel();
				break;
			case (BROKER_TOK_OWN):
				processBrokerTokenOwn();
				break;


			default:
				// NEED TO GENERATE AN ERROR HERE
				if (S1DEBUG) {
					Serial1.print(F("ERROR. Cant process: "));
					Serial1.println(message_type);
				}
				break;
		}
	}
	else {
		aJsonObject *response = aJson.createObject();
		aJsonObject *error = aJson.createObject();
		aJson.addItemToObject(response, "jsonrpc", aJson.createItem("2.0"));
		aJson.addItemToObject(response, "id", aJson.createNull());
		aJson.addItemToObject(error, "code", aJson.createItem(-32700));
		aJson.addItemToObject(error, "message", aJson.createItem("Parse error."));
		aJson.addItemToObject(response, "error", error);
		aJson.deleteItem(error);
		aJson.deleteItem(response);
	}
	//printFreeRam("pSer near end 3");
	if (serial_msg) {
		//Serial1.println(F("Deleting serial_msg"));
		aJson.deleteItem(serial_msg); // done with incoming message
	}
}

uint16_t getMessageType(aJsonObject** json_in_msg,int16_t * json_id, const uint8_t json_req_count) {
	// Extract method and ID from message.
	uint8_t json_method = BROKER_ERROR;
	aJsonObject *jsonrpc_method = aJson.getObjectItem(*json_in_msg, "method");
	for (uint8_t j_method = 0; j_method < json_req_count; j_method++) {
		if (!strcmp(jsonrpc_method->valuestring, ::REQUEST_STRINGS[j_method])) {
			if (S1DEBUG) {
				Serial1.print(F("JSON request: ")); Serial1.println(REQUEST_STRINGS[j_method]);
			}
			json_method = j_method;
			break;
		}
	}
	// Get ID here
	aJsonObject *jsonrpc_id = aJson.getObjectItem(*json_in_msg, "id");
	*json_id = jsonrpc_id->valueint;
	return json_method;
}

uint8_t processStatus(aJsonObject *json_in_msg,bool * statusverbose, BrokerData *broker_objs[], const uint8_t broker_obj_count) {
	//printFreeRam("pBS start");
	uint8_t status_matches_found = 0;
	// get params which will contain data and style
	// First process style
	aJsonObject *jsonrpc_params = aJson.getObjectItem(json_in_msg, "params");
	// Extract Style from params
	aJsonObject *jsonrpc_style = aJson.getObjectItem(jsonrpc_params, "style");
	if (!strcmp(jsonrpc_style->valuestring, "terse")) *statusverbose = false;
	else *statusverbose = true;
	clearDataMap(); // Sets all data_map array values to false
	// Now Extract data list
	aJsonObject *jsonrpc_data = aJson.getObjectItem(jsonrpc_params, "data");
	// data will be list of parameters: ["Voltage","Vcc",Current_Load"]
	// Now parse data list and set data_map array values
	aJsonObject *jsonrpc_data_item = jsonrpc_data->child;
	//Serial1.print(jsonrpc_data_item->valuestring);
	//printFreeRam("pBS data 1");
	while (jsonrpc_data_item) { 
		for (uint8_t broker_data_idx = 0; broker_data_idx < BROKERDATA_OBJECTS; broker_data_idx++) {
			//Serial1.print("Comparing "); Serial1.print(jsonrpc_data_item->valuestring); Serial1.print(" to "); Serial1.println(brokerobjs[broker_data_idx]->getName());
			if (!strcmp(jsonrpc_data_item->valuestring, broker_objs[broker_data_idx]->getName())) {
				//Serial1.print(F("B data: ")); Serial1.println(jsonrpc_data_item->valuestring);
				::data_map[broker_data_idx] = true; 
				//Serial1.print(broker_data_idx); Serial1.print("="); Serial1.println(::data_map[broker_data_idx]);
				status_matches_found++;
				break; // break out of for loop
			}
		}
		jsonrpc_data_item = jsonrpc_data_item->next; // Set pointer for jsonrpc_data_item to next item.
	}
	return status_matches_found;
}

uint8_t processBrokerUnubscribe(aJsonObject *json_in_msg) {
	/*Processes an un-subscribe message
	For example:
	{"method" : "unsubscribe",
	"params" : {"data":["Voltage", "Vcc"]}
	"id" : 14}
	*/

	uint8_t unsubscribe_matches_found = 0;
	aJsonObject *jsonrpc_params = aJson.getObjectItem(json_in_msg, "params");
	// Now Extract data list
	aJsonObject *jsonrpc_data = aJson.getObjectItem(jsonrpc_params, "data");

	// Start output
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += printResultStr(out_buffer, out_buffer_idx);
	bool first = true;
	// Now parse data list
	if (jsonrpc_data) {
		aJsonObject *jsonrpc_data_item = jsonrpc_data->child;
		//Serial1.print(jsonrpc_data_item->valuestring);
		//printFreeRam("pBS data 1");
		while (jsonrpc_data_item) {
			bool found = false;
			for (uint8_t broker_data_idx = 0; broker_data_idx < BROKERDATA_OBJECTS; broker_data_idx++) {
				if (!strcmp(jsonrpc_data_item->valuestring, ::brokerobjs[broker_data_idx]->getName())) {
					if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",");
					out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"%s\":{", jsonrpc_data_item->valuestring); // even if it's bad data
					unsubscribe_matches_found++;
					// Set subscription up
					::brokerobjs[broker_data_idx]->unsubscribe();
					out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"status\":\"ok\"}");
					found = true;
					first = false;
					break; // break out of for loop
				}
			}
			if (found == false) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"status\":\"error\"},"); // There should be more to this, but that's all for now.
			jsonrpc_data_item = jsonrpc_data_item->next; // Set pointer for jsonrpc_data_item to next item.
		}
	}
	// Now finish output
	// Should add update rates....
	out_buffer_idx = addMsgId(out_buffer, out_buffer_idx, json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
	return unsubscribe_matches_found;
}

uint8_t processBrokerSubscribe(aJsonObject *json_in_msg) {
	/*Processes a subscribe message
	For example:
	{"method" : "subscribe",
	 "params" : {
		"data":["Voltage", "Vcc"],
		"style":"terse",
		"updates":"on_change",
		"min_update_ms":1000}
	"id" : 14}
	*/
	printFreeRam("pBSub start");
	uint8_t subscribe_matches_found = 0;
	bool subscribe_verbose = true;
	bool subscribe_on_change = true;
	uint32_t subscribe_min_update_ms = __LONG_MAX__;
	uint32_t subscribe_max_update_ms = __LONG_MAX__;
	// First process style
	aJsonObject *jsonrpc_params = aJson.getObjectItem(json_in_msg, "params");

	//char *aJsonPtr; // For debug prints
	//Serial1.print("jsonrpc_params: ");	aJsonPtr = aJson.print(jsonrpc_params);	Serial1.println(aJsonPtr); free(aJsonPtr); // So we don't have a memory leak

	// Extract Optional Style
	aJsonObject *jsonrpc_style = aJson.getObjectItem(jsonrpc_params, "style");
	//Serial1.print("jsonrpc_style: "); aJsonPtr = aJson.print(jsonrpc_style);	Serial1.println(aJsonPtr); free(aJsonPtr); // So we don't have a memory leak
	if (jsonrpc_style) {
		if (!strcmp(jsonrpc_style->valuestring, "terse")) subscribe_verbose = false;
		else subscribe_verbose = true;
	}

	// Extract Optional Updates
	aJsonObject *jsonrpc_updates = aJson.getObjectItem(jsonrpc_params, "updates");
	if (jsonrpc_updates) {
		if (!strcmp(jsonrpc_updates->valuestring, "on_new")) subscribe_on_change = false;
		else subscribe_on_change = true;
	}

	// Extract Optional Min Update Rate
	aJsonObject *jsonrpc_min_rate = aJson.getObjectItem(jsonrpc_params, "min_update_ms");
	//Serial1.print("jsonrpc_min_rate: ");	aJsonPtr = aJson.print(jsonrpc_min_rate);	Serial1.println(aJsonPtr); free(aJsonPtr); // So we don't have a memory leak
	if (jsonrpc_min_rate) 	subscribe_min_update_ms = (uint32_t)jsonrpc_min_rate->valueint; 

	// Extract Optional Max Update Rate
	aJsonObject *jsonrpc_max_rate = aJson.getObjectItem(jsonrpc_params, "max_update_ms");
	//Serial1.print("jsonrpc_max_rate: "); aJsonPtr = aJson.print(jsonrpc_max_rate);	Serial1.println(aJsonPtr); free(aJsonPtr); // So we don't have a memory leak
	if (jsonrpc_max_rate) subscribe_max_update_ms = (uint32_t)jsonrpc_max_rate->valueint;

	// Now some calculations based on https://sites.google.com/site/verticalprofilerupgrade/home/ControllerSoftware/ipc-specification
	//
	if ( subscribe_min_update_ms == __LONG_MAX__ && subscribe_max_update_ms == __LONG_MAX__) {
		// Neither provided, set based on spec
		subscribe_min_update_ms = max(subscribe_min_update_ms, (uint32_t)BROKER_MIN_UPDATE_RATE_MS);
		subscribe_max_update_ms = subscribe_min_update_ms * 4; 
	}
	else {
		// at least one parameter provided
		if (subscribe_max_update_ms == __LONG_MAX__) {
			// Only minimum provided
			subscribe_min_update_ms = max(subscribe_min_update_ms, (uint32_t)BROKER_MIN_UPDATE_RATE_MS); // make minimum is big enough
			subscribe_max_update_ms = subscribe_min_update_ms * 4; // set Max, This is the spec
		}
		else if (subscribe_min_update_ms == __LONG_MAX__) {
			// Only maximum provided
			subscribe_max_update_ms = max(subscribe_max_update_ms, (uint32_t)BROKER_MIN_UPDATE_RATE_MS); // make minimum is big enough
			subscribe_min_update_ms = max(subscribe_max_update_ms / 4, (uint32_t)BROKER_MIN_UPDATE_RATE_MS); // set Min, This is the spec
		}
		else {
			// both provided
			// can't be less than broker minimum
			subscribe_min_update_ms = max(subscribe_min_update_ms, (uint32_t)BROKER_MIN_UPDATE_RATE_MS);
			subscribe_max_update_ms = max(subscribe_max_update_ms, subscribe_min_update_ms); // Max should be at least as big as min
		}
	}

	// Now Extract data list
	aJsonObject *jsonrpc_data = aJson.getObjectItem(jsonrpc_params, "data");
	if (S1DEBUG) {
		char *aJsonPtr = aJson.print(jsonrpc_data);
		Serial1.print(F("Data Items:"));
		Serial1.println(aJsonPtr);
		free(aJsonPtr); // So we don't have a memory leak
	}

	//Serial1.print("jsonrpc_data: ");	aJsonPtr = aJson.print(jsonrpc_data);	Serial1.println(aJsonPtr); free(aJsonPtr); // So we don't have a memory leak


	// Start output
	bool first = true;
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += printResultStr(out_buffer, out_buffer_idx);
	// data will be list of parameters: ["Voltage","Vcc",Current_Load"]
	// Now parse data list
	if (jsonrpc_data) {
		aJsonObject *jsonrpc_data_item = jsonrpc_data->child;
		while (jsonrpc_data_item) {
			bool found = false;
			for (uint8_t broker_data_idx = 0; broker_data_idx < BROKERDATA_OBJECTS; broker_data_idx++) {
				if (!strcmp(jsonrpc_data_item->valuestring, ::brokerobjs[broker_data_idx]->getName())) {
					if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",");
					out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"%s\":{\"status\":\"ok\"}", jsonrpc_data_item->valuestring); // even if it's bad data
					subscribe_matches_found++;
					// Set subscription up
					::brokerobjs[broker_data_idx]->subscribe(subscribe_min_update_ms, subscribe_max_update_ms);
					::brokerobjs[broker_data_idx]->setSubOnChange(subscribe_on_change);
					::brokerobjs[broker_data_idx]->setVerbose(subscribe_verbose);
					found = true;
					first = false;
					break; // break out of for loop
				}
			}
			//if ( found == false ) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"status\":\"error\"}"); // There should be more to this, but that's all for now.
			jsonrpc_data_item = jsonrpc_data_item->next; // Set pointer for jsonrpc_data_item to next item.
		}
	}
	// Now finish output
	// Should add update rates....
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"max_update_ms\":%lu", subscribe_max_update_ms);
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"min_update_ms\":%lu", subscribe_min_update_ms);
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"updates\":\"%s\"", subscribe_on_change?ON_CHANGE:ON_NEW); //ON_NEW ON_CHANGE
	out_buffer_idx = addMsgTime(out_buffer, out_buffer_idx,::TZ,true);
	out_buffer_idx = addMsgId(out_buffer, out_buffer_idx,json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
	return subscribe_matches_found;
}

uint8_t processSet(aJsonObject *json_in_msg) {
	/* process set message
	{"method" : "set", "params" : {"Load_Energy":0,"Charge_Energy":0},"id" : 17}
	*/
	aJsonObject *jsonrpc_params = aJson.getObjectItem(json_in_msg, "params");
	if (S1DEBUG) {
		Serial1.print("set params:");
		char *aJsonPtr = aJson.print(jsonrpc_params);
		Serial1.println(aJsonPtr);
		free(aJsonPtr); // So we don't have a memory leak
	}
	uint8_t parameters_set = 0;
	// Start output
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += printResultStr(out_buffer, out_buffer_idx);
	// So now we have 1 to n items of unknown name. Will have to iterate, and check existance.
	bool first = true;
	for (uint8_t broker_data_idx = 0; broker_data_idx < BROKERDATA_OBJECTS; broker_data_idx++) {
		aJsonObject *jsonrpc_set_param = aJson.getObjectItem(jsonrpc_params, ::brokerobjs[broker_data_idx]->getName());
		if (jsonrpc_set_param) {
			// Found one!
			if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ","); // preceding comma
			out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"%s\":{\"status\":", ::brokerobjs[broker_data_idx]->getName()); // name of parameter and status...
			if (!::brokerobjs[broker_data_idx]->isRO()) {
				// Settable
				double setValue = -999;
				if (jsonrpc_set_param->type == aJson_Int) {
					setValue = (double)jsonrpc_set_param->valueint;
				}
				else if (jsonrpc_set_param->type == aJson_Long) {
					setValue = (double)jsonrpc_set_param->valuelong;
				}
				else if (jsonrpc_set_param->type == aJson_Float) {
					setValue = (double)jsonrpc_set_param->valuefloat;
				}
				bool success = ::brokerobjs[broker_data_idx]->setData((double)setValue);
				if (S1DEBUG) {
					Serial1.print("Setting ");
					Serial1.print(::brokerobjs[broker_data_idx]->getName());
					Serial1.print(" to ");
					Serial1.println(setValue);
				}
				if (success) {
					out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"ok\"}");
					parameters_set++;
				}
				else {
					// couldn't set
					out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"error, couldn't set\"}");
				}
			}
			else out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"error, RO\"}");
			first = false;
		}
	}
	// Now finish output
	// Should add update rates....
	out_buffer_idx = addMsgTime(out_buffer, out_buffer_idx,::TZ,true);
	out_buffer_idx = addMsgId(out_buffer, out_buffer_idx,json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
	return parameters_set;
}

void processListData() {
	/* List data parameters available.
	{"method" : "list_data","id" : 18}
	*/
	// Start output
	bool first = true;
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += printResultStr(out_buffer, out_buffer_idx);
	char param_type[] = "\"Rx\"";
	for (uint8_t broker_data_idx = 0; broker_data_idx < BROKERDATA_OBJECTS; broker_data_idx++) {
		if (::brokerobjs[broker_data_idx]->isRO()) param_type[2] = 'O';
		else param_type[2] = 'W';
		// Break this into multiple lines just to make it easier to read.
		if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",");
		out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"%s\":", ::brokerobjs[broker_data_idx]->getName());
		out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "{\"units\":\"%s\",", ::brokerobjs[broker_data_idx]->getUnit());
		out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"type\":%s}", param_type);
		first = false;
	}
	//Add message_time
	if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",");
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"message_time\":{\"units\":\"UTC\",\"type\":\"RO\"}");
	out_buffer_idx = addMsgId(out_buffer, out_buffer_idx, json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
}

uint8_t processReset(aJsonObject *json_in_msg) {
	/*Call reset for requested parameters. This will set min and max to 0. if RW, will also set value to 0.
	Message format is like "status", but no "style". 
	Response is like "subscribe";
	*/
	//printFreeRam("pR start");
	uint8_t reset_matches_found = 0;
	// First process style
	aJsonObject *jsonrpc_params = aJson.getObjectItem(json_in_msg, "params");
	clearDataMap(); // Sets all data_map array values to false
	// Now Extract data list
	aJsonObject *jsonrpc_data = aJson.getObjectItem(jsonrpc_params, "data");
	bool first = true;
	bool found = false;
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += printResultStr(out_buffer, out_buffer_idx);
	// data will be list of parameters: ["Voltage","Vcc",Current_Load"]
	// Now parse data list
	aJsonObject *jsonrpc_data_item = jsonrpc_data->child;
	while (jsonrpc_data_item) {
		found = false;
		if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",");
		first = false;
		out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"%s\":{", jsonrpc_data_item->valuestring); // even if it's bad data
		for (uint8_t broker_data_idx = 0; broker_data_idx < BROKERDATA_OBJECTS; broker_data_idx++) {
			if (!strcmp(jsonrpc_data_item->valuestring, ::brokerobjs[broker_data_idx]->getName())) {
				// got a match
				found = true;
				out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"status\":\"ok\"}");
				::brokerobjs[broker_data_idx]->resetMin();
				::brokerobjs[broker_data_idx]->resetMax();
				if (!brokerobjs[broker_data_idx]->isRO()) ::brokerobjs[broker_data_idx]->setData(0); // only for "RW" parameters
				reset_matches_found++;
				break; // break out of for loop
			}
		}
		if (found == false) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"status\":\"error\"}"); // There should be more to this, but that's all for now.
		jsonrpc_data_item = jsonrpc_data_item->next; // Set pointer for jsonrpc_data_item to next item.
	}
	out_buffer_idx = addMsgTime(out_buffer, out_buffer_idx,::TZ,true);
	out_buffer_idx = addMsgId(out_buffer, out_buffer_idx,::json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
	return reset_matches_found;
}

void processBrokerStatus() {
	/*
	{
	"result" : {
		"suspended":True|False,
		"power_on":True|False|"unknown",
		"instr_connected":True|False,
		"db_connected":True|False,
		"start_time":<timestamp>,
		"last_data_time":<timestamp>|"None",
		"last_db_time": <timestamp>|"None",
		"message_time" : {
			"value" : 2010092416310000,
			"units" : "EST"}
	},
	"id":8
	}
	*/

	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += printResultStr(out_buffer, out_buffer_idx);
	// First constant stuff
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"suspended\":\"False\"");
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"power_on\":\"True\"");
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"instr_connected\":\"True\"");
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"db_connected\":\"False\"");
	// Now non-constant
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"start_time\":%s", ::broker_start_time);
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"last_data_time\":%s", ::v_batt.getSplTimeStr());
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"last_db_time\":\"None\"");
	out_buffer_idx = addMsgTime(out_buffer, out_buffer_idx,::TZ,true);
	out_buffer_idx = addMsgId(out_buffer, out_buffer_idx,::json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
}

void generateStatusMessage() {
	//printFreeRam("gSM start");
						  // based on contents of datamap array, generate status message.
						  /*
						  {
						  "result" : {
						  "Voltage" : {
						  "value" : 13.5,
						  "units" : "V",
						  "sample_time":20110801135647605},
						  "Vcc" : {
						  "value" : 4.85,
						  "units" : "V",
						  "sample_time":20110801135647605}}
						  "id" : 1
						  }*/
	bool first = true;
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += printResultStr(out_buffer, out_buffer_idx);
	for (uint8_t obj_no = 0; obj_no < BROKERDATA_OBJECTS; obj_no++) {
		if (::data_map[obj_no] == true) {
			char statusValue[20] = "-999"; // Holds status double value as a string
			::brokerobjs[obj_no]->dataToStr(statusValue);
			if (!first) out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ","); // preceding comma
			out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"%s\":{", ::brokerobjs[obj_no]->getName());
			out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "\"value\":%s", statusValue);
			if (::status_verbose == true) {
				out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"units\":\"%s\"", ::brokerobjs[obj_no]->getUnit());
				// Only report min and max if they exist
				double min_d = ::brokerobjs[obj_no]->getMin();
				double max_d = ::brokerobjs[obj_no]->getMax();
				if (min_d == min_d) {
					::brokerobjs[obj_no]->dataToStr(statusValue);
					out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"min\":%s", statusValue);
				}
				if (max_d == max_d) {
					::brokerobjs[obj_no]->dataToStr(statusValue);
					out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"max\":%s", statusValue);
				}
				out_buffer_idx += sprintf(out_buffer + out_buffer_idx, ",\"sample_time\":%s", ::brokerobjs[obj_no]->getSplTimeStr());
			}
			out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "}");
			first = false;
		}
	}
	out_buffer_idx = addMsgTime(out_buffer, out_buffer_idx, ::TZ,true);
	out_buffer_idx = addMsgId(out_buffer, out_buffer_idx, json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
}

void processBrokerTokenAck(aJsonObject *json_in_msg,bool force) {
	/* This is currently the simplest implementation. Ignores Force.
	Should compare name to current value and deny of they don't match, but due to the nature of this "broker" there can only be one connection at a time.
	*/
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	aJsonObject *jsonrpc_params = aJson.getObjectItem(json_in_msg, "params");
	aJsonObject *jsonrpc_name = aJson.getObjectItem(jsonrpc_params, "name");
	Serial1.println(jsonrpc_name->valuestring);
	strncpy(token_owner, jsonrpc_name->valuestring, TOKEN_OWN_SIZE);
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "{\"result\":\"ok\",\"id\":%u}", ::json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
}

void processBrokerTokenRel() {
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	token_owner[0] = 0; // clears owner
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "{\"result\":\"ok\",\"id\":%u}", ::json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
}

void processBrokerTokenOwn() {
	char out_buffer[MAIN_BUFFER_SIZE]; // Holds outgoing data
	uint16_t out_buffer_idx = 0;
	out_buffer_idx += sprintf(out_buffer + out_buffer_idx, "{\"result\":\"%s\",\"id\":%u}", token_owner,::json_id);
	Serial.println(out_buffer);
	if (S1DEBUG) {
		Serial1.print(out_buffer_idx);
		Serial1.print(" - ");
		Serial1.println(out_buffer);
	}
}



void clearDataMap() {
	for (uint8_t i = 0; i < BROKERDATA_OBJECTS; i++) {
		::data_map[i] = false;
	}
}

const char * BoolToString(const bool b)
{
	return b ? "true" : "false";
}

time_t getTeensy3Time()
{
	return Teensy3Clock.get();
}

void WatchdogReset()
{
	// use the following 4 lines to kick the dog
	noInterrupts();
	WDOG_REFRESH = 0xA602;
	WDOG_REFRESH = 0xB480;
	interrupts();
	// if you don't refresh the watchdog timer before it runs out, the system will be rebooted
	delay(1); // the smallest delay needed between each refresh is 1ms. anything faster and it will also reboot.
}
