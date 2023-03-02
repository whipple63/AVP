package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokerError;
import edu.unc.ims.avp.BufferedPreparedStatement;
import edu.unc.ims.instruments.sounders.SounderInstrument;
import edu.unc.ims.instruments.sounders.SounderData;
import edu.unc.ims.instruments.sounders.SounderListener;
import java.lang.reflect.Constructor;
import java.sql.Timestamp;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import java.util.ArrayList;
import edu.unc.ims.avp.Logger.LogLevel;
import java.util.Arrays;
import java.util.List;
import java.util.Calendar;

/**
 * Adapter-level code for depth sounders.  This includes routines to do low-level
 * data pre-processing (e.g. averaging), and logging to the database and responding to 
 * external broker commands (via the interface) that are specific to sounders (e.g. data
 * retrieval).
 */
public class SounderAdapter extends BrokerAdapter implements SounderListener {

    private Broker mBroker;             // Reference to the controlling Broker.
    private SounderInstrument mSounder;       // The sounder device class.
    String mHost ;
    int mPort;
    
    // Values to tune the algorithm
    private static final long COLLECTION_WINDOW = 600000;
    private static final int COLLECTION_THRESHOLD = 100;
    private static final int GOOD_THRESHOLD = 30;
    private static final int BAD_THRESHOLD = 50;
    private static final double DEPTH_PERCENTILE = 0.9;
    
    // these values are read from the config file
    private double DEFAULT_DEPTH_M;
    private double MIN_DEPTH_M;
    private double MAX_DEPTH_M;
    private double MAX_STEP_M;

    private HashMap<String, Double> mMeasuredValues = new HashMap<String, Double>();    // place to keep data ready
    private List<Double> mAvgDepthValues = new ArrayList<Double>();    // List of accumulated readings for averaging.

    private HashMap<Long, Double> mWorkingDepths = new HashMap<Long, Double>();
    private boolean mWorkingDepthUpdated = false;   // will change to true when first given a value

    private ArrayList<Double> mSamples = new ArrayList<Double>();
    private int mCollected = 0;
    private int mBad = 0;

    private static final int UPDATE_INTERVAL = 1000;    // Minimum subscription interval
    @Override public int getMinSubInterval() { return UPDATE_INTERVAL;  }

    // Time of last data recorded to database and last data collected
    private long mLastDbTime = 0;
    private long mLastDataTime = 0;
    
    private long mAveragingStart = 0;
    private long mAveragingPeriod = 60000;
    
    // parameters that can be subscribed to
    private static String[] arrayOf(String a, String b) {
        String[] rv = {a, b};
        return rv;
    }

    static {
        JSONParameters.put("water_depth", arrayOf("meters", "RO"));
        JSONParameters.put("water_depth_1minave", arrayOf("meters", "RO"));
        JSONParameters.put("water_depth_working", arrayOf("meters", "RO"));
        JSONParameters.put("water_temp_surface", arrayOf("degrees C", "RO"));
    }


    
    /**
     * Constructor initializes measured values to indicate that no measurements
     * have been made yet and gets values from config.
     * 
     * @param  broker   Controlling Broker.
     */
    public SounderAdapter(final Broker broker) throws Exception {
        mBroker = broker;
        
        mMeasuredValues.put("timestamp", Double.valueOf(0));
        mMeasuredValues.put("water_depth", Double.valueOf(0));
        mMeasuredValues.put("water_depth_1minave", Double.valueOf(0));
        mMeasuredValues.put("water_depth_working", DEFAULT_DEPTH_M);
        mMeasuredValues.put("water_temp_surface", Double.valueOf(0));
        
        // get some parameters from the config file
        DEFAULT_DEPTH_M = Double.parseDouble(mBroker.getProperties().getProperty("DefaultDepthM", "5"));
        MIN_DEPTH_M =     Double.parseDouble(mBroker.getProperties().getProperty("MinDepthM",     "1"));
        MAX_DEPTH_M =     Double.parseDouble(mBroker.getProperties().getProperty("MaxDepthM",    "10"));
        MAX_STEP_M  =     Double.parseDouble(mBroker.getProperties().getProperty("MaxStepM",    "0.0005"));

        String adapterName = getClass().getName().substring(getClass().getName().lastIndexOf('.')+1);
        mHost = mBroker.getProperties().getProperty(adapterName + "_host", "localhost");
        mPort = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_port", "55237"));
        
        // Load the instrument class
        Class<?> c = ClassLoader.getSystemClassLoader().loadClass(mBroker.getProperties().getProperty("instrument_class"));
        Constructor cst = c.getDeclaredConstructor(String.class, int.class);
        mSounder = (SounderInstrument)cst.newInstance(mHost, mPort);
    }

    
    /**
     * Initialize connection to the device.  Turn power on if necessary, get config
     * file information, instantiate the instrument class as specified in config and connect.
     * 
     * @throws Exception   on error
     */
    @Override
    public final void connect() throws Exception {
        power_on();     // turn on the instrument's power

        mSounder.addListener(this);   // Register this class as a listener of the instrument

        // Connect to the instrument
        mLogger.log("Connecting to Sounder @ " + mHost + ":" + mPort + "...", "SounderAdapter", LogLevel.INFO);
        mSounder.connect();
        mLogger.log("Connected to Sounder @ " + mHost + ":" + mPort, "SounderAdapter", LogLevel.INFO);
        
        // could put these values in the config file
        setSampling(true);  // sounders default to sampling
        setLogging(true);   // default to logging
    }

    
    /**
     * Free up any resources prior to destruction.  Disconnecting stops the instrument's run thread.
     * @throws Exception   on error.
     */
    @Override
    public final void disconnect() throws Exception {
        if ( mSounder != null && isConnected()) {
            mSounder.disconnect();
        }
    }

    
    /**
     * Attempt a soft reset of the device.  See device specific reset.
     * @throws Exception   on error.
     */
    @Override
    public final void softReset() throws Exception {
        mSounder.reset();
    }

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * 
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        if (toOn == true) {
            if (mSounder.startSampling()) {
                mSampling = SAMPLING_ON;
            }
        } else {
            if (mSounder.stopSampling()) {
                mSampling = SAMPLING_OFF;
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
            double newValue = mMeasuredValues.get(ps);
            if (lastO instanceof Double) {
                double oldValue = (Double) lastO;
                changed = oldValue != newValue;
            } else {
                changed = true;
            }
            if (Double.isNaN(newValue) || Double.isInfinite(newValue)) {
                newValue = -1;
            }
            entry.setValue(Double.valueOf(newValue));
            reply.addResult(ps, "value", newValue, changed);
            reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(mMeasuredValues.get("timestamp").longValue()),
                    changed);
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
     * Check to see if we are still connected.
     * @return  boolean
     */
    @Override
    public boolean isConnected() {
        if (mSounder != null) {
            return mSounder.isConnected();
        } else {
            return false;
        }
    }

    
    /**
     * onMeasurement is called by the sounder instrument code each time a set of
     * data have been received.  The adapter's handling of the data starts here.
     * 
     * @param d    data from the sounder
     */
    @Override
    public final void onMeasurement(final SounderData d) {
        long timestamp = System.currentTimeMillis();
        mLastDataTime = timestamp;  // keep track of when data are received

        // data are stored in mMeasuredValues
        averageDepth(d, timestamp); // calculate based on incoming data
        workingDepth(d, timestamp);

        mMeasuredValues.put("timestamp", (double) timestamp);
        mMeasuredValues.put("water_depth", d.getDepthM());
        mMeasuredValues.put("water_temp_surface", d.getTempC());

        // add this depth to a growing list
        mSamples.add(d.getDepthM());
        
        if (timeToInsert()) {           // data into the database
            mSamples = trim(mSamples);  // trim extreme values (outliers)
            insertData();               // into the database
            mLastDbTime = timestamp;    // keep track of when the insert happened
            mSamples.clear();           // clear out the samples to start over
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

        Timestamp ts = new Timestamp(currentMinuteInMillis());  // time truncated to nearest minute
        
        /* TODO: Soon database structure should be specified in the config file and all
         * values going in the db should be subscribable (e.g. change calculated_depth to 
         * be a running average) and standardize the variable names.  BrokerAdapter level code
         * could have generic running average and std code.  In fact, names could just
         * be read from the db and retrieved.
         */
        String table_prefix = mBroker.getProperties().getProperty("db_table_prefix", "bp");
        String cmd = "insert into " + table_prefix + "_depth " +
                "(loc_code, sample_time, working_depth, calculated_depth, " +
                "calculated_depth_std, num_good_pings, temp_c)" +
                "values(?, ?, ?, ?, ?, ?, ?)";
        try {
            // insert a row
            BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd);
            pstmt.setString(1, table_prefix);
            pstmt.setTimestamp(2, ts);
            pstmt.setDouble(3, mMeasuredValues.get("water_depth_working"));
            pstmt.setDouble(4, calculatedDepth(mSamples));
            pstmt.setDouble(5, std(mSamples));
            pstmt.setInt(6, numGood(mSamples));
            pstmt.setDouble(7, mMeasuredValues.get("water_temp_surface"));
            mBroker.getDb().bufferedExecuteUpdate(pstmt);
        } catch (Exception e) {
            mLogger.log("Insert:" + e.toString(), "SounderAdapter", LogLevel.ERROR);
        }
    }

    
    /**
     * Keep track of averaged data, add if available.
     * This whole thing would be better off written as a running average for a time
     * period.  A utility class that is constructed with a stat period and can
     * return mean and std ignoring infinite and nan values.  Can poll for stats
     * and total data accumulation time (or boolean has length been reached).
     * 
     * @param  d   New data point
     * @param  timestamp  timestamp for data value
     */
    private void averageDepth(final SounderData d, final long timestamp) {
        Double v, last;
        double average = 0;
        double reading = d.getDepthM();
        
        mAvgDepthValues.add(new Double(reading));
        if (mAveragingStart == 0) {
            mAveragingStart = timestamp;    // time of first reading
            
        } else {
            if ((timestamp - mAveragingStart) >= mAveragingPeriod) {
                double total = 0.0;
                Iterator<Double> i = mAvgDepthValues.iterator();
                last = 0.0;
                while (i.hasNext()) {   // for each of the mAvgDepthValues
                    v = i.next();
                    if (v == Double.NaN) { v = last; }  // skip NaNs
                    last = v;
                    total += v.floatValue();    // total them up
                }
                if (mAvgDepthValues.size() > 0) {
                    average = total / mAvgDepthValues.size();   // THIS ISN'T RIGHT IF THERE WERE NANS
                }
                mMeasuredValues.put("water_depth_1minave", average);
                
                // reset to start accumulating values again
                mAveragingStart = 0;
                mAvgDepthValues.clear();
            }
        }
    }
    

    /**
     * Calculate the mean of the list of samples
     * @param samples
     * @return the mean
     */
    private double calculatedDepth(ArrayList<Double> samples) {
        return mean(samples);
    }
    
    
    /**
     * Working depth is a more complicated algorithm that attempts to track the 
     * water depth with less errors.  There must be enough good observations and 
     * the working depth can't step beyond a certain amount each iteration.
     * 
     * @param d
     * @param timestamp 
     */
    private void workingDepth(final SounderData d, final long timestamp) {
        double reading = d.getDepthM();
        mCollected++;   // count readings
        
        if ((reading > MIN_DEPTH_M) && (reading < MAX_DEPTH_M)) {   // add to working depths if with thresholds
            mWorkingDepths.put(timestamp, reading);
        } else {
            mBad++;
        }
        
        if (mCollected >= COLLECTION_THRESHOLD) {
            if (mBad > BAD_THRESHOLD) { // log if there were too many bad readings
                mLogger.log(mBad + " of the last " + mCollected  + " depth readings were bad.",
                        "SounderAdapter", LogLevel.INFO);
            }
            mCollected = 0;
            mBad = 0;
        }
        
        Long[] timestamps = new Long[mWorkingDepths.size()];
        mWorkingDepths.keySet().toArray(timestamps);    // get all of the time stamps
        Arrays.sort(timestamps);                        // and sort them
        for (int i = 0; i < timestamps.length; i++) {
            if (timestamp - timestamps[i] > COLLECTION_WINDOW) {    // if a value is too old, remove it
                mWorkingDepths.remove(timestamps[i]);
            } else {
                break; // since array is sorted, we can break here
            }
        }
        
        if (mWorkingDepths.size() < GOOD_THRESHOLD) {
            return; // don't update working depth
        }
        
        // find the depth that represents the DEPTH_PERCENTILE value
        Double[] depths = new Double[mWorkingDepths.size()];
        depths = mWorkingDepths.values().toArray(depths);
        ArrayList<Double> vdep = new ArrayList<Double>(Arrays.asList(depths));
        double workingDepth = normsinv(DEPTH_PERCENTILE) * std(vdep) + mean(vdep);
        
        if (mWorkingDepthUpdated) {     // if there is a working depth to change
            double currentDepth = mMeasuredValues.get("water_depth_working");
            double delta = workingDepth - currentDepth;
            if (delta > MAX_STEP_M) {   // only allow slow changes to the depth
                // These aren't abnormal, we're always hunting for the spot
                workingDepth = currentDepth + MAX_STEP_M;
            } else if (delta < -MAX_STEP_M) {
                workingDepth = currentDepth - MAX_STEP_M;
            }
        }
        mMeasuredValues.put("water_depth_working", workingDepth);
        mWorkingDepthUpdated = true;
    }
    
    
    /**
     Rounds the current time down to the nearest whole minute.
     @return the current time with seconds and milliseconds set to zero.
     */
    private long currentMinuteInMillis() {
        Calendar now = Calendar.getInstance();
        now.set(Calendar.SECOND, 0);
        now.set(Calendar.MILLISECOND, 0);
        return now.getTimeInMillis();
    }

    
    /**
     * Add up the number of non-infinite and non-NaN samples we have.
     * 
     * @param samples
     * @return n
     */
    private int numGood(ArrayList<Double> samples) {
        Iterator<Double> iter = samples.iterator();
        int n = 0;
        while (iter.hasNext()) {
            double sample = iter.next().doubleValue();
            if (!Double.isInfinite(sample) && !Double.isNaN(sample)) {
                n++;
            }
        }
        return n;
    }


    /**
     * Remove values that exceed max and min thresholds
     * @param samples
     * @return trimmed samples
     */
    private ArrayList<Double> trim(ArrayList<Double> samples) {
        Iterator<Double> iter = samples.iterator();
        while (iter.hasNext()) {
            double sample = iter.next().doubleValue();
            if ((sample < MIN_DEPTH_M || sample > MAX_DEPTH_M)) {
                iter.remove();
            }
        }

        return samples;
    }

    
    /**
     * Take the mean ignoring infinite and NaN values.
     * 
     * @param samples
     * @return mean
     */
    private double mean(ArrayList<Double> samples) {
        Iterator<Double> iter = samples.iterator();
        double sum = 0;
        int n = 0;
        while (iter.hasNext()) {
            double sample = iter.next().doubleValue();
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
     * @param samples
     * @return mean
     */
    private double std(ArrayList<Double> samples) {
        double m = mean(samples);
        Iterator<Double> iter = samples.iterator();
        int n = 0;
        double sum = 0;
        while (iter.hasNext()) {
            double sample = iter.next().doubleValue();
            if (!Double.isInfinite(sample) && !Double.isNaN(sample)) {
                sum += Math.pow((sample - m), 2);
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
     Lower tail quantile for standard normal distribution function.
    
     This function returns an approximation of the inverse cumulative
     standard normal distribution function.  I.e., given P, it returns
     an approximation to the X satisfying P = Pr{Z <= X} where Z is a
     random variable from the standard normal distribution.
    
     The algorithm uses a minimax approximation by rational functions
     and the result has a relative error whose absolute value is less
     than 1.15e-9.
    
     Author:      Peter John Acklam
     Time-stamp:  2003-05-05 05:15:14
     E-mail:      pjacklam@online.no
     WWW URL:     http://home.online.no/~pjacklam

     An algorithm with a relative error less than 1.15*10-9 in the entire region.
      * 
      * @param p
      * @return 
      */
    private double normsinv(double p) {
        // Coefficients in rational approximations
        double[] a = {-3.969683028665376e+01,  2.209460984245205e+02,
                      -2.759285104469687e+02,  1.383577518672690e+02,
                      -3.066479806614716e+01,  2.506628277459239e+00};

        double[] b = {-5.447609879822406e+01,  1.615858368580409e+02,
                      -1.556989798598866e+02,  6.680131188771972e+01,
                      -1.328068155288572e+01 };

        double[] c = {-7.784894002430293e-03, -3.223964580411365e-01,
                      -2.400758277161838e+00, -2.549732539343734e+00,
                       4.374664141464968e+00,  2.938163982698783e+00};

        double[] d = {7.784695709041462e-03, 3.224671290700398e-01,
                      2.445134137142996e+00,  3.754408661907416e+00};

        // Define break-points.
        double plow  = 0.02425;
        double phigh = 1 - plow;

        // Rational approximation for lower region:
        if ( p < plow ) {
                 double q  = Math.sqrt(-2*Math.log(p));
                 return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) /
                                                 ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
        }

        // Rational approximation for upper region:
        if ( phigh < p ) {
                 double q  = Math.sqrt(-2*Math.log(1-p));
                 return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) /
                                                        ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1);
        }

        // Rational approximation for central region:
        double q = p - 0.5;
        double r = q*q;
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q /
                                 (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1);
    }

    
    /**
     Checks for the beginning of a ten-minute interval.
     @return true if it is time to insert values into the database
     */
    private boolean timeToInsert() {    
        Calendar now = Calendar.getInstance();
        lastMinute = minute;
        minute = now.get(Calendar.MINUTE);
        return !mSamples.isEmpty() && (minute % 10 == 0) && (minute != lastMinute);
    }
    int minute = -1;
    int lastMinute = -1;
}
