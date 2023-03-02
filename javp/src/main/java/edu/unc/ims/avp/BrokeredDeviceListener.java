package edu.unc.ims.avp;

import org.json.JSONObject;

/**
Interface to listen for data from a brokered device.
*/
public interface BrokeredDeviceListener {
    /**
    Data item from a brokered device.
    @param  d   The data item.
    */
    void onData(JSONObject d);
    boolean isActive();
}
