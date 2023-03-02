package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokeredDeviceListener;
import edu.unc.ims.avp.BufferedPreparedStatement;
import edu.unc.ims.instruments.lisst.*;
import org.json.JSONObject;
import org.json.JSONException;
import edu.unc.ims.avp.Logger.LogLevel;
import java.sql.Timestamp;
import java.io.FileInputStream;
import java.io.File;
import edu.unc.ims.instruments.TimeoutException;
import edu.unc.ims.avp.BrokerError;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;

/**
Adapts from BrokeredDevice.
 */
public class LisstAdapter extends BrokerAdapter implements LisstListener {
    
    private Lisst mLisst;      /** The device class. */
    private Broker mBroker;    /** Reference to the controlling Broker. */
    private static final int MIN_SUB_INTERVAL = 6000;
    private int mCastNumber;
    private int mPumpDelay;     /** time in seconds for water to reach lisst from hose intake */
    /** Time of last data recorded to database and last data collected */
    private long mLastDbTime = 0;
    private long mLastDataTime = 0;

    public LisstAdapter(final Broker broker) {
        mBroker = broker;
    }
    
    /**
    Initialize the device.
    @throws Exception   on error
     */
    public final void connect() throws Exception {
        // First thing we do is turn on the power
        if (getPower()==POWER_OFF) {
            power_on();
            Thread.sleep(35000);    // LISST needs about 35 sec to power on and boot
        } else {
            mLogger.log("The power port is already ON", this.getClass().getName(), LogLevel.INFO);
        }

        String host = mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_host", "localhost");
        int port = Integer.parseInt(mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_port", "55236"));
        mLisst = new Lisst(mBroker, host, port);
        
        mLogger.log("Connecting to LISST @ " + host + ":" + port + "...", this.getClass().getName(), LogLevel.INFO);
        mLisst.connect();
        mLogger.log("Connected to Lisst @ " + host + ":" + port + "...", this.getClass().getName(), LogLevel.INFO);

        mLisst.addListener(this);
        
        // could put these values in the config file
        setSampling(false);  // not used for lisst
        setLogging(true);   // default to logging
    }

    /**
    Free up any resources prior to destruction.
    @throws Exception   on error.
     */
    public final void disconnect() throws Exception {
        if ( mLisst != null && isConnected()) {
            mLisst.disconnect();
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
        mLisst.softReset();
    }

    public final boolean isConnected() {
        if (mLisst != null) {
            return mLisst.isConnected();
        } else { return false; }
    }

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * The Lisst requires arguments, so uses the extended method start_collection
     * 
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        mSampling = SAMPLING_OFF;
    }
    

    /**
     * This is called to update and return the parameters.  If not busy,
     * this will request the status of all parameters and update them all.
     *
     * @param params
     * @param reply
     */
    public void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {

        // only if we are not collecting can we get new status
        if (mLisst.mLisstData.getDataCollection()==false && mLisst.mLisstBusy==false) {
            try {
                synchronized (this) { mLisst.getStatus(); }     // update the data
            } catch (TimeoutException e) {
                mLogger.log("Get:" + e.toString(), this.getClass().getName(), LogLevel.ERROR);
                reply.addError(BrokerError.E_CONNECTION);
                return;
            }
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
            if (ps.equals("seawater_pump"))    { newValue = mLisst.mLisstData.getSeawaterPump();    }
            if (ps.equals("clean_water_flush")){ newValue = mLisst.mLisstData.getCleanWaterFlush(); }
            if (ps.equals("data_collection"))  { newValue = mLisst.mLisstData.getDataCollection();  }
            if (ps.equals("clean_water_level")){ newValue = mLisst.mLisstData.getCleanWaterLevel(); }
            if (ps.equals("serial_number"))    { newValue = mLisst.mLisstData.getSerialNumber();    }
            if (ps.equals("firmware_version")) { newValue = mLisst.mLisstData.getFirmwareVersion(); }
            if (ps.equals("data_file_name"))   { newValue = mLisst.mLisstData.getDataFileName();    }
            if (ps.equals("data_file_transferred")) {newValue=mLisst.mLisstData.getDataFileTransferred(); }
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
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(mLisst.mLisstData.getStatusTimestamp()), changed);
        }
    }

    /**
     * put writable values
     * @param params
      * @param reply
     */
    public synchronized void put(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
        // loop through all requested parameters
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            // get current requested parameter and make sure it's valid
            Map.Entry<String, Object> param = iter.next();
            String ps = param.getKey();
            Object o = param.getValue();
            if (!checkParameter(ps)) {
                // unsupported, skip it
                reply.addError(BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }
            Boolean b = false;
            if (o instanceof Boolean) {
                b = (Boolean) o;
            } else if (o instanceof String) {
                b = Boolean.valueOf((String) o);
            }
            // we have a valid requested parameter, set the value
            if (mLisst.mLisstData.getDataCollection()==true) {
                reply.addError(BrokerError.E_INSTRUMENT_BUSY);
            } else {
                while (mLisst.mLisstBusy == true) { // wait for our chance to communicate
                    try { Thread.sleep(10); } catch (Exception e) { /*do nothing*/ }
                }

                if (ps.equals("seawater_pump"))    {
                    mLisst.mLisstData.setSeawaterPump(b);   // set the indicator
                    try {
                        mLisst.seawaterPump();                  // and act on the value
                    } catch (TimeoutException e) {
                        mLogger.log("Get:" + e.toString(), this.getClass().getName(), LogLevel.ERROR);
                        reply.addError(BrokerError.E_CONNECTION);
                        return;
                    }
                    reply.addResult("OK", true);
                }
                if (ps.equals("clean_water_flush")){
                    mLisst.mLisstData.setCleanWaterFlush(b);// set the indicator
                    try {
                        mLisst.cleanWaterFlush();               // and act on the value
                    } catch (TimeoutException e) {
                        mLogger.log("Get:" + e.toString(), this.getClass().getName(), LogLevel.ERROR);
                        reply.addError(BrokerError.E_CONNECTION);
                        return;
                    }
                    reply.addResult("OK", true);
                }
            }
        }
    }

    /**
    allows methods with non-standard JSON reply formats to be serviced.

    @param method String representation of the method.
    @param request The original JSON request.
     */
    @Override
    public void extendedMethod(String method, JSONObject request, BrokeredDeviceListener listener) throws Exception {
//        JSONObject response = new JSONObject();
        BrokerMessage reply = new BrokerMessage(method, true);
        JSONObject params;
        String lisst_file;   // lisst data file name
        boolean success = false;

        try {
            reply.setId(request.getInt("id"));
            reply.setMethod(method);
            if (isConnected()) {    // make sure we are connected
                if(method.equals("get_file")) {
                    if (mLisst.mLisstData.getDataCollection() == true) {
                        reply.addError(BrokerError.E_INSTRUMENT_BUSY);
                    } else {
                        while (mLisst.mLisstBusy == true) { // wait for our chance to communicate
                            try { Thread.sleep(10); } catch (Exception e) { /*do nothing*/ }
                        }

                        if (request.has("params")) {
                            params = request.getJSONObject("params");
                            if(params.has("lisst_file")) {
                                lisst_file = params.getString("lisst_file");
                            } else {
                                lisst_file = mLisst.mLisstData.getDataFileName();
                            }
                        } else {
                            lisst_file = mLisst.mLisstData.getDataFileName();
                        }
                        if (lisst_file != null) {
                            mLogger.log("Beginning file transfer of "+lisst_file, this.getClass().getName(), LogLevel.DEBUG);
                            success = mLisst.getFile(lisst_file);
                        }
                        if (success) {
                            mLogger.log("File transfer of "+lisst_file+" successful.", this.getClass().getName(), LogLevel.DEBUG);
                            reply.addResult("Success");
                        } else {
                            mLogger.log("File transfer of "+lisst_file+" FAILED.", this.getClass().getName(), LogLevel.ERROR);
                            reply.addResult("Fail");
                        }
                    }
                } else if(method.equals("delete_file")) {
                    if (mLisst.mLisstData.getDataCollection() == true) {
                        reply.addError(BrokerError.E_INSTRUMENT_BUSY);
                    } else {
                        while (mLisst.mLisstBusy == true) { // wait for our chance to communicate
                            try { Thread.sleep(10); } catch (Exception e) { /*do nothing*/ }
                        }

                        if (request.has("params")) {
                            params = request.getJSONObject("params");
                            if(params.has("lisst_file")) {
                                lisst_file = params.getString("lisst_file");
                                mLisst.deleteFile(lisst_file);
                                mLogger.log("Deleting lisst file: "+lisst_file, this.getClass().getName(), LogLevel.DEBUG);
                                reply.addResult("Deleted "+lisst_file);
                            } else {
                                reply.addResult("This command requires a file name paramater lisst_file");
                            }
                        } else {
                            reply.addResult("This command requires a file name paramater lisst_file");
                        }
                    }
                } else if(method.equals("start_collection")) {
                    if (mLisst.mLisstData.getDataCollection() == true) {
                        reply.addError(BrokerError.E_INSTRUMENT_BUSY);
                    } else {
                        while (mLisst.mLisstBusy == true) { // wait for our chance to communicate
                            try { Thread.sleep(10); } catch (Exception e) { /*do nothing*/ }
                        }

                        if (request.has("params")) {
                            params = request.getJSONObject("params");
                            if(params.has("cast_number")) {
                                mCastNumber = params.getInt("cast_number");
                            } else {
                                mCastNumber = 1;
                            }
                            if(params.has("pump_delay")) {
                                mPumpDelay = params.getInt("pump_delay");
                            } else {
                                mPumpDelay = 0;
                            }
                        } else {
                            mCastNumber = 1;
                            mPumpDelay = 0;
                        }
                        mLogger.log("Starting data collection for cast: "+mCastNumber, this.getClass().getName(), LogLevel.DEBUG);
                        mLisst.startCollection();
                        reply.addResult("OK");
                    }
                } else if(method.equals("stop_collection")) {
                    mLogger.log("Stopping data collection for cast: "+mCastNumber, this.getClass().getName(), LogLevel.DEBUG);
                    mLisst.stopCollection();
                    reply.addResult("OK");
                }
            } else {
                reply.addError(BrokerError.E_CONNECTION);
            }
        } catch(TimeoutException e) {
            reply.addError(BrokerError.E_CONNECTION);
        } catch(Exception e) {
            e.printStackTrace();
            try {
                reply.addResult(e.toString());
            } catch(Exception ee) {
                ee.printStackTrace();
            }
        }
        try {
            listener.onData(reply.toJSONResponse());
        } catch (JSONException e) {
            mLogger.log("Exception during response in extended method: " + e.toString(),
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }

    public void extendedReply(String method, HashMap<String, Object> results,
            HashMap<String, Boolean> changed) {
        // TODO: log reply to unknown method requested
    }

    /**
     * Called when lisst finishes sending its measurements.
     * @param d
     */
    public final void onMeasurement(final LisstData d) {
        mLastDataTime = System.currentTimeMillis();
        
        if ( !Boolean.parseBoolean(mBroker.getProperties().getProperty("db_enabled", "true")) ||
             ( getLogging() != true ) ) {
            return;
        }

        try {
            // insert a row
            Timestamp ts = new Timestamp(System.currentTimeMillis());

            String table_prefix = mBroker.getProperties().getProperty("db_table_prefix", "bp");
// This code would work when both running locally and the file is stored locally            
//            String cmd =
//                "insert into " + table_prefix + "_lisst values(?, ?, lo_import(?))";
            String cmd = "insert into " + table_prefix + "_lisst " + 
                    "(cast_no, loc_code, sample_time, serial_number, firmware_version, " +
                    "lisst_file_name, lisst_file, meas_per_avg, zero_file, clean_water_level, pump_delay) " +
                    "values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
            BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd);
//            PreparedStatement pstmt = mBroker.getDb().getConnection().prepareStatement(cmd);
            pstmt.setInt(1, new Integer(mCastNumber));
            pstmt.setString(2, table_prefix);
            pstmt.setTimestamp(3, ts);
            pstmt.setString(4, mLisst.mLisstData.getSerialNumber());
            pstmt.setString(5, mLisst.mLisstData.getFirmwareVersion());
            pstmt.setString(6, mLisst.mLisstData.getDataFileName());
            File df = new File (mLisst.mLisstFileFolder+"/"+mLisst.mLisstData.getDataFileName());
            FileInputStream fis = new FileInputStream(mLisst.mLisstFileFolder+"/"+mLisst.mLisstData.getDataFileName());
//            System.out.println("fis avail:"+fis.available());
//            byte[] b = new byte[2048];
//            System.out.println("bytes read: "+fis.read(b, 0, (int)df.length()));
            pstmt.setBinaryStream(7, fis, (int)df.length());
            pstmt.setInt(8, mLisst.mLisstData.getMeasPerAvg());
            pstmt.setBoolean(9,mLisst.mLisstData.getZeroFile());
            pstmt.setInt(10, mLisst.mLisstData.getCleanWaterLevel());
            pstmt.setInt(11, mPumpDelay);
// This code would work when both running locally and the file is stored locally            
//            pstmt.setString(3, mLisst.mLisstFileFolder+"/"+mLisst.mLisstData.getDataFileName());
//System.out.println(pstmt.toString());

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
        JSONParameters.put("seawater_pump",     arrayOf("boolean",     "RW", "0"));
        JSONParameters.put("clean_water_flush", arrayOf("boolean",     "RW", "1"));
        JSONParameters.put("data_collection",   arrayOf("boolean",     "RW", "2"));
        JSONParameters.put("clean_water_level", arrayOf("percent",     "RO", "3"));
        JSONParameters.put("serial_number",     arrayOf("text",        "RO", "4"));
        JSONParameters.put("firmware_version",  arrayOf("text",        "RO", "5"));
        JSONParameters.put("data_file_name",    arrayOf("text",        "RO", "6"));
        JSONParameters.put("data_file_transferred", arrayOf("boolean", "RO", "7"));
    }

}
