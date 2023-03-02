package edu.unc.ims.avp;

import org.json.JSONArray;
import org.json.JSONObject;
import org.json.JSONException;
import edu.unc.ims.avp.adapters.BrokerAdapter;
import java.util.HashMap;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.Map;
import java.util.Calendar;
import java.util.TimeZone;


/**
 * BrokerRequest handles command requests that require knowledge specific to an
 * instrument/adapter such as what data are available.  It is called by customCommand
 * and is passed commands after broker.processRequest determines that it does not
 * handle them.  These methodNeedsToken will not get called if the broker is suspended.
 * <p>
 * After the constructor is called, call execute to process the request.  If the 
 * request is for a subscription, this will start the subscription thread.
 */
public class BrokerRequest {
    
    private BrokerAdapter mAdapter;
    private BrokeredDeviceListener mListener;

    private BrokerSubscription mSubscription = null;

    private JSONObject mRequestObject;
    private int mID;
    
    // enum of methodNeedsToken handled here to be used in the switch statement
    public static enum MethodsHandled {
        status, subscribe, set, power, initialize, list_data,
        unsubscribe, serial_pass, restart, other, unknown
    }
    private MethodsHandled mMethodRequested;

    public static final HashMap<String, Boolean> methodNeedsToken = new HashMap<String, Boolean>();
    static {
        methodNeedsToken.put("status",       Boolean.FALSE);
        methodNeedsToken.put("subscribe",    Boolean.FALSE);
        methodNeedsToken.put("set",          Boolean.TRUE);
        methodNeedsToken.put("power",        Boolean.TRUE);
        methodNeedsToken.put("initialize",   Boolean.TRUE);
        methodNeedsToken.put("list_data",    Boolean.FALSE);
        methodNeedsToken.put("unsubscribe",  Boolean.FALSE);
        methodNeedsToken.put("serial_pass",  Boolean.TRUE);
        methodNeedsToken.put("restart",      Boolean.TRUE);
    }
    /**
     * Check if the given method needs the token to run
     * @param s     name of the method
     * @return      boolean
     */
    public static boolean restrictedMethod(String s) {
        if (methodNeedsToken.get(s) == Boolean.TRUE) {
            return true;
        } else {
            return false;
        }
    }

    
    /**
     * Construct the BrokerRequest object and initialize
     * @param obj       JSONObject containing the request
     * @param adapter   the BrokerAdapter to which we belong
     * @param listener  the class (ControllerClientHandler) to pass the JSON reply back to
     */
    public BrokerRequest(JSONObject obj, BrokerAdapter adapter,  BrokeredDeviceListener listener) {
        mRequestObject = obj;
        mAdapter = adapter;
        mListener = listener;
    }


    /**
     * Process the request and issue a reply back.  If the request isn't handled
     * here, send it to the adapter's instrument-specific extendedMethod routine.
     */
    public void execute() throws Exception {
        BrokerMessage reply = new BrokerMessage();
        JSONObject params = null;
        boolean mustReply;
        String methodString = "";
        
        // Extract the json id and set it into the reply
        try {
            mID = mRequestObject.getInt("id");
            reply.setId(mID);
            mustReply = true;
        } catch (JSONException j) {
            mustReply = false;
        }
        
        // Extract the requested method and set it into the reply
        try {
            methodString = mRequestObject.getString("method");
            mMethodRequested = MethodsHandled.valueOf(methodString);
            reply.setMethod(methodString);
        } catch (JSONException j) {
            reply.addError(BrokerError.E_METHOD_PARSE);
            try {
                mListener.onData(reply.toJSONResponse());
            } catch (JSONException e) {
                Logger.getLogger().log("JSONException caught during BrokerRequest: " + e.getMessage(),
                    this.getClass().getName(),  Logger.LogLevel.WARN);
            }
            return;
        } catch (IllegalArgumentException iae) {
            mMethodRequested = MethodsHandled.other;
        }

        // Handle each possible method
        switch (mMethodRequested) {
            case status:
                if (mAdapter.isConnected()) {
                    params = getParams(reply);
                    status(params, reply);
                } else {
                    reply.addError(BrokerError.E_CONNECTION);
                }
                break;
            case set:
                if (mAdapter.isConnected()) {
                    params = getParams(reply);
                    set(params, reply);
                } else {
                    reply.addError(BrokerError.E_CONNECTION);
                }
                break;
            case subscribe:
                params = getParams(reply);
                subscribe(params, reply);
                break;
            case unsubscribe:
                params = getParams(reply);
                unsubscribe(params, reply);
                break;
            case power:
                params = getParams(reply);
                power(params, reply);
                break;
            case initialize:
                // TODO: initialize();
                break;
            case list_data:
                list_data(reply);
                break;
            case serial_pass:
                // TODO: serial_pass(params);
                break;
            case restart:
                // TODO: restart();
                break;
            default:
                mustReply = false;
                mAdapter.extendedMethod(methodString, mRequestObject, mListener);
        }
        
        // Send the reply back to the listener
        if (mustReply) {
            try {
                mListener.onData(reply.toJSONResponse());
            } catch (JSONException e) {
                Logger.getLogger().log("JSONException caught during BrokerRequest: " + e.getMessage(),
                    this.getClass().getName(),  Logger.LogLevel.WARN);
            }
        }
        
        // If this is a subscription, start the thread
        if ((mSubscription != null) && !reply.hasMajorError() && (mMethodRequested == MethodsHandled.subscribe)) {
            new Thread(mSubscription, "subscription-"+params.toString()).start();
        }
    }

    // Get the parameters from the request and catch possible JSONExceptions
    private JSONObject getParams(BrokerMessage reply) {
        JSONObject p=null;
        try {
            p = mRequestObject.getJSONObject("params");
        } catch (JSONException j) {
            reply.addError(BrokerError.E_PARAMS_PARSE);
        }
        return p;
    }

    
    /**
     * Set a value of one of the possible broker parameters (if settable)
     * @param jp        JSON params
     * @param reply     to send back to listener
     */
    private void set(JSONObject jp, BrokerMessage reply) throws Exception {
        String[] keys = JSONObject.getNames(jp);
        HashMap<String, Object> params = new HashMap<String, Object>();
        for (int i = 0; i < keys.length; i++) {
            String ps = keys[i];
            if (mAdapter.checkParameter(ps)) {
                try {
                    if (BrokerAdapter.JSONParameters.get(ps)[0].equalsIgnoreCase("boolean")) {
                        params.put(keys[i], jp.getBoolean(keys[i]));
                    } else if (BrokerAdapter.JSONParameters.get(ps)[0].equalsIgnoreCase("string") ||
                            BrokerAdapter.JSONParameters.get(ps)[0].equalsIgnoreCase("text")) {
                        params.put(keys[i], jp.getString(keys[i]));
                    } else {    // assume double
                        params.put(keys[i], jp.getDouble(keys[i]));
                    }
                } catch (JSONException j) {
                    reply.addError(ps, BrokerError.E_PARAMS_PARSE);
                }
            } else {
                reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
            }
        }
        mAdapter.put(params, reply);
    }

    
    private void power(JSONObject jp, BrokerMessage reply) {
        try {
            String ps = jp.getString("status");
            mAdapter.power(ps, reply);
        } catch (JSONException je) {
            reply.addError(BrokerError.E_PARAMS_PARSE);
        }
    }

    
    private void status(JSONObject jp, BrokerMessage reply) throws Exception {
        HashMap<String, Object> params = new HashMap<String, Object>();
        try {
            JSONArray data = jp.getJSONArray("data");
            String style = jp.optString("style");
            if (style.isEmpty() || style.equals("verbose")) {
                reply.setVerbose(true);
            } else if (style.equals("terse")) {
                reply.setVerbose(false);
            } else {
                reply.addError(BrokerError.E_STYLE_PARSE);
                return;
            }
            for (int i = 0; i < data.length(); i++) {
                /* JSONExceptions will be caught and reported as parse errors. */
                String ps = data.getString(i);
                if (mAdapter.checkParameter(ps)) {
                    params.put(ps, null);
                    Logger.getLogger().log("Adding parameter " + ps + " from request.", this.getClass().getName(),
                            Logger.LogLevel.DEBUG);
                } else {
                    reply.addError(ps, BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                    Logger.getLogger().log("Unsupported status parameter: " + ps, this.getClass().getName(),
                            Logger.LogLevel.DEBUG);
                }
            }
        } catch (JSONException j) {
            reply.addError(BrokerError.E_PARAMS_PARSE);
            Logger.getLogger().log("JSONException while parsing subscription request: " + jp.toString(), this.getClass().getName(),
                    Logger.LogLevel.DEBUG);
            return;
        }
        mAdapter.get(params, reply);
    }

    
    /**
     * Subscribe to a parameter at a certain rate, or upon new updates, or
     * upon data change.  
     * 
     * @param jp        JSON params
     * @param reply     to send to the listener
     */
    private void subscribe(JSONObject jp, BrokerMessage reply) throws Exception {
        long minInterval = 0;
        long maxInterval = 0;
        boolean onNew;
        boolean minSet = false;
        boolean maxSet = false;
        JSONArray data;
        boolean verbose = true;
        
        // get what data to subscribe to
        try {
            data = jp.getJSONArray("data");
        } catch (JSONException j) {
            reply.addError(BrokerError.E_PARAMS_PARSE);
            return;
        }
        
        // if there get the minimum update interval in ms
        try {
            minInterval = jp.getLong("min_update_ms");
            minSet = true;
        } catch (JSONException e) {
            // okay to ignore
        }
        
        // if there get the maximum update interval in ms
        try {
            maxInterval = jp.getLong("max_update_ms");
            maxSet = true;
        } catch (JSONException e) {
            // okay to ignore
        }

        // If neither min nor max was set, set the min to the minimum subscription
        // interval as determined by the specific adapter code.  Set max based on that value.
        int range = 4;  // mult factor to determine interval range
        if (!minSet && !maxSet) {
            maxInterval = mAdapter.getMinSubInterval() * range;
            minInterval = mAdapter.getMinSubInterval();
        }
        if (!minSet && maxSet) {    // attempt to keep the range
            minInterval = maxInterval / range;
        }
        if (minSet && !maxSet) {    // attempt to keep the range
            maxInterval = minInterval * range;
        }
        // if the minimum or maximum is too small, set it to the minimum
        if (minInterval < mAdapter.getMinSubInterval()) {
            minInterval = mAdapter.getMinSubInterval();
        }
        if (maxInterval < mAdapter.getMinSubInterval()) {
            maxInterval = mAdapter.getMinSubInterval();
        }
        if (minInterval > maxInterval) {
            reply.addError(BrokerError.E_SUB_INTERVAL);
            return;
        }
        // Intervals are set
        reply.addResult("min_update_ms", minInterval);
        reply.addResult("max_update_ms", maxInterval);
        
        // set verbose or terse style
        String style = jp.optString("style");        
        if (style.isEmpty() || style.equals("verbose")) {
            reply.setVerbose(true);
            verbose = true;
        } else if (style.equals("terse")) {
            reply.setVerbose(false);
            verbose = false;
        } else {
            reply.addError(BrokerError.E_STYLE_PARSE);
            return;
        }
        
        // set whether updates should come on new data or on changed data
        String updates = jp.optString("updates");
        if (updates.isEmpty() || updates.equals("on_new")) {
            onNew = true;
        } else if (updates.equals("on_change")) {
            onNew = false;
        } else {
            reply.addError(BrokerError.E_UPDATES_PARSE);
            return;
        }
        
        /* Create a list of parameter strings and pass this list to a
        BrokerSubscription constructor. Add results of this operation to a reply.
        If there are errors, add those to the reply. */
        try {
            ArrayList<String> paramStrings = new ArrayList<String>();
            for (int i = 0; i < data.length(); i++) {
                String ps = data.getString(i); // JSONExceptions will be caught and reported as parse errors
                if (mAdapter.checkParameter(ps)) {
                    paramStrings.add(ps);
                    reply.addResult(ps, "status", "ok");
                } else {
                    reply.addError(ps, BrokerError.E_UNSUPPORTED_SUB_PARAM);
                }
            }
            
            // Construct the new subscription
            if (paramStrings.isEmpty() == false) {      
                mSubscription = new BrokerSubscription(paramStrings, minInterval,
                        maxInterval, onNew, verbose, mAdapter, mListener);
            }
            
        } catch (JSONException j) {
            reply.addError(BrokerError.E_PARAMS_PARSE);
            Logger.getLogger().log("JSONException while parsing subscription request: "
                    + data.toString(), this.getClass().getName(),
                    Logger.LogLevel.INFO);
            return;
        }
    }

    
    private void unsubscribe(JSONObject jp, BrokerMessage reply) throws Exception {
        try {
            JSONArray data = jp.getJSONArray("data");
            for (int i = 0; i < data.length(); i++) {
                /* JSONExceptions will be caught and reported as parse errors. */
                String ps = data.getString(i);
                if (mAdapter.checkParameter(ps)) {
                    if (mAdapter.hasSubscription(ps, mListener)) {
                        mAdapter.dropSubscription(ps, mListener);
                        reply.addResult(ps, "status", "ok");
                    } else {
                        reply.addError(ps, BrokerError.E_SUB_NOT_FOUND);
                    }
                } else {
                    reply.addError(ps, BrokerError.E_UNSUPPORTED_SUB_PARAM);
                }
            }
        } catch (JSONException j) {
            reply.addError(BrokerError.E_PARAMS_PARSE);
            return;
        }
    }
    
    private void list_data(BrokerMessage reply) throws Exception {
            Iterator<Map.Entry<String, String[]>> iter = mAdapter.JSONParameters.entrySet().iterator();
            while (iter.hasNext()) {
                Map.Entry<String, String[]> entry = iter.next();
                String ps = entry.getKey();
                reply.addResult(ps, "units", entry.getValue()[0]);
                reply.addResult(ps, "type", entry.getValue()[1]);
            }
            reply.addResult("message_time", "units", Calendar.getInstance().getTimeZone().getDisplayName(false, TimeZone.SHORT));
            reply.addResult("message_time", "type", "RO");
    }
    
}
