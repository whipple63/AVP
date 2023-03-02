package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokerError;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.avp.BufferedPreparedStatement;
import edu.unc.ims.instruments.gpsd.*;
import org.json.*;
import java.sql.Timestamp;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import java.text.SimpleDateFormat;
import java.util.Date;


/**
 *
 * @author Tony Whipple
 */
public class GpsdAdapter extends BrokerAdapter implements GpsdListener {

    /** The gpsd device class. */
    private Gpsd mGpsd;

    /** Keep track of connections */
    private boolean mIsConnected = false;

    /** A JSON object to contain the most recent TPV message */
    private JSONObject mJo = null;

    /** Reference to the controlling Broker. */
    private Broker mBroker;

    /** Logger. */
    private Logger mLogger = null;

    /** Period in minutes for recording to database */
    private double mLogPeriod = 10;    // could easily go in config file

    /** Rate at which gps updates data */
    private static final int UPDATE_INTERVAL = 1000;

    /** Time of last data recorded to database and last data collected */
    private long mLastDbTime = 0;
    private long mLastDataTime = 0;

    // The hashmap JSONParameters is declared in BrokerAdapter.  This must exist
    // and be populated with the list of parameters, units, and access types (RO, RW)
    static {
        JSONParameters.put("device", arrayOf("string",  "RO"));
        JSONParameters.put("time",   arrayOf("UTC",     "RO"));
        JSONParameters.put("ept",    arrayOf("seconds", "RO"));
        JSONParameters.put("lat",    arrayOf("degrees", "RO"));
        JSONParameters.put("lon",    arrayOf("degrees", "RO"));
        JSONParameters.put("alt",    arrayOf("meters",  "RO"));
        JSONParameters.put("epx",    arrayOf("meters",  "RO"));
        JSONParameters.put("epy",    arrayOf("meters",  "RO"));
        JSONParameters.put("epv",    arrayOf("meters",  "RO"));
        JSONParameters.put("track",  arrayOf("degrees", "RO"));
        JSONParameters.put("speed",  arrayOf("m/s",     "RO"));
        JSONParameters.put("climb",  arrayOf("m/s",     "RO"));
        JSONParameters.put("epd",    arrayOf("degrees", "RO"));
        JSONParameters.put("eps",    arrayOf("m/s",     "RO"));
        JSONParameters.put("epc",    arrayOf("m/s",     "RO"));
        JSONParameters.put("mode",   arrayOf("numeric", "RO"));
        JSONParameters.put("log_period", arrayOf("minutes", "RW"));
    }
    private static String[] arrayOf(String a, String b) {
        String[] rv = {a, b};
        return rv;
    }

    public GpsdAdapter(final Broker broker) {
        mBroker = broker;
        mLogPeriod = Double.parseDouble(mBroker.getProperties().getProperty("period", "10.0"));
        mLogger = Logger.getLogger();   // construct a new logger
    }

    
    /**
    Connect and initialize.
    Must be the first method called.
    @throws Exception   on error
    */
    public void connect() throws Exception {

        String host = mBroker.getProperties().getProperty("host", "localhost");
        int port = Integer.parseInt(mBroker.getProperties().getProperty("port", "2947"));
        mGpsd = new Gpsd(host, port);
        
        mLogger.log("Connecting to Gpsd @ " + host + ":" + port + "...", "GpsdAdapter",  LogLevel.INFO);
        mGpsd.connectGpsdSocket();
        mIsConnected = true;
        
        // could put these values in the config file
        setSampling(true);  // default to sampling
        setLogging(true);   // default to logging

        mGpsd.addListener(this);
    }

    
    /**
    Clean up any resources prior to object destruction.
    Gives the device a chance to gracefully release any resources it may use
    prior to it's destruction.
    @throws Exception   on error
    */
    public void disconnect() throws Exception {
        // call Gpsd disconnect
        if ( mGpsd != null && isConnected()) {
            mGpsd.disconnectGpsdSocket();
        }

        // get rid of the Gpsd object
        mGpsd = null;
        mIsConnected = false;
    }

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * 
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        if (toOn == true) {
            if (mGpsd.startSampling()) {
                mSampling = SAMPLING_ON;
            }
        } else {
            if (mGpsd.stopSampling()) {
                mSampling = SAMPLING_OFF;
            }
        }
    }
    
    
    /**
    Let the device attempt to reset to a known state.
    @throws Exception   on error
    */
    public void softReset() throws Exception {
        mGpsd.softReset();
    }


    public int getMinSubInterval() {
        return UPDATE_INTERVAL;
    }

    public boolean isConnected() {
        return mIsConnected;
    }


    /* get
     * params contains parameter-old_value pairs.
     * get will check the new value of the parameter and reply with a timestamp,
     * the key, the newValue, and whether it changed from the old value.
     */
    public synchronized void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
        if (mJo == null) {
            reply.addError(BrokerError.E_INVALID_DATA);
            return;
        }
        
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        SimpleDateFormat ISO8601DATEFORMAT = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.S");
        Date obsDateUTC = ISO8601DATEFORMAT.parse(mJo.optString("time").substring(0, 22));
        Long timeVal = BrokerMessage.tsValue( obsDateUTC.getTime()-18000000 );  // convert UTC to EST
        
        while (iter.hasNext()) {
            boolean changed;
            Map.Entry<String, Object> entry = iter.next();
            String ps = entry.getKey();
            if (!checkParameter(ps)) {
                reply.addError(BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }

            if (ps.equals("device")){
                String newValue = mJo.optString(ps);
                if (entry.getValue() == null){
                    changed = true;
                }
                else {
                    changed = entry.getValue() != newValue;
                }
                entry.setValue(String.valueOf(newValue));
                reply.addResult(ps, "value", newValue, changed);
                reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
                reply.addResult(ps, "sample_time", timeVal, changed);
            }
            else if (ps.equals("log_period")) {
                String newValue = String.valueOf(mLogPeriod);
                if (entry.getValue() == null){
                    changed = true;
                }
                else {
                    changed = entry.getValue() != newValue;
                }
                entry.setValue(String.valueOf(newValue));
                reply.addResult(ps, "value", newValue, changed);
                reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
                reply.addResult(ps, "sample_time", timeVal, changed);                
            }
            else {
                Double newValue = mJo.optDouble(ps);

                if (entry.getValue() == null){
                    changed = true;
                }
                else {
                    // NaNs are coming back as strings
                    Double v;
                    if (entry.getValue() instanceof String) { v = Double.NaN; }
                    else { v = (Double) entry.getValue(); }
                    changed = v.doubleValue() != newValue;
                }
                if (newValue.isNaN()) {
                    entry.setValue(newValue.toString());
                    reply.addResult(ps, "value", newValue.toString(), changed);
                    reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
                    reply.addResult(ps, "sample_time", timeVal, changed);
                }
                else {
                    entry.setValue(Double.valueOf(newValue));
                    reply.addResult(ps, "value", newValue, changed);
                    reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
                    reply.addResult(ps, "sample_time", timeVal, changed);
            }
            }
        }
    }

    public void put(HashMap<String, Object> params, BrokerMessage reply) {
        // loop through all requested parameters
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            // get current requested parameter and make sure it's valid
            Map.Entry<String, Object> param = iter.next();
            String ps = param.getKey();
            Object value = param.getValue();
            if (!checkParameter(ps)) {
                // unsupported, skip it
                reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
                continue;
            }
            
            if (JSONParameters.get(ps)[TYPE_INDEX].equals("RO")) {
                reply.addError(ps, BrokerError.E_SET_PARAM_RO);
                continue;
            }
            
            // we have a valid requested parameter, set the value
            if (ps.equals("log_period")) {
                mLogPeriod = (Double) value;
                mLogger.log("Changed log_period to: " + mLogPeriod, this.getClass().getName(), LogLevel.INFO);
                try {
                    reply.addResult(ps, "status", "ok");
                } catch (Exception e) {
                    mLogger.log("Exception setting log period: " + e.getMessage(), this.getClass().getName(), LogLevel.ERROR);
                }
            }
        }
    }


    /**
    Data from Gpsd.
    @param d    data
    */
    public synchronized final void onMeasurement(final GpsData d) {
        long timestamp = System.currentTimeMillis();
        mLastDataTime = timestamp;

        //expects a json array...
        try {
            JSONObject jo = new JSONObject(d.get());
            
            // Once every mLogPeriod save the position (TPV class) to the db
            String cls = jo.getString("class");
            if ( cls.equals("TPV") ) {
                mJo = new JSONObject(d.get());
                if (timestamp >= mLastDbTime+mLogPeriod*60000) {
                    insertData();
                    mLastDbTime = timestamp;
                }
            }
        } catch (JSONException e) {
            System.out.println(e.getMessage());
            e.printStackTrace(System.out);
            System.exit(-1);
        } 
    }

    public Timestamp getLastDataTime() { return new Timestamp(mLastDataTime); }
    public Timestamp getLastDbTime() { return new Timestamp(mLastDbTime); }

    /**
    Insert a row of data into the database.
    */
    protected synchronized final void insertData() {
        if ( !Boolean.parseBoolean(mBroker.getProperties().getProperty("db_enabled", "true")) ||
             ( getLogging() != true ) ) {
            return;
        }
        
        // Sometimes the time doesn't exist yet
        if (!mJo.has("time")) { 
            return;
        }
        SimpleDateFormat ISO8601DATEFORMAT = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.S");
        Date obsDateUTC=null;
        Long timeVal = 0L;
        try {
            obsDateUTC = ISO8601DATEFORMAT.parse(mJo.optString("time").substring(0, 22));
            timeVal = obsDateUTC.getTime()-18000000;  // convert UTC to EST
        } catch (Exception e) {
            e.printStackTrace();
        }

        try {
            // insert a row
            Timestamp ts = new Timestamp(System.currentTimeMillis());

//System.out.println(mJo.getNames(mJo));

            String table_prefix = mBroker.getProperties().getProperty("db_table_prefix", "bp");
            String cmd = "insert into " + table_prefix + "_gps " +
                    "(loc_code, sample_time, period, device, gps_time, lat, lon, " +
                    "alt, epx, epy, epv, track, speed, climb, epd, eps, epc, mode) " +
                    "values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
            BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd);
//            PreparedStatement pstmt = mBroker.getDb().getConnection().prepareStatement(cmd);
            pstmt.setString(1, table_prefix);
            pstmt.setTimestamp(2, ts);
            pstmt.setDouble(3, mLogPeriod);
            if (mJo.optString("device").length() > 24) {
                pstmt.setString(4, mJo.optString("device").substring(0,24));
            }
            else {
                pstmt.setString(4, mJo.optString("device"));
            }
            pstmt.setTimestamp(5, new Timestamp(timeVal));
            pstmt.setDouble( 6, mJo.optDouble("lat"));
            pstmt.setDouble( 7, mJo.optDouble("lon"));
            pstmt.setDouble( 8, mJo.optDouble("alt"));
            pstmt.setDouble( 9, mJo.optDouble("epx"));
            pstmt.setDouble(10, mJo.optDouble("epy"));
            pstmt.setDouble(11, mJo.optDouble("epv"));
            pstmt.setDouble(12, mJo.optDouble("track"));
            pstmt.setDouble(13, mJo.optDouble("speed"));
            pstmt.setDouble(14, mJo.optDouble("climb"));
            pstmt.setDouble(15, mJo.optDouble("epd"));
            pstmt.setDouble(16, mJo.optDouble("eps"));
            pstmt.setDouble(17, mJo.optDouble("epc"));
            pstmt.setInt(18, mJo.getInt("mode"));
//System.out.println(pstmt.toString());
            
            mBroker.getDb().bufferedExecuteUpdate(pstmt);
//            pstmt.executeUpdate();
//            pstmt.close();
        } catch (Exception e) {
            mLogger.log("Insert:" + e.toString(), "GpsdAdapter", LogLevel.ERROR);
        }
    }

}
