/* Functions specific to the Energry Monitoring application*/

#include "E_Mon.h"

#define MS_PER_HR 3600000


uint16_t ADCData::getADCreading() {
	uint32_t pin_value = _adc->analogRead(_channel,ADC_0);
	uint32_t max_value = _adc->getMaxValue(ADC_0);
	uint16_t mV = 3300 * ((double)pin_value/ (double)max_value);
	_getTimeDelta();
	/*
	if (S1DEBUG) {
		Serial1.print("pin: "); Serial1.print(_channel);
		Serial1.print(" value: "); Serial1.print(pin_value);
		Serial1.print("/"); Serial1.print(max_value);
		Serial1.print(",in mV = "); Serial1.println(mV);
	}
	*/
	return mV;
}


double	CurrentData::getData() {
	// Returns current in Amps. Assumes Vcc = 3.3volts
	// Vout = (Sensitivity * i + Vcc/2)
	uint16_t adc_mV = getADCreading();
	//Serial1.printf("ADC current reading is: %d mV, offset is %d and sens is %d\n", adc_mV, _offset_mV, _mV_per_A);
	double current_A = (double)(adc_mV  - _offset_mV) / (double)_mV_per_A;
	// May want to check if data seems valid 
	_setDataValue(current_A);
	_getTimeDelta();
	_checkMinMax();
	return _data_value;
}

uint16_t CurrentData::lookupACSsens(ACS_MODELS model) {
	// Returns mV/A for this IC.
	switch (model) {
		case ACS711_12B: return 110;
		case ACS711_25B: return 55;
		case ACS715_20A: return 185;
		case ACS715_30A: return 133;
		case ACS722_05B: 
		case ACS722_10U: return 264;
		case ACS722_10B: 
		case ACS722_20U: return 132;
		case ACS722_20B: 
		case ACS722_40U: return 66;
		case ACS722_40B: return 33;
		default: return 0;
	}
	return 0;
}

uint16_t CurrentData::lookupACSoffset(ACS_MODELS model, uint16_t Vcc_mV) {
	// Returns mV offset for this IC.
	uint16_t offset_mV = 0;
	switch (model) {
		case ACS711_12B: offset_mV = Vcc_mV / 2; break;
		case ACS711_25B: offset_mV = Vcc_mV / 2; break;
		case ACS715_20A: Vcc_mV * 0.1; break;
		case ACS715_30A: Vcc_mV * 0.1; break;
		case ACS722_05B: offset_mV = Vcc_mV / 2; break;
		case ACS722_10U: offset_mV = Vcc_mV * 0.1; break;
		case ACS722_10B: offset_mV = Vcc_mV / 2; break;
		case ACS722_20U: offset_mV = Vcc_mV * 0.1; break;
		case ACS722_20B: offset_mV = Vcc_mV / 2; break;
		case ACS722_40U: offset_mV = Vcc_mV * 0.1; break;
		case ACS722_40B: offset_mV = Vcc_mV / 2; break;
	}
	if (true) Serial1.printf("Offset = %d\n",offset_mV);
	return offset_mV;
}

int8_t CurrentData::lookupACSfunction(ACS_MODELS model) {
	// returns 0 if function is input, 1 if it is an output, -1 if unused or unknown
	switch (model) {
		// Pin indicates current FAULT when low
		case ACS711_12B:
		case ACS711_25B: return 0;
		// Pin is used passivly as FILTER
		case ACS715_20A:
		case ACS715_30A: return -1;
		// this chip has BW_SEL (bandwidth selection). Ground = 80kHz, Vcc = 20 kHz.
		case ACS722_05B:
		case ACS722_10U:
		case ACS722_10B:
		case ACS722_20U:
		case ACS722_20B:
		case ACS722_40U:
		case ACS722_40B: return 1;
	}
	return -1;
}

double VoltageData::getData() {
	//method returns voltage in volts
	uint16_t voltage_mV = getADCreading();
	voltage_mV *= _v_div();
	// May want to check if data seems valid 
	_setDataValue((double)voltage_mV / 1000.0);
	_checkMinMax();
	return _data_value;
}


double PowerData::getData() {
	// Power is voltage times current. We have _voltage and _current.
	// MAYT WANT TO MAKE SURE VOLTAGE AND CURRENT DATA ISN'T TOO OLD.
	_setDataValue(_voltage->getValue() * _current->getValue());
	_checkMinMax();
	_getTimeDelta();
	return _data_value;
}


bool PowerData::setData(double set_value) {
	if (set_value == 0) {
		resetData();
		return true;
	}
	else return false;
}

void PowerData::resetData() {
	_data_value = 0;
	resetMin();
	resetMax();
}

double EnergyData::getData() {
	// Returns Energy in Wh.
	// First see what our current power is
	const double power_W = _power->getValue();
	// Assume it's constant since last sample and get new energy value
	const double energy_since_last = (power_W * (double)_getTimeDelta()) / (double)MS_PER_HR;
	// Now totalize this.
	_setDataValue(_data_value + energy_since_last);
	return _data_value;
}
bool EnergyData::setData(double energy_Wh) {
	// In certain instances, like after a reboot, _data_value should be initialized to a non-zero value.
	_setDataValue(energy_Wh);
	_getTimeDelta();
	return true;
}




/*

FOUND CODE:

double calcIrms(uint8_t NUMBER_OF_SAMPLES, uint8_t Channel, double supply_voltage) {
int ADC_COUNTS = 65536 / 2; //15bit due to single ended.
int ICAL = 100; //current constant = (100 / 0.050) / 20 = 100

for (uint8_t n = 0; n < NUMBER_OF_SAMPLES; n++) {
lastSampleI = sampleI;
sampleI = ads.readADC_SingleEnded(Channel);
lastFilteredI = filteredI;
filteredI = 0.996 * (lastFilteredI + sampleI - lastSampleI);

// Root-mean-square method current
// 1) square current values
sqI = filteredI * filteredI;
// 2) sum
sumI += sqI;
}

double I_RATIO = ICAL * ((supply_voltage) / (ADC_COUNTS));
double Irms = I_RATIO * sqrt(sumI / NUMBER_OF_SAMPLES);

//Reset accumulators
sumI = 0;

return Irms;
}

*/