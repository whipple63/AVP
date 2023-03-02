// E_Mon.h

#ifndef _E_MON_h
#define _E_MON_h

#include "broker_data.h"
#include <ADC_Module.h>
#include <ADC.h>

enum ACS_MODELS
	// List of supported ACS7xx current sensors.
{
	ACS711_12B,	// -12 to 12 amps
	ACS711_25B,	// -25 to 25 amps
	ACS715_20A,	//   0 to 20 amps
	ACS715_30A,	//   0 to 30 amps
	ACS722_05B,	//  -5 to  5 amps
	ACS722_10U,	//   0 to 10 amps
	ACS722_10B,	// -10 to 10 amps
	ACS722_20U,	//   0 to 20 amps
	ACS722_20B,	// -20 to 20 amps
	ACS722_40U,	//   0 to 40 amps
	ACS722_40B	// -40 to 40 amps
};

/*
class ADCData is an abstract intermediate class for all data objects which get their data from the Teensy's built in ADC
Always Read Only
*/
class ADCData : public DynamicData {
public:
	ADCData(const char *name, const char *unit, ADC &adc, uint8_t ADCchannel, uint8_t resp_width, uint8_t resp_dec) : DynamicData(name, unit, true, resp_width, resp_dec) {
		_channel = ADCchannel; // should be 0-4
		_adc = &adc;
	}
	uint16_t getADCreading();
	uint8_t	getChannel() { return _channel; }
	double	getValue() { return _data_value; }
	void	setFunction(bool function_value);
protected:
	ADC	*_adc;
private:
	uint8_t	_channel;	// Analog read pin number
};

/*
class VoltageData is a class for all data objects which represent a voltage object
*/
class VoltageData : public ADCData {
public:
	VoltageData(const char *name, ADC &adc, uint8_t ADCchannel, uint32_t high_div, uint32_t low_div, uint8_t resp_width, uint8_t resp_dec) : ADCData(name, "V", adc, ADCchannel, resp_width, resp_dec) {
		_high_div = high_div;
		_low_div = low_div;
	}
	double getData();
	bool	setData(double set_value) { return false; }
private:
	double	_v_div() { return (_high_div + _low_div) / _low_div; }
	double	_high_div;
	double	_low_div;
};

/*
class CurrentData is a class for all data objects which represent a current object
*/
class CurrentData : public ADCData {
public:
	CurrentData(const char *name, ADC &adc, uint8_t ADCchannel, ACS_MODELS model, uint8_t f_pin, uint16_t Vcc_mV, uint8_t resp_width, uint8_t resp_dec) : ADCData(name, "A", adc, ADCchannel,  resp_width, resp_dec) {
		_model = model;
		_f_pin = f_pin;
		_mV_per_A = lookupACSsens(_model);
		_offset_mV = lookupACSoffset(_model, Vcc_mV);
		_funct = lookupACSfunction(_model);
		switch (_funct) {
		case 1:	pinMode(_f_pin, OUTPUT);
			digitalWrite(_f_pin, HIGH); // Set to 80 kHz
			break;
		case 0: pinMode(_f_pin, INPUT); break; // Low = current fault
		case -1: break; // not used
		}
	}
	double	getData();
	bool	setData(double set_value) { return false; }
private:
	int8_t	_f_pin; // Function pin number. <0 is unused.
	int8_t	_funct; 
	uint16_t	_mV_per_A;
	uint16_t	_offset_mV;
	ACS_MODELS	_model;	//ACS7xx variant
	uint16_t	lookupACSsens(enum ACS_MODELS);
	uint16_t	lookupACSoffset(enum ACS_MODELS, uint16_t Vcc_mV);
	int8_t lookupACSfunction(enum ACS_MODELS);
};

/*
class PowerData is a class for all data objects which represent a power object
Always Read Only
*/
class PowerData : public DynamicData {
public:
	PowerData(const char *name, CurrentData &current, VoltageData &voltage, uint8_t resp_width, uint8_t resp_dec) : DynamicData(name, "W", true, resp_width, resp_dec) {
		_voltage = &voltage;
		_current = &current;
	}
	double	getData();	// Calculates new Power based on most recent current and voltage
	bool	setData(double set_value);
	void	resetData();
	double	getValue() { return _data_value; }
private:
	CurrentData	*_current;
	VoltageData	*_voltage;
};

/*
class EnergyData is a class for all data objects which represent an energy object
*/
class EnergyData : public DynamicData {
public:
	EnergyData(const char *name, PowerData &power, uint8_t resp_width, uint8_t resp_dec) : DynamicData(name, "Wh", false, resp_width, resp_dec) {
		_power = &power;
		_data_value = 0; // STARTS AS 0 AND TOTALIZES.
	}
	double getData(); // Calculates new Energy based on most recent power
	bool	setData(double energy_value);	// Used for setting value, usually after reboot.
	bool	resetData() { return setData(0); }
	double	getValue() { return _data_value; }
private:
	PowerData	*_power;
};



#endif

// Function prototypes