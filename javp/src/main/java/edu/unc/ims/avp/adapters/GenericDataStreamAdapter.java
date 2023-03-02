package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokerError;
import edu.unc.ims.avp.BrokeredDeviceListener;
import edu.unc.ims.avp.BufferedPreparedStatement;
import edu.unc.ims.instruments.generic.GenericDataStream;
import edu.unc.ims.instruments.generic.GenericDataStreamData;
import edu.unc.ims.instruments.generic.GenericDataStreamListener;
import java.lang.reflect.Constructor;
import java.sql.Timestamp;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.ArrayList;
import edu.unc.ims.avp.Logger.LogLevel;
import java.util.Arrays;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * Adapter-level code for a generic data stream.  This includes routines to do low-level
 * data pre-processing (e.g. averaging), and logging to the database and responding to 
 * external broker commands (via the interface).
 */
public class GenericDataStreamAdapter extends BrokerAdapter implements GenericDataStreamListener {

    private boolean mDebugThis = false;
    
    private Broker mBroker;             // Reference to the controlling Broker.
    private GenericDataStream mGDS;     // The device class.
    String mHost ;
    int mPort;
    
    private String[] mColNames;   // to hold information about the data structure
    private String[] mColTypes;
    private String[] mColUnits;
    
    private GenericDataStreamData mMeasuredValues;
    
    private LinkedList<GenericDataStreamData> mSamples = new LinkedList<GenericDataStreamData>();

    private ArrayList<MeanInfo> mMeanVars = new ArrayList<MeanInfo>();
    private class MeanInfo {    // helper class to hold vars to take means of
        protected String mVarName;  // the variable to take the mean and std of
        protected int mNumObs;      // number of observations over which to take means and stds
        protected double mOutlierStd; // std beyond which to trim outliers
        protected double lowLim;    // lower limit for trimming
        protected double upLim;     // upper limit for trimming
        public MeanInfo(String name, int nobs, double std) {
            mVarName = name;
            mNumObs = nobs;
            mOutlierStd = std;
        }
    }
    private int mMaxObs = 0;
    
    private static final int UPDATE_INTERVAL = 1000;    // Minimum subscription interval
    @Override public int getMinSubInterval() { return UPDATE_INTERVAL;  }

    // Time of last data recorded to database and last data collected
    private long mLastDbTime = 0;
    private long mFirstDataTime = 0;
    private long mLastDataTime = 0;
       
    private static String[] arrayOf(String a, String b) {
        String[] rv = {a, b};
        return rv;
    }


    /**
     * Constructor initializes measured values to indicate that no measurements
     * have been made yet and gets values from config.
     * 
     * @param  broker   Controlling Broker.
     */
    public GenericDataStreamAdapter(final Broker broker) throws Exception {
        mBroker = broker;
                
        // get some parameters from the config file
        mColNames = mBroker.getProperties().getProperty("column_names").split("[ ,\t]+");
        mColTypes = mBroker.getProperties().getProperty("column_types").split("[ ,\t]+");
        mColUnits = mBroker.getProperties().getProperty("column_units").split("[ ,\t]+");
        for (int i=0; i<mColNames.length; i++) {
            JSONParameters.put(mColNames[i], arrayOf(mColUnits[i], "RO"));
        }

        String[] meanVars = mBroker.getProperties().getProperty("mean_vars").split("[ ,\t]+");
        String[] numObs = mBroker.getProperties().getProperty("num_obs").split("[ ,\t]+");
        String[] outlierStd = mBroker.getProperties().getProperty("outlier_std").split("[ ,\t]+");        
        if ( (meanVars.length != numObs.length) || (meanVars.length != outlierStd.length) ) {
            mLogger.log("Config file error. mean_vars, num_obs, and outlier_std all must have same length.",
                    "GenericDataStreamAdapter", LogLevel.ERROR);
        }
        for (int i=0; i<meanVars.length; i++) {
            mMeanVars.add(new MeanInfo(meanVars[i], Integer.valueOf(numObs[i]), Double.valueOf(outlierStd[i])));
            JSONParameters.put(meanVars[i]+"_mean"+numObs[i], arrayOf("Double", "RO"));
            JSONParameters.put(meanVars[i]+"_std"+numObs[i], arrayOf("Double", "RO"));
            if (Integer.valueOf(numObs[i]) > mMaxObs) { mMaxObs = Integer.valueOf(numObs[i]); }
        }

        
        String adapterName = getClass().getName().substring(getClass().getName().lastIndexOf('.')+1);
        mHost = mBroker.getProperties().getProperty(adapterName + "_host", "localhost");
        mPort = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_port", "55239"));
        
        // Load the instrument class
        Class<?> c = ClassLoader.getSystemClassLoader().loadClass(mBroker.getProperties().getProperty("instrument_class"));
        Constructor cst = c.getDeclaredConstructor(Broker.class, String.class, int.class);
        mGDS = (GenericDataStream)cst.newInstance(mBroker, mHost, mPort);
    }

    
    /**
     * Initialize connection.  Turn power on if necessary, get config
     * file information, instantiate the instrument class as specified in config and connect.
     * 
     * @throws Exception   on error
     */
    @Override
    public final void connect() throws Exception {
        if (mBroker.getProperties().containsKey("AioAdapter_host")) {
            power_on();     // turn on the instrument's power
        }

        mGDS.addListener(this);   // Register this class as a listener of the instrument

        // Connect to the instrument
        mLogger.log("Connecting to data stream @ " + mHost + ":" + mPort + "...", "GenericDataStreamAdapter", LogLevel.INFO);
        mGDS.connect();
        mLogger.log("Connected to data stream @ " + mHost + ":" + mPort, "GenericDataStreamAdapter", LogLevel.INFO);
        
        // could put these values in the config file
        setSampling(true);  // default to sampling
        setLogging(true);   // default to logging
    }

    
    /**
     * Free up any resources prior to destruction.  Disconnecting stops the instrument's run thread.
     * @throws Exception   on error.
     */
    @Override
    public final void disconnect() throws Exception {
        if ( mGDS != null && isConnected()) {
            mGDS.disconnect();
        }
    }

    
    /**
     * Attempt a soft reset of the device.  See device specific reset.
     * @throws Exception   on error.
     */
    @Override
    public final void softReset() throws Exception {
        mGDS.reset();
    }

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * 
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        if (toOn == true) {
            if (mGDS.startSampling()) {
                mSampling = SAMPLING_ON;
            }
        } else {
            if (mGDS.stopSampling()) {
                mSampling = SAMPLING_OFF;
                mFirstDataTime = 0;
            }
        }
    }
    
    
    /**
     * Must keep track of times.  This information is made available via the broker status
     * command and helps to insure that things are still working.
     */
    @Override public Timestamp getLastDataTime() { return new Timestamp(mLastDataTime); }
    @Override public Timestamp getLastDbTime() { return new Timestamp(mLastDbTime); }

    
    /**
     * Get a value from this broker and report whether it has changed.
     * 
     * @param params    values to get
     * @param reply     to be sent back to requester
     * @throws Exception 
     */
    @Override
    public void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            boolean changed;
            Map.Entry<String, Object> entry = iter.next();
            String ps = entry.getKey();
            Object lastO = entry.getValue();
            if (!checkParameter(ps)) {
                reply.addError(BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }
            Object newValue = mMeasuredValues.getData().get(ps);

            changed = true;
            if (lastO != null) {
                if (lastO.equals(newValue)) { changed = false; }
            }

            entry.setValue(newValue);
            reply.addResult(ps, "value", newValue, changed);
            reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(
                    (Long) mMeasuredValues.getData().get("timestamp") ), changed);
        }
    }

    
    /**
     * Set a value, if possible, in this broker
     * @param params    the values to set
     * @param reply     to send back to caller
     */
    @Override
    public void put(HashMap<String, Object> params, BrokerMessage reply) {
        // since all parameters are RO, do nothing
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
            
            if(method.equals("send_command")) {
                if (request.has("params")) {
                    params = request.getJSONObject("params");
                    if(params.has("cmd")) {
                        int nLines = 0;
                        if (params.has("nLineReply")) {
                            nLines = params.getInt("nLineReply");
                        }
                        String cmdReply = mGDS.sendCommand(params.getString("cmd"), nLines);   // send command and get a nLines reply
                        reply.addResult(cmdReply);
                    } else {
                        reply.addError(BrokerError.E_BAD_COMMAND, "No cmd argument to send given.");
                    }
                }
            }                
            
        } catch(Exception e) {
            mLogger.log("Exception in GDS extended method: " + e.getMessage(), 
                    this.getClass().getName(), LogLevel.ERROR);
            reply.addError(BrokerError.E_EXCEPTION, e.getMessage());
        }
        
        // Send the response back to the listener
        try {
            listener.onData(reply.toJSONResponse());
        } catch (JSONException e) {
            mLogger.log("JSON Exception in GDS calling onData: " + e.getMessage(), 
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }

        
    /**
     * Check to see if we are still connected.
     * @return  boolean
     */
    @Override
    public boolean isConnected() {
        if (mGDS != null) {
            return mGDS.isConnected();
        } else {
            return false;
        }
    }

    
    /**
     * onMeasurement is called by the instrument code each time a set of
     * data have been received.  The adapter's handling of the data starts here.
     * 
     * @param d    data from the sounder
     */
    @Override
    public final void onMeasurement(final GenericDataStreamData d) {
        long timestamp = System.currentTimeMillis();
        mLastDataTime = timestamp;  // keep track of when data are received
        if (mFirstDataTime == 0) {  // keep time of first data received
            mFirstDataTime = timestamp;
        }

        mMeasuredValues = d;
        mMeasuredValues.getData().put("timestamp", timestamp);
        if (mDebugThis == true) { System.out.println("data: " + mMeasuredValues.getData().toString()); }
        
        // add this observation and keep only as many observations as we need
        mSamples.add(mMeasuredValues);
        if (mSamples.size() > mMaxObs) {
            mSamples.removeFirst();
        }
        
        // then calculate the statistics and put the requested variables in the map
        calculateAverages();
        
        
        if (timeToInsert()) {           // data into the database
            insertData();               // into the database
            mLastDbTime = timestamp;    // keep track of when the insert happened
        }
    }

    
    /**
     * Insert a row of data into the database if enabled and logging.
     */
    protected final void insertData() {
        if ( !Boolean.parseBoolean(mBroker.getProperties().getProperty("db_enabled", "true")) ||
             ( getLogging() != true ) ) {
            return;
        }

        Timestamp ts = new Timestamp( (Long) mMeasuredValues.getData().get("timestamp") );
        
        String table_prefix  = mBroker.getProperties().getProperty("db_table_prefix", "test");
        String table_postfix = mBroker.getProperties().getProperty("db_table_postfix", "generic");
        String table_cols    = mBroker.getProperties().getProperty("db_table_columns");
        String[] data_keys   = mBroker.getProperties().getProperty("db_data_to_insert").split("[ ,\t]+");
        
        StringBuilder cmd = new StringBuilder();
        cmd.append("insert into ").append(table_prefix).append("_").append(table_postfix).append(" ");
        cmd.append("(loc_code, sample_time, ").append(table_cols).append(") ").append("values(");
        // there will be 2 more columns than in the config file for loc_code and sample time
        for (int i=0; i<data_keys.length+1; i++) {
            cmd.append("?, ");
        }
        cmd.append("?)");
        
        try {
            // insert a row
            BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd.toString());
            
            pstmt.setString(1, table_prefix);
            pstmt.setTimestamp(2, ts);
            
            for (int i=0; i<data_keys.length; i++) {
                // for each key get it's type and insert
                if ( mMeasuredValues.getData().containsKey(data_keys[i]) ) {
                    if ( mMeasuredValues.getType().get(data_keys[i]).equals("string") ) {
                        pstmt.setString(i+3,(String) mMeasuredValues.getData().get(data_keys[i]));
                    }
                    if ( mMeasuredValues.getType().get(data_keys[i]).equals("int") ) {
                        pstmt.setInt(i+3, (Integer) mMeasuredValues.getData().get(data_keys[i]));
                    }
                    if ( mMeasuredValues.getType().get(data_keys[i]).equals("double") ) {
                        pstmt.setDouble(i+3, (Double) mMeasuredValues.getData().get(data_keys[i]));
                    }
                }
            }
            
            mBroker.getDb().bufferedExecuteUpdate(pstmt);
        } catch (Exception e) {
            mLogger.log("Insert:" + e.toString(), "GenericDataStreamAdapter", LogLevel.ERROR);
        }
    }

    
    //
    // loop through mMeanVars taking stats and putting them in mMeasuredValues
    //
    private void calculateAverages() {
        Iterator<MeanInfo> iter = mMeanVars.iterator();
        while (iter.hasNext()) {
            MeanInfo m = iter.next();   // for each var we are taking stats of
            setTrimLimits(m);
            mMeasuredValues.getData().put(m.mVarName+"_mean"+m.mNumObs, mean(m));
            mMeasuredValues.getType().put(m.mVarName+"_mean"+m.mNumObs, "double");
            mMeasuredValues.getData().put(m.mVarName+"_std"+m.mNumObs, std(m));
            mMeasuredValues.getType().put(m.mVarName+"_std"+m.mNumObs, "double");
        }
        
    }
    
    private void setTrimLimits(MeanInfo m) {
        double savedStdLim = m.mOutlierStd;
        
        // calculate mean and std with no trimming        
        m.mOutlierStd = 0;
        double thisStd = std(m);
        double thisMean = mean(m);
        
        // set the limits based on the untrimmed values
        m.lowLim = thisMean - savedStdLim*thisStd;
        m.upLim = thisMean + savedStdLim*thisStd;
        m.mOutlierStd = savedStdLim;
    }
    
    
    /**
     * Take the mean ignoring infinite and NaN values.
     * 
     * @param m
     * @return mean
     */
    private double mean(MeanInfo m) {
        int sz = mSamples.size() > m.mNumObs ? mSamples.size()-m.mNumObs : 0;
        Iterator<GenericDataStreamData> iter = mSamples.listIterator(sz);
        double sum = 0;
        int n = 0;
        while (iter.hasNext()) {
            double sample;
            GenericDataStreamData nxt = iter.next();
            if ( nxt.getType().get(m.mVarName) == "int") {
                sample = ((Integer)nxt.getData().get(m.mVarName)).doubleValue();
            } else {
                sample = (Double) nxt.getData().get(m.mVarName);
            }
            // check the trim limits
            if (m.mOutlierStd != 0) {
                if (sample < m.lowLim || sample > m.upLim) { 
                    if (mDebugThis) { System.out.println("trimming: "+sample); }
                    continue; 
                }
            }
            if (!Double.isInfinite(sample) && !Double.isNaN(sample)) {
                sum += sample;
                n++;
            }
        }
        if (n > 0) {
            return (sum / n);
        } else {
            return 0;
        }
    }
    

    /**
     * Take the standard deviation ignoring infinite and NaN values.
     * 
     * @param m
     * @return std
     */
    private double std(MeanInfo m) {
        double mn = mean(m);
        int sz = mSamples.size() > m.mNumObs ? mSamples.size()-m.mNumObs : 0;
        Iterator<GenericDataStreamData> iter = mSamples.listIterator(sz);
        
        int n = 0;
        double sum = 0;
        while (iter.hasNext()) {
            double sample;
            GenericDataStreamData nxt = iter.next();
            if ( nxt.getType().get(m.mVarName) == "int") {
                sample = ((Integer)nxt.getData().get(m.mVarName)).doubleValue();
            } else {
                sample = (Double) nxt.getData().get(m.mVarName);
            }
            // check the trim limits
            if (m.mOutlierStd != 0) {
                if (sample < m.lowLim || sample > m.upLim) { continue; }
            }
            if (!Double.isInfinite(sample) && !Double.isNaN(sample)) {
                sum += Math.pow((sample - mn), 2);
                n++;
            }
        }
        if (n > 0) {
            return Math.sqrt(sum / n);
        } else {
            return 0;
        }
    }

    
    /**
     Checks to see if it is time to insert data into the database.
     */
    private boolean timeToInsert() {
        int write_interval = Integer.valueOf(mBroker.getProperties().getProperty("db_write_interval", "0"));
        if (write_interval != 0) {
            if (mLastDbTime == 0) { // true until first insert
                return System.currentTimeMillis() > mBroker.getStartTime() + write_interval*1000;
            }
            return System.currentTimeMillis() > mLastDbTime + write_interval*1000;
        }
        else {
            return true;
        }
    }
}
