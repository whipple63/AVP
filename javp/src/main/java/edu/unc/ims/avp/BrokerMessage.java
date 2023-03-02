package edu.unc.ims.avp;

import org.json.JSONObject;
import org.json.JSONArray;
import org.json.JSONException;
import java.util.Map;
import java.util.HashMap;
import java.util.Iterator;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Calendar;
import java.util.TimeZone;
import java.sql.Timestamp;  // only used in main test routine

/**
 * BrokerMessage constructs a JSON message (www.json.org) using JSON-RPC (json-rpc.org).
 * Messages can be a request (method invocation), a response to a request or a notification.
 * An attempt has been made to conform to JSON-RPC 2.0. Data are added via the add* and set* methods.
 * Once all data are added, the final message is constructed with a call to toJSONResponse, 
 * toJSONRequest, or toJSONNotification.
 * 
 */
public class BrokerMessage {

//    /*
//     * For testing purposes only.  Demonstrates calls to create different kinds
//     * of messages.
//     */
//    public static void main(String [] args) throws Exception {
//        BrokerMessage bm;
//        JSONObject m;
//        
//        //create the simplest response message
//        bm = new BrokerMessage();
//        bm.setId(1);
//        bm.addResult("ok");
//        m=bm.toJSONResponse();
//        System.out.println(m.toString(3));
//        System.out.println("");
//        
//        //create a message with a response object containing multiple K:V pairs (e.g. broker_status)
//        bm = new BrokerMessage();
//        bm.setId(2);
//        //bm.addResult("suspended", true);    // NO! This will cause an unwanted message format iff it is called first
//        bm.addResult("suspended", Boolean.TRUE);    //Note that results MUST be objects (i.e. not boolean, but Boolean)
//        bm.addResult("power_on", "unknown");
//        bm.addResult("start time", ( new Timestamp(System.currentTimeMillis()) ).toString() );
//        m=bm.toJSONResponse();
//        System.out.println(m.toString(3));
//        System.out.println("");
//        
//        //create a message with a response object containing multiple K:V pairs 
//        //with some Values as objects (e.g. status, subscription, etc.)
//        bm = new BrokerMessage();
//        bm.setId(3);
//        bm.addResult("depth_m", "value", Double.valueOf(1.5));  // must be an object
//        bm.setVerbose(true);
//        bm.addResult("depth_m", "units", "Meters", true, true); // changed=t and forVerbose=t
//        bm.addResult("depth_m", "sample_time", Long.valueOf(bm.tsValue()) );
//        bm.addError("lollipop", BrokerError.E_UNSUPPORTED_SUB_PARAM);        
//        bm.addResult("testing mixed format", "it works");
////        bm.addError(BrokerError.E_UPDATES_PARSE);
//        m=bm.toJSONResponse();
//        System.out.println(m.toString(3));
//        System.out.println("");
//
//        // create a notification e.g. subscription
//        // although via the spec we are adding params rather than results, results
//        // make more sense in this context and support the changed and verbose flags
//        bm = new BrokerMessage();
//        bm.setMethod("subscription");
////        bm.addError(BrokerError.E_UPDATES_PARSE);
//        bm.addResult("depth_m", "value", Double.valueOf(1.5));  // must be an object
//        bm.setVerbose(true);
//        bm.addResult("depth_m", "units", "Meters", true, true); // changed=t and forVerbose=t
//        bm.addResult("depth_m", "sample_time", Long.valueOf(bm.tsValue()) );
//        m=bm.toJSONNotification();
//        System.out.println(m.toString(3));
//        System.out.println("");
//        
//    }


    private HashMap<String, Object> mResults = new HashMap<String, Object>();   // map of param names and results
    private Iterator<Map.Entry<String, Object>> mIter = mResults.entrySet().iterator(); // Iterator over the result HashMap
    
    private HashMap<String, Boolean> mChanged = new HashMap<String, Boolean>(); // map of param names and whether value has changed.
    
    private BrokerError mError;     // BrokerError object for this result
    
    private String mMethod;         // Requested JSON method
    public void setMethod(String method) { mMethod = method; }
    
    private boolean mVerbose;       // Determines whether short (false) or long (true) responses are returned.
    public void setVerbose(boolean verbose) { mVerbose = verbose; }
       
    private boolean mHasMajorError; // no parameter value can be returned; no JSON message ID will be returned
    public boolean hasMajorError() { return mHasMajorError; }
    
    private boolean mHasMinorError; // only individual parameter values affected; JSON message ID will be returned
        
    private int mID = -1;            // JSON message ID of the reply. Should match the message ID of the request.
    public void setId(int id) { mID = id; }

    private static final boolean DAYLIGHT_NAME = false; // daylight or standard timezone name in reply (e.g., EST vs. EDT)

    
    /**
     * Empty constructor
     */
    public BrokerMessage() {
        this("");
    }

    /**
     * Constructor given method default values of verbose=t
     * @param methodString 
     */
    public BrokerMessage(String methodString) {
        this(methodString, true);
    }

    /**
     * Constructor populates member variables with parameters given
     * @param method
     * @param verbose
     */
    public BrokerMessage(String method, boolean verbose) {
        mMethod = method;
        mVerbose = verbose;
        mHasMajorError = false;
        mHasMinorError = false;
    }

    
    /**
     * Adds a single result object to generate the simplest form of a JSON reply: 
     * {"result": result, ... }
     * Can only be called once to generate a single result.
     * 
     * @param result    the result object to add
     * @param changed   true if data have changed
     * @throws Exception    if a result already exists
     */
    public void addResult(Object result, boolean changed) throws Exception {
        if (mResults.size() >= 1) {
            throw new Exception("Can't add keyless result with existing results.");
        }
        mResults.put("result", result);
        mChanged.put("result", changed);
    }
    
    /**
     * Defaults changed to true
     * 
     * @see #addResult(Object result, boolean changed)
     * 
     * @param result
     * @throws Exception 
     */
    public void addResult(Object result) throws Exception {
        addResult(result, true);
    }
    
    /**
     * Uses structures built in addResult and defaults changed to true (won't be used in a request)
     * 
     * @see #addResult(Object result, boolean changed)
     * 
     * @param param
     * @throws Exception 
     */
    public void addParam(Object param) throws Exception {
        addResult(param, true);
    }

    
    /**
     * Adds a new key-value pair to the result HashMap and updates mChanged HashMap
     * to indicate if the value has changed.  Will generate messages of the form: 
     * {"result": {key:value, key:value, ...} ... } Can be called repeatedly to 
     * add more results.
     * 
     * @param key     associated with this result
     * @param result    the result
     * @param changed   indicates changed data
     */
    public void addResult(String key, Object result, boolean changed) {
        mResults.put(key, result);
        mChanged.put(key, changed);
    }

    /**
     * addResult assumes the parameter value has changed if no boolean is provided
     * as a parameter.
     * 
     * @see #addResult(String key, Object result, boolean changed)
     * 
     * @param key
     * @param result 
     */
    public void addResult(String key, Object result) {
        addResult(key, result, true);
    }

    /**
     * Uses structures built in addResult and defaults changed to true (won't be used in a request)
     * 
     * @see #addResult(String key, Object result, boolean changed)
     * 
     * @param key
     * @param param 
     */
    public void addParam(String key, Object param) {
        addResult(key, param, true);
    }
    
    
    /**
     * Adds results containing nested objects.  These will take on the form: 
     * {"result": {key:{subkey:value, subkey:value, ...}, key:{...}, ...} ... }
     * Can be called repeatedly to add new keys or add new subkeys to existing keys.
     * 
     * @param key
     * @param subkey
     * @param result
     * @param changed
     * @param forVerbose    indicates that this subkey will only be used if mVerbose=t
     */
    public void addResult(String key, String subkey, Object result, boolean changed, boolean forVerbose) throws Exception {
        HashMap<String, Object> nestMap;
        
        // check to see if key exists
        if (mResults.containsKey(key)) {
            if ( !(mResults.get(key) instanceof HashMap) ) {
                throw new Exception("Key already exists and is not a HashMap.");
            } else {
                // if key exists, get hashmap
                nestMap = (HashMap<String, Object>) mResults.get(key);
                mChanged.put(key, mChanged.get(key) | changed); // or the changed value
            }
        } else {
            // if not, make hashmap and add key:hashmap to mResults
            nestMap = new HashMap<String, Object>();
            mResults.put(key, nestMap);
            mChanged.put(key, changed);     // set the changed value
        }
        
        // if forVerbose, append "VERBO$E" to subkey
        if (forVerbose) {
            subkey = subkey + "VERBO$E";
        }
        
        // add subkey:result to hashmap (verify that this updates the hashmap stored in mResults)
        nestMap.put(subkey, result);
    }
    
    /**
     * Defaults forVerbose to false
     * 
     * @see #addResult(String key, String subkey, Object result, boolean changed, boolean forVerbose)
     * 
     * @param key
     * @param subkey
     * @param result
     * @param changed
     * @throws Exception if key already exists and is not a HashMap.
     */
    public void addResult(String key, String subkey, Object result, boolean changed) throws Exception {
         addResult(key, subkey, result, changed, false);
    }    

    /**
     * Defaults forVerbose to false and changed to true
     * 
     * @see #addResult(String key, String subkey, Object result, boolean changed, boolean forVerbose)
     * 
     * @param key
     * @param subkey
     * @param result
     * @throws Exception if key already exists and is not a HashMap.
     */
    public void addResult(String key, String subkey, Object result) throws Exception {
         addResult(key, subkey, result, true, false);
    }    
        
    /**
     * Uses structures built in addResult and defaults forVerbose to false and 
     * changed to true (won't be used in a request)
     * 
     * @see #addResult(String key, String subkey, Object result, boolean changed, boolean forVerbose)
     * 
     * @param key
     * @param subkey
     * @param param
     * @throws Exception if key already exists and is not a HashMap.
     */
    public void addParam(String key, String subkey, Object param) throws Exception {
         addResult(key, subkey, param, true, false);
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
     * 
     * @return true if any parameter has changed, or any error has been recorded
     */
    public boolean hasNew() {
        return (mChanged.containsValue(true) || mHasMajorError || mHasMinorError);
    }


    
    /**
     * Parse current time value into the appropriate format.
     */
    public static long tsValue(long t) {
        SimpleDateFormat formatter = new SimpleDateFormat("yyyyMMddHHmmssSS");
        String timeStr = formatter.format(new Date(t));
        return Long.parseLong(timeStr);
    }
    /**
     * uses current time
     */
    public static long tsValue() {
        return (tsValue(System.currentTimeMillis()));
    }

    
    
    /**
     * toJSONRequest creates a request message
     * A Request object will consist of "jsonrpc":"2.0", "method" : a single method string,
     * "params" : parameters which come from an object or array, and "id" : an id
     * 
     * Internally this will modify a JSONResponse by adding a method, and changing "result"
     * to "params".
     * 
     * @return  JSONObject of the request
     * @throws JSONException
     * @throws Exception 
     */
    public JSONObject toJSONRequest() throws JSONException, Exception {
        JSONObject Request = toJSONResponse();
        Request.put("method", mMethod);
        if (Request.has("result")) {
            Request.put("params", Request.get("result"));
            Request.remove("result");
        }
        return Request;
    }
        
    /**
     * toJSONNotification creates a notification message
     * A notification is a request without an ID
     * 
     * @return  JSONObject of the notification
     * @throws JSONException
     * @throws Exception 
     */
    public JSONObject toJSONNotification() throws JSONException, Exception {
        JSONObject Notification = toJSONRequest();
        Notification.remove("id");
        return Notification;
    }
    
    /**
     * toJSONResponse creates a response message
     * A response object will consist of "jsonrpc":"2.0", 
     * "result" : any value or array or object (unless error),
     * "error" : an error object, and "id" : an id
     * 
     * Internally this will add the json version, add the id, 
     * if a (major) error exists add it and return, else, check mResults hashmap.
     * If there is a single entry with the key "result" add "result" : value.
     * If there are multiple entries or 1 entry not named "result", add all of the
     * key:value pairs as an object.  Values can be objects themselves.
     * 
     * Methods needed include:
     * addResult(object) to add "result":object.
     * addResult(key string, object) to add K:V pairs.  Multiple calls add more.
     * addResult(key string, subkey, value, changed, false) adds a hashmap to key
     * addResult(key string, subkey, value, changed, true) adds a hashmap to key with subkeys appending "VERBO$E"
     */
    public JSONObject toJSONResponse() throws JSONException, Exception {
        JSONObject Response = new JSONObject();
        JSONObject resultObject = new JSONObject();
        JSONObject tsObject;
        Map.Entry<String, Object> entry;
        String key = "";
        Object value = null;

        Response.put("jsonrpc", "2.0");
        if (mID == -1) {
            Response.put("id", JSONObject.NULL);
        } else {
            Response.put("id", mID);
        }

        // Major errors convert (BrokerError) mError to JSON, add and return
        if (mHasMajorError) {
            JSONObject errorObject = mError.toJSONObject(false);
            Response.put("error", errorObject);
            return Response;
        }

        mIter = mResults.entrySet().iterator();
        while (mIter.hasNext()) {            
            entry = mIter.next();
            key = entry.getKey();
            value = entry.getValue();
                
            if (value instanceof BrokerError) {
                resultObject.put(key, ((BrokerError) value).toJSONObject(false));
            } else {
                if (value instanceof Double) {
                    resultObject.put(key, ((Double) value).doubleValue());
                } else if (value instanceof Integer) {
                    resultObject.put(key, ((Integer) value).intValue());
                } else if (value instanceof Long) {
                    resultObject.put(key, ((Long) value).longValue());
                } else if (value instanceof Boolean) {
                    resultObject.put(key, ((Boolean) value).booleanValue());
                } else if (value instanceof String) {
                    resultObject.put(key, ((String) value));
                } else if (value instanceof JSONObject) {
                    resultObject.put(key, (JSONObject) value);
                } else if (value instanceof JSONArray) {
                    resultObject.put(key, (JSONArray) value);
                } else if (value instanceof HashMap) {  // handle nested hashmaps by creating new JSONObjects
                    JSONObject nestedResult = new JSONObject();
                    Iterator<Map.Entry<String, Object>> nestIter = ((HashMap<String, Object>) value).entrySet().iterator();
                    Map.Entry<String, Object> nestEntry;
                    String nestKey = "";
                    Object nestValue = null;
                    
                    while (nestIter.hasNext()) {
                        nestEntry = nestIter.next();
                        nestKey = nestEntry.getKey();
                        nestValue = nestEntry.getValue();
                        
                        if (nestKey.endsWith("VERBO$E")) {
                            if (!mVerbose) {
                                continue;
                            }
                            nestKey = nestKey.substring(0, nestKey.indexOf("VERBO$E")); // truncate
                        }

                        if (nestValue instanceof BrokerError) {
                            nestedResult = ((BrokerError) nestValue).toJSONObject(false);
                        } else {
                            if (nestValue instanceof Double) {
                                nestedResult.put(nestKey, ((Double) nestValue).doubleValue());
                            } else if (nestValue instanceof Integer) {
                                nestedResult.put(nestKey, ((Integer) nestValue).intValue());
                            } else if (nestValue instanceof Long) {
                                nestedResult.put(nestKey, ((Long) nestValue).longValue());
                            } else if (nestValue instanceof Boolean) {
                                nestedResult.put(nestKey, ((Boolean) nestValue).booleanValue());
                            } else if (nestValue instanceof String) {
                                nestedResult.put(nestKey, ((String) nestValue));
                            } else if (nestValue instanceof JSONArray) {
                                nestedResult.put(nestKey, (JSONArray) nestValue);
                            }
                        }
                    }
                    resultObject.put(key, (JSONObject) nestedResult);
                } 
            }
        }

        //  handle single result
        if (mResults.size() == 1 && key.equals("result")) {
            if (value instanceof Double) {
                Response.put(key, ((Double) value).doubleValue());
            } else if (value instanceof Integer) {
                Response.put(key, ((Integer) value).intValue());
            } else if (value instanceof Long) {
                Response.put(key, ((Long) value).longValue());
            } else if (value instanceof Boolean) {
                Response.put(key, ((Boolean) value).booleanValue());
            } else if (value instanceof String) {
                Response.put(key, ((String) value));
            } else {
                throw new Exception("Unsupported type for a single result.");
            }             
        } else {
            Response.put("result", resultObject);
        }
        
        // add a message timeStamp
        if (resultObject.has("message_time")) { // list_data puts it in already
            tsObject = resultObject.getJSONObject("message_time");
        } else {
            tsObject = new JSONObject();
        }
        tsObject.put("value", tsValue());
        if (mVerbose) {
            tsObject.put("units", Calendar.getInstance().getTimeZone().getDisplayName(DAYLIGHT_NAME, TimeZone.SHORT));
        }
        resultObject.put("message_time", tsObject);

        return Response;
    }
    
}
