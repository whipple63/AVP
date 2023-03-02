package edu.unc.ims.avp;

import org.json.JSONObject;

/**
Broker client listener.
*/
public interface BrokerClientListener {
    /**
    Data arrived.
    @param  d   data.
    */
    void onData(JSONObject d);
    boolean isActive();

}
