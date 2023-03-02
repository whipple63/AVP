package edu.unc.ims.avp;

import org.json.JSONObject;
import org.json.JSONException;
import java.util.Map;
import java.util.HashMap;
import java.util.Iterator;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Calendar;
import java.util.TimeZone;
import edu.unc.ims.avp.adapters.BrokerAdapter;

/**
 * NOTE: This class is deprecated.  BrokerMessage is a better choice.
 * 
 * BrokerReply constructs a JSON reply (www.json.org) to a JSON-RPC (json-rpc.org) 
 * request (method invocation).  Replies take the form of a response (id must match 
 * that of the request) or a notification (id must be null).  The reply can be passed
 * back to the control port listener and will include any requested data, errors
 * or just an ok to indicate command success.
 * 
 */
public class BrokerReply {
    
    private HashMap<String, Object> mResults = new HashMap<String, Object>();   // map of param names and results
    private String mMethod;         // Requested JSON method
    public void setMethod(String method) { mMethod = method; }
    private boolean mVerbose;       // Determines whether short (false) or long (true) responses are returned.
    public void setVerbose(boolean verbose) { mVerbose = verbose; }
    private boolean mOnNew;         // Whether results are returned every new reading (true) or only when value has changed.
    private BrokerAdapter mDevice;  // The servicing BrokerAdapter. Result data returned through mDevice.onData
    public void setDevice(BrokerAdapter device) { mDevice = device; }
    private boolean mHasMajorError; // no parameter value can be returned; no JSON message ID will be returned
    public boolean hasMajorError() { return mHasMajorError; }
    private boolean mHasMinorError; // only individual parameter values affected; JSON message ID will be returned
    private long mTimestamp;        // Result timestamp
    public void addTimestamp(long ts) { mTimestamp = ts; }
    private long mMinInterval;
    private long mMaxInterval;
    private int mID;                // JSON message ID of the reply. Should match the message ID of the request.
    public void setId(int id) { mID = id; }

    private HashMap<String, Boolean> mChanged = new HashMap<String, Boolean>(); // map of param names and whether value has changed.
    private BrokerError mError;     // BrokerError object for this result
    private Iterator<Map.Entry<String, Object>> mIter = mResults.entrySet().iterator(); // Iterator over the result HashMap

    private static final boolean DAYLIGHT_NAME = false; // daylight or standard timezone name in reply (e.g., EST vs. EDT)

    
    /**
     * Empty constructor
     */
    public BrokerReply() {
        this("");
    }

    /**
     * Constructor given method default values of verbose=t and onNew=t
     * @param methodString 
     */
    public BrokerReply(String methodString) {
        this(methodString, true, true, null);
    }

    /**
     * Constructor populates member variables with parameters given
     * @param method
     * @param verbose
     * @param onNew
     * @param device 
     */
    public BrokerReply(String method, boolean verbose, boolean onNew,
            BrokerAdapter device) {
        mMethod = method;
        mVerbose = verbose;
        mOnNew = onNew;
        mDevice = device;
        mHasMajorError = false;
        mHasMinorError = false;
        mTimestamp = 0;
        mMinInterval = 0;
        mMaxInterval = 0;
    }

    
    /**
     * Adds a major error to the result. The error cannot be related to an
     * individual parameter, so it applies to the entire request and is stored in
     * mError.
     * 
     * @param code error code
     */
    public void addError(int code) {
        mError = new BrokerError(code);
        mHasMajorError = true;
    }

    /**
     * Adds a major error to the result. The error cannot be related to an
     * individual parameter, so it applies to the entire request and is stored in
     * mError.
     * 
     * @param code  error code
     * @param data  string additional information
     */
    public void addError(int code, String data) {
        mError = new BrokerError(code, data);
        mHasMajorError = true;
    }

    /**
     * Adds a minor error to the result. The error is related to an individual
     * parameter and stored in the result HashMap.
     * 
     * @param param associated with the error
     * @param code  error code
     */
    public void addError(String param, int code) {
        BrokerError error = new BrokerError(code);
        addResult(param, error, true);
        mHasMinorError = true;
    }

    
    /**
     * Adds a new key-value pair to the result HashMap and updates mChanged HashMap
     * to indicate if the value has changed.
     * 
     * @param param     associated with this result
     * @param result    the result
     * @param changed   indicates changed data
     */
    public void addResult(String param, Object result, boolean changed) {
        mResults.put(param, result);
        mIter = mResults.entrySet().iterator();
        mChanged.put(param, changed);
    }

    /**
     * addResult assumes the parameter value has changed if no boolean is provided
     * as a parameter.
     * 
     * @param param
     * @param result 
     */
    public void addResult(String param, Object result) {
        addResult(param, result, true);
    }

    /**
     * 
    @return true if any parameter has changed, or any error has been recorded
     */
    public boolean hasNew() {
        return (mChanged.containsValue(true) || mHasMajorError || mHasMinorError);
    }


    /**
     * Setting minimum and maximum intervals to be returned in the reply. Only used
     * for replies to subscribe requests.
     * 
     * @param minInterval
     * @param maxInterval 
     */
    public void setIntervals(long minInterval, long maxInterval) {
        mMinInterval = minInterval;
        mMaxInterval = maxInterval;
    }

    
    /**
     * Parse timestamp value into the appropriate format.
     */
    private long tsValue() {
        SimpleDateFormat formatter = new SimpleDateFormat("yyyyMMddHHmmssSS");
        String timeStr = formatter.format(new Date(mTimestamp));
        return Long.parseLong(timeStr);
    }

    
    /* Deprecate?
     * look for handling of mID - that's the only difference. if that gets
     * cleaned up then convert to just using joJSONNotification...
     */
    public JSONObject toJSONObject() throws JSONException {
        JSONObject obj = new JSONObject();
        toJSONObject(obj);
        return obj;
    }
    /* Adds mID to obj and calls toJSONNotification(obj).
    Deprecate? */

    public void toJSONObject(JSONObject obj) throws JSONException {
        obj.put("id", mID);
        toJSONNotification(obj);
    }

    /**
     * Create the JSON message based on what has been added to this object.
     * 
     * @param obj
     * @throws JSONException 
     */
    public void toJSONNotification(JSONObject obj) throws JSONException {
        JSONObject resultObject;
        JSONObject paramObject;
        JSONObject tsObject;

        // Major errors convert (BrokerError) mError to JSON, add and return
        if (mHasMajorError) {
            JSONObject errorObject = mError.toJSONObject(false);
            obj.put("error", errorObject);
            return;
        }

        // Replies are generated differently based on what method was called
        if ( mMethod.equals("status") || mMethod.equals("subscription")) {
            /* replies to status:
                . create a new resultObject
                . create a new paramObject
                . iterate through mIter, adding entries to paramObject
                . add a timestamp to paramObject
                . add the header "result" to paramObject
                . append paramObject to resultObject
             */
            resultObject = new JSONObject();
            while (mIter.hasNext()) {
                paramObject = new JSONObject();
                Map.Entry<String, Object> entry = mIter.next();
                String key = entry.getKey();
                Object value = entry.getValue();
                if (value instanceof BrokerError) {
                    paramObject = ((BrokerError) value).toJSONObject(false);
                } else {
                    if (value instanceof Double) {
                        paramObject.put("value", ((Double) value).doubleValue());
                    } else if (value instanceof Integer) {
                        paramObject.put("value", ((Integer) value).intValue());
                    } else if (value instanceof Boolean) {
                        paramObject.put("value", ((Boolean) value).booleanValue());
                    } else if (value instanceof String) {
                        paramObject.put("value", ((String) value));
                    } 
                    if (mVerbose) {
                        paramObject.put("units", mDevice.JSONParameters.get(key)[mDevice.UNITS_INDEX]);
                    }
                }
                if (mOnNew || mChanged.get(key).booleanValue()) {
                    resultObject.put(key, paramObject);
                }
            }
            tsObject = new JSONObject();
            tsObject.put("value", tsValue());
            if (mVerbose) {
                tsObject.put("units", Calendar.getInstance().getTimeZone().getDisplayName(DAYLIGHT_NAME, TimeZone.SHORT));
            }
            resultObject.put("sample_time", tsObject);
            if (mMethod.equals("status")) {
                obj.put("result", resultObject);
            } else {
                obj.put("method", "subscription");
                obj.put("params", resultObject);
            }



        } else if (mMethod.equals("set") || mMethod.equals("subscribe") || mMethod.equals("unsubscribe")) {
            /*
            replies to set, subscribe, and unsubscribe requests are similar
            . create a new resultObject
            . create a new paramObject
            . iterate through mIter, adding entries to paramObject
            . for subscription requests, add interval information
            . append paramObject to resultObject
             */
            resultObject = new JSONObject();
            while (mIter.hasNext()) {
                paramObject = new JSONObject();
                Map.Entry<String, Object> entry = mIter.next();
                String key = entry.getKey();
                Object value = entry.getValue();
                if (value instanceof BrokerError) {
                    paramObject = ((BrokerError) value).toJSONObject(true);
                } else {
                    paramObject.put("status", (String) value);
                }
                resultObject.put(key, paramObject);
            }
            if (mMethod.equals("subscribe")) {
                resultObject.put("max_update_ms", mMaxInterval);
                resultObject.put("min_update_ms", mMinInterval);
            }
            obj.put("result", resultObject);


        } else if (mMethod.equals("power")
                || mMethod.equals("initialize")
                || mMethod.equals("restart")
                || mMethod.equals("tokenAcquire")
                || mMethod.equals("tokenForceAcquire")
                || mMethod.equals("tokenRelease")
                || mMethod.equals("tokenOwner")
                || mMethod.equals("suspend")
                || mMethod.equals("resume")
                || mMethod.equals("shutdown")
                || mMethod.equals("connect")
                || mMethod.equals("disconnect")
                || mMethod.equals("softReset")
                || mMethod.equals("take_sample")
                || mMethod.equals("sampler_on")
                || mMethod.equals("get_file")
                || mMethod.equals("delete_file")
                || mMethod.equals("start_collection")
                || mMethod.equals("stop_collection")
                || mMethod.equals("wipe")
                || mMethod.equals("start_sampling")
                || mMethod.equals("stop_sampling")
                || mMethod.equals("start_logging")
                || mMethod.equals("stop_logging")
                || mMethod.equals("calibratePressure")
                ) {
            /*
            for above listed:
            . add "result" entry that contains the name of the requested method
             */
            Object value = mResults.get(mMethod);
            obj.put("result", (String) value);


        } else if (mMethod.equals("list_data")) {
            resultObject = new JSONObject();
            Iterator<Map.Entry<String, String[]>> iter = mDevice.JSONParameters.
                    entrySet().iterator();
            while (iter.hasNext()) {
                paramObject = new JSONObject();
                Map.Entry<String, String[]> entry = iter.next();
                String ps = entry.getKey();
                paramObject.put("units", entry.getValue()[0]);
                paramObject.put("type", entry.getValue()[1]);
                resultObject.put(ps, paramObject);
            }
            tsObject = new JSONObject();
            tsObject.put("units", Calendar.getInstance().getTimeZone().
                    getDisplayName(DAYLIGHT_NAME, TimeZone.SHORT));
            tsObject.put("type", "RO");
            resultObject.put("sample_time", tsObject);
            obj.put("result", resultObject);

        } else if (mMethod.equals("broker_status")) {
            // results are added as key-value pairs using addResult
            resultObject = new JSONObject();
            while (mIter.hasNext()) {
                Map.Entry<String, Object> entry = mIter.next();
                String key = entry.getKey();
                Object value = entry.getValue();
                if (value instanceof BrokerError) {
                    resultObject = ((BrokerError) value).toJSONObject(true);
                } else {
                    resultObject.put(key, (String) value);
                }
            }
            obj.put("result", resultObject);
            
        } else {
            Logger.getLogger().log("toJSONNotification called for unsupported method "
                    + mMethod + ". This shouldn't happen.", this.getClass().getName(), Logger.LogLevel.ERROR);
        }
    }

    public JSONObject toJSONNotification() throws JSONException {
        JSONObject obj = new JSONObject();
        toJSONNotification(obj);
        return obj;
    }
}
