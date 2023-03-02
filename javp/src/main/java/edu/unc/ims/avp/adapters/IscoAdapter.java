package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokeredDeviceListener;
import edu.unc.ims.avp.BufferedPreparedStatement;
import edu.unc.ims.instruments.isco.*;
import org.json.JSONObject;
import org.json.JSONException;
import edu.unc.ims.avp.Logger.LogLevel;
import java.sql.Timestamp;
import edu.unc.ims.instruments.TimeoutException;
import edu.unc.ims.avp.BrokerError;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;

/**
Adapts from BrokeredDevice.
 */
public class IscoAdapter extends BrokerAdapter implements IscoListener {
    
    private Isco mIsco;         /** The ISCO device class. */
    private Broker mBroker;    /** Reference to the controlling Broker. */
    private static final int MIN_SUB_INTERVAL = 2000;
    private static final int DEFAULT_SAMPLE_VOLUME = 1000;
    private int mCastNumber;    /** Which cast number is this sample associated with */
    private Double mSampleDepth;    /** At what depth was this sample taken */
    /** Time of last data recorded to database and last data collected */
    private long mLastDbTime = 0;
    private long mLastDataTime = 0;

    public IscoAdapter(final Broker broker) {
        mBroker = broker;
    }
    
    /**
    Initialize the device.
    @throws Exception   on error
     */
    public final void connect() throws Exception {

        // First thing we do is check the power (we won't turn it on or off because the
        // Isco power controls the water direction valve (Isco off == water goes to LISST)
        if (getPower()==POWER_OFF) {
            mLogger.log("The power port is OFF, aborting connect attempt",
                this.getClass().getName(), LogLevel.WARN);
             throw new Exception("ISCO Power not on - aborting connect");
        } else {
            mLogger.log("The power port is ON", this.getClass().getName(), LogLevel.INFO);
        }

        String host = mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_host", "localhost");
        int port = Integer.parseInt(mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_port", "55235"));
        mIsco = new Isco(host, port);
        
        mLogger.log("Connecting to Isco @ " + host + ":" + port + "...", this.getClass().getName(), LogLevel.INFO);
        mIsco.connect();
        mLogger.log("Connected to Isco @ " + host + ":" + port + "...", this.getClass().getName(), LogLevel.INFO);

        mIsco.addListener(this);
        
        // could put these values in the config file
        setSampling(true);  // default to sampling
        setLogging(true);   // default to logging
    }

    
    /**
    Free up any resources prior to destruction.
    @throws Exception   on error.
     */
    public final void disconnect() throws Exception {
        if ( mIsco != null && isConnected()) {
            mIsco.disconnect();
        }
    }

    public int getMinSubInterval() {
        return MIN_SUB_INTERVAL;
    }


    /**
    Attempt a soft reset.
    @throws Exception   on error.
     */
    public final void softReset() throws Exception {
        mIsco.softReset();
    }

    public final boolean isConnected() {
        if (mIsco != null) {
            return mIsco.isConnected();
        } else { return false; }
    }

    /**
     * This is called to update and return the parameters.  In the case of the ISCO
     * this will request the status of all parameters and update them all.
     *
     * @param params
     * @param reply
     */
    public void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {

        try {
            synchronized (this) { mIsco.pollStatus(); }     // update the data
        } catch (TimeoutException e) {
            mLogger.log("Get: " + e.toString() + params.toString(), this.getClass().getName(), LogLevel.ERROR);
            reply.addError(BrokerError.E_CONNECTION);
            return;
        }

        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            boolean changed;
            Map.Entry<String, Object> entry = iter.next();
            String ps = entry.getKey();
            if (!checkParameter(ps)) {
                reply.addError(BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }
            Object newValue = null;
            if (ps.equals("hardware_revision")){ newValue = mIsco.mIscoData.getHardwareRevision(); }
            if (ps.equals("software_revision")){ newValue = mIsco.mIscoData.getSoftwareRevision(); }
            if (ps.equals("model"))            { newValue = mIsco.mIscoData.getModel();            }
            if (ps.equals("ID"))               { newValue = mIsco.mIscoData.getID();               }
            if (ps.equals("isco_time"))        { newValue = mIsco.mIscoData.getIscoStatusTime();   }
            if (ps.equals("isco_status"))      { newValue = mIsco.mIscoData.getIscoStatus();       }
            if (ps.equals("isco_sample_time")) { newValue = mIsco.mIscoData.getIscoSampleTime();   }
            if (ps.equals("bottle_num"))       { newValue = mIsco.mIscoData.getBottleNum();        }
            if (ps.equals("sample_volume"))    { newValue = mIsco.mIscoData.getSampleVolume();     }
            if (ps.equals("sample_status"))    { newValue = mIsco.mIscoData.getSampleStatus();     }
            if (entry.getValue() == null){
                changed = true;
            }
            else {
                if (newValue instanceof Double) { changed = !newValue.equals( (Double) entry.getValue() ); }
                else if (newValue instanceof Integer) { changed = !newValue.equals( (Integer) entry.getValue() ); }
                else if (newValue instanceof Boolean) { changed = !newValue.equals( (Boolean) entry.getValue() ); }
                else { changed = !newValue.equals(entry.getValue()); }
            }
            entry.setValue(newValue);
            reply.addResult(ps, "value", newValue, changed);
            reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(mIsco.mIscoData.getStatusTimestamp()), changed);
        }
    }

    /**
    Adapter method to set parameters on the instrument. An Iterator processes
    the parameter HashMap (of parameter names and values). For each parameter,
    putSingle is called with the parameter, value, and BrokerReply as arguments.
    The BrokerReply is updated with errors if they occur.
    @param params A HashMap of parameters and their requested values.
    @param reply The running BrokerReply for this JSON request.
     */
    public synchronized void put(HashMap<String, Object> params, BrokerMessage reply) {
        // there are no writable values
    }

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * Does nothing for an Isco.
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        mSampling = SAMPLING_ON;
    }
    
    
    /**
    allows methods with non-standard JSON reply formats to be serviced.

    @param method String representation of the method.
    @param request The original JSON request.
     */
    public void extendedMethod(String method, JSONObject request, BrokeredDeviceListener listener) throws Exception {
//        JSONObject response = new JSONObject();
        BrokerMessage reply = new BrokerMessage(method, true);
        JSONObject params;
        int bnum;   // bottle number
        int svol;   // sample volume
        try {
            reply.setId(request.getInt("id"));
            reply.setMethod(method);
//            response.put("id", request.get("id"));
            if (isConnected()) {    // make sure we are connected
                if(method.equals("take_sample")) {
                    mLogger.log("Beginning ISCO sample", this.getClass().getName(), LogLevel.DEBUG);
                    if (request.has("params")) {
                        params = request.getJSONObject("params");

                        if(params.has("bottle_num")) { bnum = params.getInt("bottle_num");
                        } else { bnum = mIsco.mIscoData.getBottleNum() + 1; }
                        if(params.has("sample_volume")) { svol = params.getInt("sample_volume");
                        } else { svol = DEFAULT_SAMPLE_VOLUME; }
                        if(params.has("cast_number")) { mCastNumber = params.getInt("cast_number");
                        } else { mCastNumber = 1; }
                        if(params.has("sample_depth")) { mSampleDepth = params.getDouble("sample_depth");
                        } else { mSampleDepth = 0.0; }
                    } else { // really shoouldn't get here but values given for testing
                        bnum = mIsco.mIscoData.getBottleNum() + 1;
                        svol = DEFAULT_SAMPLE_VOLUME;
                        mCastNumber = 1;
                        mSampleDepth = 0.0;
                    }
                    if ((bnum > 0 && bnum <= 24) && (svol > 0 && svol <= 1000)) {
                        try {
                            mIsco.takeSample(bnum, svol);
                        } catch (TimeoutException e) {
                            reply.addError(BrokerError.E_CONNECTION);
                        }
                    }
                    // we could hang here until the sample is over
                    mLogger.log("ISCO sample under way", this.getClass().getName(), LogLevel.DEBUG);
                    reply.addResult("OK");   // will translate to "result" "OK"
//                    response.put("result", "OK");
                } else if(method.equals("sampler_on")) {
                    mIsco.softPowerSampler();
                    reply.addResult("OK");   // will translate to "result" "OK"
//                    response.put("result", "OK");
                }
            } else {
                reply.addError(BrokerError.E_CONNECTION);
            }
        } catch(TimeoutException e) {
            reply.addError(BrokerError.E_CONNECTION);
        } catch(Exception e) {
            e.printStackTrace();
            try {
                reply.addResult( e.toString());
//                response.put("result", e.toString());
            } catch(Exception ee) {
                ee.printStackTrace();
            }
        }
        try {
            listener.onData(reply.toJSONResponse());
        } catch (JSONException e) {
            // TODO: log
        }
    }

    public void extendedReply(String method, HashMap<String, Object> results,
            HashMap<String, Boolean> changed) {
        // TODO: log reply to unknown method requested
    }

    /**
     * Called when isco finishes its collection.
     * @param d
     */
    public final void onMeasurement(final IscoData d) {
        mLastDataTime = System.currentTimeMillis();
        
        if ( !Boolean.parseBoolean(mBroker.getProperties().getProperty("db_enabled", "true")) ||
             ( getLogging() != true ) ) {
            return;
        }
        
        try {
            // insert a row
            Timestamp ts = new Timestamp(System.currentTimeMillis());

            String table_prefix = mBroker.getProperties().getProperty("db_table_prefix", "bp");
            String cmd = "insert into " + table_prefix + "_isco " +
                    "(cast_no, loc_code, sample_time, bottle_number, sample_depth, sample_volume, " +
                    "sample_status, isco_model, isco_ID, hardware_revision, software_revision) " +
                    "values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
            BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd);
//            PreparedStatement pstmt = mBroker.getDb().getConnection().prepareStatement(cmd);
            pstmt.setInt(1, new Integer(mCastNumber));
            pstmt.setString(2, table_prefix);
            pstmt.setTimestamp(3, ts);
            pstmt.setInt(4, mIsco.mIscoData.getBottleNum());
            pstmt.setDouble(5, mSampleDepth);
            pstmt.setInt(6, mIsco.mIscoData.getSampleVolume());
            pstmt.setInt(7, mIsco.mIscoData.getSampleStatus());
            pstmt.setString(8, mIsco.mIscoData.getModel());
            pstmt.setString(9, mIsco.mIscoData.getID());
            pstmt.setString(10, mIsco.mIscoData.getHardwareRevision());
            pstmt.setString(11, mIsco.mIscoData.getSoftwareRevision());

            mBroker.getDb().bufferedExecuteUpdate(pstmt);
//            pstmt.executeUpdate();
//            pstmt.close();

            mLastDbTime = mLastDataTime;
        } catch (Exception e) {
            mLogger.log("Insert:" + e.toString(), this.getClass().getName(), LogLevel.ERROR);
        }
    }

    public Timestamp getLastDataTime() { return new Timestamp(mLastDataTime); }
    public Timestamp getLastDbTime() { return new Timestamp(mLastDbTime); }


    /**
    Java doesn't seem to allow arrays of constants. This method lets
    us populate constant arrays at initialization.
    @param a element 0
    @param b element 1
    @param c element 2
    @return an array of the three elements.
     */
    private static final String[] arrayOf(String a, String b, String c) {
        String[] rv = {a, b, c};
        return rv;
    }

    static {
        JSONParameters.put("hardware_revision", arrayOf("text",                  "RO", "0"));
        JSONParameters.put("software_revision", arrayOf("text",                  "RO", "1"));
        JSONParameters.put("model",             arrayOf("text",                  "RO", "2"));
        JSONParameters.put("ID",                arrayOf("text",                  "RO", "3"));
        JSONParameters.put("isco_time",         arrayOf("Days since 1-Jan-1900", "RO", "4"));
        JSONParameters.put("isco_status",       arrayOf("Integer",               "RO", "5"));
        JSONParameters.put("isco_sample_time",  arrayOf("Days since 1-Jan-1900", "RO", "6"));
        JSONParameters.put("bottle_num",        arrayOf("Integer",               "RO", "7"));
        JSONParameters.put("sample_volume",     arrayOf("ml",                    "RO", "8"));
        JSONParameters.put("sample_status",     arrayOf("Integer",               "RO", "9"));
    }

}
