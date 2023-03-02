package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokerError;
import edu.unc.ims.avp.BufferedPreparedStatement;
import edu.unc.ims.instruments.wind.WindInstrument;
import edu.unc.ims.instruments.wind.WindData;
import edu.unc.ims.instruments.wind.WindListener;
import java.sql.Timestamp;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import java.util.Map;
import java.util.HashMap;
import java.util.Iterator;
import java.util.LinkedList;
import java.util.Queue;
import java.lang.reflect.Constructor;
import edu.unc.ims.avp.Logger.LogLevel;

/**
 * Adapts from BrokerAdapter to the Young 32500 compass/wind device.
 */
public class WindAdapter extends BrokerAdapter implements WindListener {
    private Broker mBroker; // Reference to the controlling Broker
    String mHost;   // instrument
    int mPort;

    private WindInstrument mY;  // The compass/wind device class

    private List<WindData> mTenMinuteWindData = new ArrayList<WindData>();
    private Queue<Double> mHourlyWindSpeeds = new LinkedList<Double>();
    private Calendar mTenMinuteStart = null;
    private Calendar mTenMinuteEnd = null;
    private double mTenMinuteMeanWindSpeed = Double.MIN_VALUE;
    private double mTenMinuteMeanWindDirectionUnitVector = Double.MIN_VALUE;
    private double mTenMinuteCompassDir = Double.MIN_VALUE;
    private double mTenMinuteDirUncorr = Double.MIN_VALUE;
    private VectorWindResult mTenMinuteMeanVector = new VectorWindResult(Double.MIN_VALUE, Double.MIN_VALUE);
    private Gust mTenMinuteMaxGust = null;
    private double mTenMinuteMeanWindSpeedStdDev = Double.MIN_VALUE;
    private double mTenMinuteMeanAirTemp = Double.MIN_VALUE;
    private double mTenMinuteMeanAirPressure = Double.MIN_VALUE;
    private WindData mLastReading = null;
    
    // Time of last data recorded to database and last data collected
    private long mLastDbTime = 0;
    private long mLastDataTime = 0;
    @Override public Timestamp getLastDataTime() { return new Timestamp(mLastDataTime); }
    @Override public Timestamp getLastDbTime() { return new Timestamp(mLastDbTime); }

    private static String[] arrayOf(String a, String b) {
        String[] rv = {a, b};
        return rv;
    }
 
    static {
        JSONParameters.put("compass_direction", arrayOf("degrees", "RO"));
        JSONParameters.put("wind_direction", arrayOf("degrees", "RO"));
        JSONParameters.put("average_wind_speed", arrayOf("m/s", "RO"));
        JSONParameters.put("average_wind_dir", arrayOf("degrees", "RO"));
        JSONParameters.put("vector_wind_speed", arrayOf("m/s", "RO"));
        JSONParameters.put("vector_wind_dir", arrayOf("degrees", "RO"));
        JSONParameters.put("wind_speed", arrayOf("m/s", "RO"));
        JSONParameters.put("air_temp", arrayOf("degrees C", "RO"));
        JSONParameters.put("air_pressure", arrayOf("bar", "RO"));
        JSONParameters.put("output_rate", arrayOf("hz", "RW"));
    }

    
    /**
     * constructor initializes member variables and starts an instance of the instrument
     * 
     * @param broker 
     */
    public WindAdapter(final Broker broker) throws Exception {
        mBroker = broker;
        
        String adapterName = getClass().getName().substring(getClass().getName().lastIndexOf('.')+1);
        mHost = mBroker.getProperties().getProperty(adapterName + "_inst_host", "localhost");
        mPort = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_inst_port", "55233"));
        
        // Load the instrument class
        Class<?> c = ClassLoader.getSystemClassLoader().loadClass(mBroker.getProperties().getProperty("instrument_class"));
        Constructor cst = c.getDeclaredConstructor(String.class, int.class, Broker.class);
        mY = (WindInstrument)cst.newInstance(mHost, mPort, mBroker);
        
    }
    
    /**
     * Connect to the instrument and initialize.
     * @throws Exception     on error
     */
    @Override
    public final void connect() throws Exception {
        power_on(); // First thing we do is turn on the power

        mY.addListener(this);   // Send all data events from the instrument to this class

        // Attempt to connect to the instrument's serial interface (via socket)
        mLogger.log("Connecting to Wind @ " + mHost + ":" + mPort + "...", this.getClass().getName(), LogLevel.INFO);
        mY.connect();
        mLogger.log("Connected to Wind @ " + mHost + ":" + mPort, this.getClass().getName(), LogLevel.INFO);

        // Override the default sample rate on the device if user requested it.
        mY.setOutputRate(Double.parseDouble(mBroker.getProperties().getProperty(
            mBroker.getAdapterName() + "_output_rate", "2.0")));

        // could put these values in the config file
        setSampling(true);  // default to sampling
        setLogging(true);   // default to logging
    }

    
    /**
     * Free up any resources prior to destruction.
     * @throws Exception     on error.
     */
    @Override
    public final void disconnect() throws Exception {
        if ( mY != null && isConnected()) {
           mY.disconnect();
        }
    }

    @Override
    public int getMinSubInterval() {
        return 100; // 100 ms is about as fast as a broker can send messages
    }


    /**
    Attempt a soft reset.
    @throws Exception     on error.
     */
    @Override
    public final void softReset() throws Exception {
        mY.reset();
    }

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * 
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        if (toOn == true) {
            if (mY.startSampling()) {
                mSampling = SAMPLING_ON;
            }
        } else {
            if (mY.stopSampling()) {
                mSampling = SAMPLING_OFF;
            }
        }
    }
    
    
    /**
     * Set a value (if RW) as requested in a JSON RPC message
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
            if (ps.equals("output_rate")) {
                try {
                    if (mY.OUTPUT_RATES.contains( (Double) value)) {
                        mY.setOutputRate( (Double) value);
                        reply.addResult(ps, "status", "ok");
                    } else {
                        reply.addError(ps, BrokerError.E_UNSUPPORTED_VALUE);
                    }
                } catch (Exception e) {
                    mLogger.log("Exception setting output rate: " + e.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                }
            }
        }
    }

    
    @Override
    public void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
        Long timeVal = 0L;    // time to use for the returned data

        // loop through all requested parameters
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            boolean changed;
            // get current requested parameter and make sure it's valid
            Map.Entry<String, Object> entry = iter.next();
            String ps = entry.getKey();
            Object value = entry.getValue();
            if (!checkParameter(ps)) {
                // unsupported, skip it
                reply.addError(ps, BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }
            
            if(mLastReading == null) {
                reply.addError(ps, BrokerError.E_INVALID_DATA);
                return;
            }

            // we have a valid requested parameter, grab the value
            Object newValue = null;
            if(ps.equals("compass_direction"))               { newValue = mLastReading.getCompassDirection(); timeVal=mLastReading.getTimestamp();}
            else if(ps.equals("uncorrected_wind_direction")) { newValue = mLastReading.getUncorrectedWindDirection();  timeVal=mLastReading.getTimestamp();}
            else if(ps.equals("wind_direction"))             { newValue = mLastReading.getWindDirection();  timeVal=mLastReading.getTimestamp();}
            else if(ps.equals("average_wind_speed"))         { newValue = mTenMinuteMeanWindSpeed; timeVal=mLastDbTime;}
            else if(ps.equals("average_wind_dir"))           { newValue = mTenMinuteMeanWindDirectionUnitVector;  timeVal=mLastDbTime;}
            else if(ps.equals("vector_wind_speed"))          { newValue = mTenMinuteMeanVector.getSpeed();  timeVal=mLastDbTime;}
            else if(ps.equals("vector_wind_dir"))            { newValue = mTenMinuteMeanVector.getDirection();  timeVal=mLastDbTime;}
            else if(ps.equals("wind_speed"))                 { newValue = mLastReading.getWindSpeed();  timeVal=mLastReading.getTimestamp();}
            else if(ps.equals("air_temp"))                   { newValue = mLastReading.getAirTemp(); timeVal=mLastReading.getTimestamp();}
            else if(ps.equals("air_pressure"))               { newValue = mLastReading.getAirPressure(); timeVal=mLastReading.getTimestamp();}
            else if(ps.equals("output_rate"))                { newValue = mY.getOutputRateAsDouble(); timeVal=System.currentTimeMillis();}
            
            // NaNs are not allowed in JSON strings
            if (newValue.equals(Double.NaN)) {
                newValue = Double.MIN_VALUE;
            }
                 
            if (value == null){
                changed = true;
            }
            else {
                if (newValue instanceof Double) { changed = !newValue.equals(  (Double) value ); }
                else if (newValue instanceof Integer) { changed = !newValue.equals( (Integer) value ); }
                else if (newValue instanceof Boolean) { changed = !newValue.equals( (Boolean) value ); }
                else { changed = !newValue.equals(value); }
            }
            entry.setValue(newValue);
            reply.addResult(ps, "value", newValue, changed);
            reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(timeVal), changed);
        }
    }

    
    @Override
    public boolean isConnected() {
        if (mY != null) {
            return mY.isConnected();
        } else {
            return false;
        }
    }

    
    /**
     * Insert a row of data into the database.
     */
    protected final void insertData() {
        if ( !Boolean.parseBoolean(mBroker.getProperties().getProperty("db_enabled", "true")) ||
             ( getLogging() != true ) ) {
            return;
        }

        // Make the timestamp to be exactly on the 10-minute boundary
        Calendar c = Calendar.getInstance();
        double dmins = (double)c.get(Calendar.MINUTE);
        double cmins = Math.floor(dmins/10.0)*10.0;
        int mins = (int)(cmins);
        c.set(Calendar.MINUTE, mins);
        c.set(Calendar.SECOND, 0);
        c.set(Calendar.MILLISECOND, 0);
        long t = c.getTimeInMillis();

        // Insert data into 10-minute table
        String table_prefix = mBroker.getProperties().getProperty("db_table_prefix", "bp");
        String cmd = "insert into " + table_prefix + "_wind " +
                "(loc_code, sample_time, speed_scalar, dir_unit_vector, speed_std, " +
                "speed_vector, dir_vector, gust_speed, gust_dir, gust_time, compass_dir, dir_uncorrected, air_temp, air_pressure) " +
                "values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd);

        try {
            pstmt.setString(1, table_prefix);
            pstmt.setTimestamp(2, new Timestamp(t));
            pstmt.setDouble(3, mTenMinuteMeanWindSpeed);
            pstmt.setDouble(4, mTenMinuteMeanWindDirectionUnitVector);
            pstmt.setDouble(5, mTenMinuteMeanWindSpeedStdDev);
            pstmt.setDouble(6, mTenMinuteMeanVector.getSpeed());
            pstmt.setDouble(7, mTenMinuteMeanVector.getDirection());
            pstmt.setDouble(8, mTenMinuteMaxGust.getValue());
            pstmt.setDouble(9, mTenMinuteMaxGust.getMaxDir());
            pstmt.setTimestamp(10, new Timestamp(mTenMinuteMaxGust.getTimestamp().getTimeInMillis()));
            pstmt.setDouble(11, mTenMinuteCompassDir);
            pstmt.setDouble(12, mTenMinuteDirUncorr);
            pstmt.setDouble(13, mTenMinuteMeanAirTemp);
            pstmt.setDouble(14, mTenMinuteMeanAirPressure);
            mBroker.getDb().bufferedExecuteUpdate(pstmt);
            mLastDbTime = t;
        } catch (Exception e) {
            mLogger.log("Insert:" + e.toString(), this.getClass().getName(), LogLevel.ERROR);
            mLogger.log("Exception on insert: " + pstmt.toString(), this.getClass().getName(), LogLevel.DEBUG);
        }
    }

    
    /**
     * Callback from the wind instrument when it has received a valid data reading.
     *
     * @param d - Data reading from the instrument.
     */
    @Override
    public final void onMeasurement(final WindData d) {
        mLastReading = d;
        mLastDataTime = System.currentTimeMillis();
        average(d);
    }

    
    /**
     * Convenience class for Gust.  Just a container for values.
     */
    public class Gust {
        Calendar mTimestamp;
        public Calendar getTimestamp() { return mTimestamp; }
        double mValue;
        public double getValue() { return mValue; }
        double mMaxDir;
        public double getMaxDir() { return mMaxDir; }
        
        public Gust(double value, long timeInMillis, double maxDir) {
            mTimestamp = Calendar.getInstance();
            mTimestamp.setTimeInMillis(timeInMillis);
            mValue = value;
            mMaxDir = maxDir;
        }
    }

    
    /**
     * Container class for wind speed and direction
     */
    public class VectorWindResult {
        double mSpeed;
        public double getSpeed() { return mSpeed; }
        double mDirection;
        public double getDirection() { return mDirection; }
        
        public VectorWindResult(double speed, double direction) {
            mSpeed = speed;
            mDirection = direction;
        }
    }

    
    // Variations on the call to getVectorMeanDirection
    private double getUnitVectorMeanCompassDir(List<WindData> data) {
        return getVectorMeanDirection(data, true, 1).mDirection;
    }

    private double getUnitVectorMeanDirUncorr(List<WindData> data) {
        return getVectorMeanDirection(data, true, 2).mDirection;
    }
    private double getUnitVectorMeanDirection(List<WindData> data) {
        return getVectorMeanDirection(data, true, 3).mDirection;
    }

    private VectorWindResult getVectorMeanDirection(List<WindData> data) {
        return getVectorMeanDirection(data, false, 3);
    }
    
    
    /**
     * Calculate a mean wind direction of whichever variable is specified either
     * using unit vectors or full vectors.
     * 
     * @param data
     * @param asUnit
     * @param whichVar
     * @return 
     */
    private VectorWindResult getVectorMeanDirection(List<WindData> data, boolean asUnit, int whichVar) {
        /*
         * Loop over all wind readings
         */
        double sumVe = 0.0;
        double sumVn = 0.0;
        Iterator<WindData> i = data.iterator();
        while(i.hasNext()) {
            WindData d = i.next();

            double theta;
            // java sin() and cos() require input as radians
            if (whichVar == 1) { theta = Math.toRadians(d.getCompassDirection()); }
            else if(whichVar == 2) { theta = Math.toRadians(d.getUncorrectedWindDirection()); }
            else { theta = Math.toRadians(d.getWindDirection()); }

            double spd = d.getWindSpeed();
            if(asUnit) {
                spd = 1.0;
            }
            sumVe += (Math.sin(theta) * spd);
            sumVn += (Math.cos(theta) * spd);
        }
        double Ve = sumVe/data.size();
        double Vn = sumVn/data.size();
        // atan2() requires radians, convert back to degrees
        double direction;
        direction = Math.toDegrees(Math.atan2(Ve, Vn));
        if(direction < 0.0) {
            direction += 360.0;
        }
        double speed = Math.sqrt(Math.pow(Ve, 2) + Math.pow(Vn, 2));
        return new VectorWindResult(speed, direction);
    }

    
    /**
     * Calculate max 5-second gust over data
     * @param data Data values
     * @param isHourly true if this is for an hour, otherwise 10-min
     */
    private Gust getMaxGust(List<WindData> data) {
        Gust g;
        long startTime = Long.MIN_VALUE;
        int startIndex = 0;
        long curMaxMillis = 0;
        double curMax = 0.0;
        double curMaxDir = 0.0; // although a valid direction, if speed is zero it is meaningless
        
        // loop over all measurements
        for(int i = 0; i < data.size(); i++) {
            // keep track of start time
            long t = data.get(i).getTimestamp();
            if(startTime < 0) {
                startTime = t;
                startIndex = i;
            }
            if((t - startTime) < 5000) {
                // not five seconds yet
                continue;
            }
            // we have a range of 5s
            double total = 0.0;
            int len = i - startIndex;
            for(int j = startIndex;j < i;j++) {
                total += data.get(j).getWindSpeed();
            }
            double mean = total / len;
            if(mean > curMax) {
                // we have a new max
                curMax = mean;
                curMaxMillis = startTime + 2500;
                /*
                 * Calculate the unit average mean direction for the max
                 * gust.
                 */
                List<WindData> x = new ArrayList<WindData>();
                for(int k = startIndex;k < i;k++) {
                    x.add(data.get(k));
                }
                curMaxDir = getUnitVectorMeanDirection(x);
            }
            startTime = Long.MIN_VALUE;
         }
         return new Gust(curMax, curMaxMillis, curMaxDir);
    }

    
    private double std(List<WindData> samples, double m) {
        Iterator<WindData> iter = samples.iterator();
        int n = 0;
        double sum = 0;
        while(iter.hasNext()) {
            WindData d = iter.next();
            double sample = d.getWindSpeed();
            if(!Double.isInfinite(sample) && !Double.isNaN(sample)) {
                sum += Math.pow((sample - m), 2);
                n++;
            }
        }
        if(n > 0) {
            return Math.sqrt(sum / n);
        } else {
            return 0;
        }
    }

    private double getMeanAirTemp(List<WindData> data) {
        double total = 0.0;
        Iterator<WindData> i = data.iterator();
        while (i.hasNext()) {
            WindData d = i.next();
            total += d.getAirTemp();
         }
         double result = (total / data.size());
         return result;
    }

    private double getMeanAirPressure(List<WindData> data) {
        double total = 0.0;
        Iterator<WindData> i = data.iterator();
        while (i.hasNext()) {
            WindData d = i.next();
            total += d.getAirPressure();
         }
         double result = (total / data.size());
         return result;
    }
    
    private double getMeanWindSpeed(List<WindData> data) {
        double total = 0.0;
        Iterator<WindData> i = data.iterator();
        while (i.hasNext()) {
            WindData d = i.next();
            total += d.getWindSpeed();
         }
         double result = (total / data.size());
         return result;
    }

    
    private void resetTenMinuteStats(Calendar now, WindData d) {
        mTenMinuteStart = (Calendar)now.clone();
        mTenMinuteEnd = (Calendar)now.clone();
        mTenMinuteEnd.add(Calendar.MINUTE, 10);
        mTenMinuteWindData.clear();
        mTenMinuteWindData.add(d);
        mTenMinuteMaxGust = null;
    }
    
    
    private void resetAllStats(Calendar now, WindData d) {
        resetTenMinuteStats(now, d);
    }

    
    /**
     * Keep track of averages.
     * @param    d     The sensor data
     */
    private void average(final WindData d) {
        /*
         * Averaging is done based on National Data Buoy Center (NDBC)
         * standards
         */
         Calendar now = Calendar.getInstance();

        /*
         * Averaging is performed over 10-minute segements of the hour,
         * e.g. 0-10, 11-20, etc.
         */
        if(mTenMinuteStart == null) {
            /* This happens at startup.  We don't start recording any data until
             * we cross a 10-minute boundary.
             */
             if((now.get(Calendar.MINUTE) % 10) == 0) {
                 resetAllStats(now, d);
             }
             return;
        }

         /*
         * We are recording data.  Has it been ten minutes since we started
         * recording the current segment?
         */
         if(now.compareTo(mTenMinuteEnd) < 0) {
             // Hasn't been 10 minutes, store the current value and continue
             mTenMinuteWindData.add(d);
             return;
         }

         /*
          * Ten minute segment has elapsed.  NDBC says we must operate at
          * 1hz minimum.  If we don't have enough segements (possibly due to
          * communication or other problems), reset the statistics.
          */
         if(mTenMinuteWindData.size() < 600) {
             /*
              * We don't have enough data for averaging.  There may have been
              * an error or the collection frequency was set too low for NDBC
              * standards
              */
             mLogger.log("NDBC requires >= 600 samples/10 mins, we have " +
                     mTenMinuteWindData.size(), this.getClass().getName(),
                     LogLevel.INFO);
             resetAllStats(now, d);
             return;
         }

         /*
          * Remove NaNs from the data
         */
        Iterator<WindData> i = mTenMinuteWindData.iterator();
        List<WindData> remList = new ArrayList<>();
        while (i.hasNext()) {   // make a list first then remove them to avoid messing up the iterator
            WindData wd = i.next();
            if ( Double.isNaN(wd.getWindSpeed()) || Double.isNaN(wd.getCompassDirection()) ) {
                remList.add(wd);
            }
         }
         mTenMinuteWindData.removeAll(remList);
         
         /*
          * We have recorded for 10 minutes and have enough samples.
          * Calculate the max 5-second gust over the previous 10-minute segment
          */
         mTenMinuteMaxGust = getMaxGust(mTenMinuteWindData);

         mTenMinuteMeanWindSpeed = getMeanWindSpeed(mTenMinuteWindData);    // Calculate mean wind speed over previous 10-minute segment.
         mTenMinuteMeanWindSpeedStdDev = std(mTenMinuteWindData, mTenMinuteMeanWindSpeed);  // Calculate the standard deviation of the wind speed
         mTenMinuteMeanWindDirectionUnitVector = getUnitVectorMeanDirection(mTenMinuteWindData);    // Calculate mean wind direction over previous 10-minute segment.
         mTenMinuteCompassDir = getUnitVectorMeanCompassDir(mTenMinuteWindData);
         mTenMinuteDirUncorr = getUnitVectorMeanDirUncorr(mTenMinuteWindData);
         mTenMinuteMeanVector = getVectorMeanDirection(mTenMinuteWindData); // Calculate mean wind vector speed/direction over previous 10-minute segment
         mTenMinuteMeanAirTemp = getMeanAirTemp(mTenMinuteWindData);
         mTenMinuteMeanAirPressure = getMeanAirPressure(mTenMinuteWindData);
         
         /*
          * Add to queue of the last 6 10-min segments.  If we have accumulated
          * six readings, we have enough to do hourly stats.
          */
         mHourlyWindSpeeds.add(new Double(mTenMinuteMeanWindSpeed));
         if(mHourlyWindSpeeds.size() == 6) {

            /*
             * Dequeue the oldest reading.  NDBC wants hourly readings ever
             * 10 minutes, i.e. the most recent hour.
             */
            mHourlyWindSpeeds.remove();


            /*
             * Store the data in the database.
             */
            insertData();

            /*
             * start over
             */
            resetAllStats(now, d);
         } else {
             /*
              * Store the 10-minute segment of data.
              */
             insertData();

             /*
              * Start over with a new 10-minute segment of data
              */
             resetTenMinuteStats(now, d);
        }
    }

}
