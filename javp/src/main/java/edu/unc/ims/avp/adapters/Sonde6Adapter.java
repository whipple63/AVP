package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerError;
import edu.unc.ims.avp.BrokeredDeviceListener;
import edu.unc.ims.avp.BufferedPreparedStatement;
import edu.unc.ims.instruments.ysi.Sonde6;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.ysi.Sonde6Data;
import edu.unc.ims.instruments.ysi.Sonde6Listener;
import org.json.JSONObject;
import org.json.JSONException;
import java.util.Iterator;
import java.util.HashMap;
import java.util.Map;
import java.util.Date;
import java.text.SimpleDateFormat;
import java.text.ParseException;
import java.util.List;
import edu.unc.ims.avp.BrokerMessage;
import java.sql.*;

/**
 * Adapts from BrokeredDevice to the YSI Sonde 6.
 */
public class Sonde6Adapter extends BrokerAdapter implements Sonde6Listener, Runnable {

    private Sonde6 mSonde;
    private Sonde6Data mLastReading = null;
    private Date mLastReadingTimestamp;
    
    /** Time of last data recorded to database and last data collected */
    private long mLastDataTime = 0; // whether it goes to the database or not
    private long mLastDbTime = 0;   // only if it went in the database
    @Override public Timestamp getLastDataTime() { return new Timestamp(mLastDataTime); }
    @Override public Timestamp getLastDbTime() { return new Timestamp(mLastDbTime); }

    
    /**
     * Constructor
     * @param broker 
     */
    public Sonde6Adapter(final Broker broker) {
        mBroker = broker;
        mLoggingMaxTime   = Integer.parseInt(mBroker.getProperties().getProperty("logging_max_time",   "1800")) * 1000;
    }
    
    /**
     * Connect to and initialize the device.
     * 
     * @throws Exception   on error
     */
    @Override
    public final void connect() throws Exception {
        power_on();     // First thing we do is turn on the power

        mSonde = new Sonde6(mBroker, mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_host", "localhost"),
            Integer.parseInt(mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_port")));
        
        mSonde.addListener(this);
        mSonde.connect();
        mRunThread = new Thread(this, this.getClass().getName());
        mRunThread.start();

        setupJSON();
        
        // initialize
        mSonde.deviceReset();
        mSonde.setWipeInterval(0);
        mSonde.setWipesPerEvent(1);
        mSonde.reset();
        
        // could put these values in the config file
        setSampling(false);  // default to not sampling
        setLogging(false);   // default to not logging
    }

    
    /**
     * Free up any resources prior to destruction.
     * @throws Exception   on error.
     */
    @Override
    public final void disconnect() throws Exception {
        if ( mSonde != null && isConnected()) {
            mSonde.disconnect();
        }
        mShutdown = true;
    }

    
    /**
     * Thread to check if the sonde sampling has timed out.
     */
    @Override
    public void run() {
       while (!mShutdown) {
            try {
                // check the timeouts
                if (getLogging() == true) {
                    if (System.currentTimeMillis() > mLoggingStartTime + mLoggingMaxTime ) {
                        mLogger.log("Sonde logging timed out.", this.getClass().getName(), LogLevel.WARN);
                        setLogging(false);
                    }
                }
                Thread.sleep(1000); // not doing anything
            } catch (InterruptedException e) { 
                // do nothing if the sleep is interrupted. 
            }
        }
    }


    @Override
    public int getMinSubInterval() {
        return 1000;
    }


    /**
     * Attempt a soft reset.
     * @throws Exception   on error.
     */
    @Override
    public final void softReset() throws Exception {
        mSonde.reset();
    }

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * 
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        if (toOn == true) {
            if (mSonde.startSampling()) {
                mSampling = SAMPLING_ON;
            }
        } else {
            if (mSonde.stopSampling()) {
                mSampling = SAMPLING_OFF;
            }
        }
    }
    

    /**
     * Handles method calls from the control port (in JSON RPC) that are specific
     * to this adapter.
     * 
     * @param method
     * @param request
     * @param listener
     * @throws Exception 
     */
    @Override
    public void extendedMethod(String method, JSONObject request, BrokeredDeviceListener listener) throws Exception {
        JSONObject params;
        BrokerMessage reply = new BrokerMessage(method, true);
        
        try {
            reply.setId(request.getInt("id"));
            reply.setMethod(method);
            
            if(method.equals("wipe")) {
                if (!getSampling()) {
                    mLogger.log("Wiping start", this.getClass().getName(),  LogLevel.DEBUG);
                    mSonde.wipe();
                    reply.addResult("OK");
                } else {
                    reply.addError(BrokerError.E_INSTRUMENT_BUSY);
                }
                
            } else if(method.equals("start_sampling")) {
                setSampling(true);
                reply.addResult("OK");
                
            } else if(method.equals("stop_sampling")) {
                setSampling(false);
                reply.addResult("OK");
                
            } else if(method.equals("start_logging")) {
                if (request.has("params")) {
                    params = request.getJSONObject("params");
                    if(params.has("cast_number")) {
                        mCastNumber = params.getInt("cast_number");
                    } else {
                        mCastNumber = 1;
                    }
                } else {
                    mCastNumber = 1;
                }
                mLoggingStartTime = System.currentTimeMillis();
                setLogging(true);
                reply.addResult("OK");
                
            } else if(method.equals("stop_logging")) {
                setLogging(false);
                reply.addResult("OK");
                
            } else if(method.equals("calibratePressure")) {
                if (!getSampling()) {
                    mSonde.calibratePressure();
                    reply.addResult("OK");
                } else {
                    reply.addError(BrokerError.E_INSTRUMENT_BUSY);
                }
            }
            
        } catch(Exception e) {
            mLogger.log("Exception in sonde extended method: " + e.getMessage(), 
                    this.getClass().getName(), LogLevel.ERROR);
            reply.addError(BrokerError.E_EXCEPTION, e.getMessage());
        }
        
        // Send the response back to the listener
        try {
            listener.onData(reply.toJSONResponse());
        } catch (JSONException e) {
            mLogger.log("JSON Exception in sonde calling onData: " + e.getMessage(), 
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }

    
    /**
     * Get a (subscribe-able) parameter value and return it in a JSON reply 
     * 
     * @param params
     * @param reply
     * @throws Exception 
     */
    @Override
    public void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
        Long timeVal;    // time to use for the returned data

        // loop through all requested parameters
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            boolean changed;

            // get current requested parameter and make sure it's valid
            Map.Entry<String, Object> entry = iter.next();
            String ps = entry.getKey();
            if (!checkParameter(ps)) {
                // unsupported, skip it
                reply.addError(BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }

            // we have a valid requested parameter, grab the value
            // check first for non-runtime values
            Object newValue;
            if (ps.equals("filter")) { newValue = mSonde.getFilter();             timeVal = mSonde.getConnectTime(); }
            else if (ps.equals("filter_tc"))  { newValue = mSonde.getFilterTC();  timeVal = mSonde.getConnectTime(); }
            else if (ps.equals("sonde_ID"))   { newValue = mSonde.getSondeID();   timeVal = mSonde.getConnectTime(); }
            else if (ps.equals("sonde_SN"))   { newValue = mSonde.getSondeSN();   timeVal = mSonde.getConnectTime(); }
            else if (ps.equals("wipes_left")) { newValue = mSonde.getWipesLeft(); timeVal = System.currentTimeMillis(); }
            else if (ps.equals("sampling"))   { newValue = getSampling();         timeVal = System.currentTimeMillis(); }
            else if (ps.equals("logging"))    { newValue = getLogging();          timeVal = System.currentTimeMillis(); }
            else if (mLastReading == null) {  reply.addError(ps, BrokerError.E_INVALID_DATA); return; }
                else {
                    if (ps.startsWith("time") ||  ps.startsWith("date")) { newValue = mLastReading.get(ps); }
                    else { newValue = mLastReading.getDouble(ps); }
                    timeVal = mLastDataTime;
                }

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
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(timeVal), changed);
        }
    }

    
    /**
     * Set a value as requested via a JSON RPC message on the port
     * 
     * @param params
     * @param reply 
     */
    @Override
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
            if (ps.equals("XXX")) {
                
            }
        
        }
    }

    
    @Override
    public boolean isConnected() {
        if (mSonde != null) {
            return mSonde.isConnected();
        } else {
            return false;
        }
    }

    
    /**
     * Called by the instrument each time it receives data.
     * @param d    data
     */
    @Override
    public final void onMeasurement(final Sonde6Data d) {
        mLastDataTime = System.currentTimeMillis();
        
        // save the reading and check if it is as expected
        mLastReading = d;
        if((d.get("date_mdy")==null) ||
           (d.get("time_hms")==null) ||
           (d.get("temp_C") == null) ||
           (d.get("spcond_mScm") == null) ||
           (d.get("sal_ppt") == null) ||
           ( (d.get("do_mgL") == null) && (d.get("odo_mgL") == null) ) ||
           (d.get("depth_m") == null) ||
           ( (d.get("turbidPl_NTU") == null) && (d.get("turbid_NTU") == null) )  ||
           (d.get("chl_ugL") == null)) {
            mLogger.log("Data from Sonde does not contain expected fields.  Data:" + mLastReading.toString(),
                this.getClass().getName(),  LogLevel.DEBUG);
            return;
        }
        
        try {
            SimpleDateFormat format = new SimpleDateFormat("M/d/yy H:m:s");
            Date tmpDate =  format.parse(d.get("date_mdy") + " " + d.get("time_hms"));
            if (tmpDate == mLastReadingTimestamp) {
                tmpDate.setTime( tmpDate.getTime() + 500 ); // add 500 ms to handle duplicate time stamps
            }
            mLastReadingTimestamp = tmpDate;
        } catch (ParseException pe) {
            mLogger.log("Error parsing sonde date: " + pe.getMessage(), 
                    this.getClass().getName(), LogLevel.ERROR);
            return;
        }
        
        insertData();   // insert the data into the database
    }
                
            
    /**
     * Insert a row of data into the database if enabled and logging.
     */
    protected final void insertData() {
        if ( !Boolean.parseBoolean(mBroker.getProperties().getProperty("db_enabled", "true")) ||
             ( getLogging() != true ) ) {
            return;
        }

        Timestamp ts = new Timestamp(mLastReadingTimestamp.getTime());
        String tablePrefix = mBroker.getProperties().getProperty("db_table_prefix", "bp");
        String cmd = "insert into " + tablePrefix + "_sonde "
          + "(cast_no, loc_code, sample_time, tempc, spcond, salppt, "
          + "dissolved_o2, optical_do, depth_m, turbid, chl, ph) "
          + "values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd);
        pstmt.setInt(1, new Integer(mCastNumber));
        pstmt.setString(2, tablePrefix);
        pstmt.setTimestamp(3, ts);
        pstmt.setDouble(4, mLastReading.getDouble("temp_C"));
        pstmt.setDouble(5, mLastReading.getDouble("spcond_mScm"));
        pstmt.setDouble(6, mLastReading.getDouble("sal_ppt"));

        // allow for either type of DO sensor
        if (mLastReading.get("do_mgL") != null) {
            pstmt.setDouble(7, mLastReading.getDouble("do_mgL"));
            pstmt.setBoolean(8, false);
        }
        if (mLastReading.get("odo_mgL") != null) {
            pstmt.setDouble(7, mLastReading.getDouble("odo_mgL"));
            pstmt.setBoolean(8, true);
        }

        pstmt.setDouble(9, mLastReading.getDouble("depth_m"));

        // allow for either type of turbidity sensor
        if (mLastReading.get("turbidPl_NTU") != null) {
            pstmt.setDouble(10, mLastReading.getDouble("turbidPl_NTU"));
        }
        if (mLastReading.get("turbid_NTU") != null) {
            pstmt.setDouble(10, mLastReading.getDouble("turbid_NTU"));
        }

        pstmt.setDouble(11, mLastReading.getDouble("chl_ugL"));

        // might or might not have ph
        if (mLastReading.get("ph") != null) {            
            pstmt.setDouble(12, mLastReading.getDouble("ph"));
        } else {
            pstmt.setDouble(12, 0.0);
        }
            
        try {
            mBroker.getDb().bufferedExecuteUpdate(pstmt);
            mLastDbTime = mLastReadingTimestamp.getTime();
        } catch (SQLException e) {
            mLogger.log("SQL Exception trying to insert data from sonde: " + e.getMessage(), 
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }


    static final int FIELD_INDEX = 2;

    private static String[] arrayOf(String a, String b, String c) {
        String[] rv = {a, b, c};
        return rv;
    }

    private void setupJSON() {
        List<Sonde6Data.ElementDesc> d = Sonde6Data.getAvailableDataElements();
        Iterator<Sonde6Data.ElementDesc> i = d.iterator();
        while(i.hasNext()) {
            Sonde6Data.ElementDesc e = i.next();
            JSONParameters.put(e.mShortName, arrayOf(e.mUnits, "RO", e.mShortName));
        }
        JSONParameters.put("sampling", arrayOf("boolean", "RO", "sampling"));
        JSONParameters.put("logging", arrayOf("boolean", "RO", "logging"));

        // add the non-runtime values next
        JSONParameters.put("filter", arrayOf("boolean", "RW", "filter"));
        JSONParameters.put("filter_tc", arrayOf("double", "RW", "filter_tc"));
        JSONParameters.put("wipes_left", arrayOf("Integer", "RO", "wipes_left"));
        JSONParameters.put("sonde_ID", arrayOf("String", "RW", "sonde_ID"));
        JSONParameters.put("sonde_SN", arrayOf("String", "RO", "sonde_SN"));
    }

    static {
        extendedMethods.put("wipe", Boolean.TRUE);
        extendedMethods.put("calibratePressure", Boolean.TRUE);
        extendedMethods.put("start_sampling", Boolean.TRUE);
        extendedMethods.put("stop_sampling", Boolean.TRUE);
        extendedMethods.put("start_logging", Boolean.TRUE);
        extendedMethods.put("stop_logging", Boolean.TRUE);
    }

    private Thread mRunThread;
    private boolean mShutdown = false;
    
    private int mCastNumber = 1;
//    private boolean mLogging = false;
    private long mLoggingStartTime  = 0;
    private int  mLoggingMaxTime    = 1800 * 1000;
    private Broker mBroker;
}
