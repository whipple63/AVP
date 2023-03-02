package edu.unc.ims.avp;

import org.json.JSONObject;

/**
 * NOTE: This class is deprecated.  It doesn't do anything.
 * 
 * Data item from a brokered device.
*/
public class BrokeredData {
    /**
    x.
    */
    private JSONObject mData;

    /**
    Data item from a brokered device.
    @param  j   data
    */
    public BrokeredData(final JSONObject j) {
        mData = j;
    }

    /**
    Get data.
    @return JSONObject of data
    */
    public final JSONObject getData() {
        return mData;
    }

    /**
    String.
    @return String
    */
    public final String toString() {
        return mData.toString();
    }
}
