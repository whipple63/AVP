package edu.unc.ims.avp.adapters;

import java.util.Properties;
import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokerError;
import edu.unc.ims.instruments.aio.JAccessIO;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import org.json.JSONObject;
import edu.unc.ims.avp.Logger.LogLevel;
import java.sql.Timestamp;

/**
Adapts from BrokeredDevice to the Access IO card.
The following configuration file properties are honored, with defaults:
<pre>
# Base address for AIO card communication (set with jumpers).  Value should
# be a hexidecimal value.
AioAdapter_base_address 220
# Direction of digital I/O ports.  8-bit string, 0=output, 1=input.
# Only honored if AioAdapter_set_direction=true.
AioAdapter_set_direction false
AioAdapter_port_a_dir 00000000
AioAdapter_port_b_dir 00000000
AioAdapter_port_c_lo_dir 0000
AioAdapter_port_c_hi_dir 0000
# Value of (output) digital I/O ports.  8-bit string of 1's and 0's.  Pins
# set as input pins ignored.  Only honored if AioAdapter_set_value=true.
AioAdapter_set_value false
AioAdapter_port_a_value 10000000
AioAdapter_port_b_value 00000000
AioAdapter_port_c_value 00000000
# Broker control port.  A single controller may connect and issue control
# commands to the broker.
AioAdapter_ctrl_port 8878
# Run in simulator mode (0 = no simulate, 1 = simulate)
AioAdapter_simulate 0
</pre>
*/
public class AioAdapter extends BrokerAdapter {
    class AioData {
        public int [] mPort = new int[3];
        public double [] mAdc = new double[8];

        public void cacheAll() throws Exception {
            for(int i=0;i<3;i++) {
                mPort[i] = JAccessIO.getPort(mBase, i);
            }
            for(int c = 0; c < 8; c++) {
                mAdc[c] = JAccessIO.getVoltage(mBase, c, 0, 1);
            }
        }

        public String toString() {
            StringBuffer sb = new StringBuffer(128);
            for(int i=0;i<3;i++) {
                sb.append("port " + ('a'+i) + "=" + Integer.toBinaryString(
                    mPort[i]) + "\n");
            }
            for(int c = 0; c < 8; c++) {
                sb.append("ADC channel " + c + "=" + mAdc[c] + "\n");
            }
            return sb.toString();
        }
    }

    /**
    Base address.
    This is the base address of the AccesIO card, e.g. 0x220.
    */
    private int mBase;

    
    public AioAdapter(final Broker broker) {
        mBroker = broker;
    }
    
    /**
    Initialize the device.
    @throws Exception   on error
    */
    public final void connect() throws Exception {
        mLogger.log("Start AccesIO (digital I/O) broker", this.getClass().getName(),  LogLevel.INFO);

        // Load dynamic library
        if(!mSimulate) {
            System.loadLibrary("JAccessIO");
            mLogger.log("JAccessIO Library successfully loaded", this.getClass().getName(), LogLevel.DEBUG);
        }

        // Initialize user options (depends on JAccessIO being loaded)
        initUserOptions(mBroker.getProperties());
    }

    /**
    Free up any resources prior to destruction.
    @throws Exception   on error.
    */
    public final void disconnect() throws Exception {
    }

    public int getMinSubInterval() {
      return MIN_SUB_INTERVAL;
    }


    private boolean cacheExpired() {
        long currentTime = System.currentTimeMillis();
        long age = currentTime - mLastUpdate;
        return (age > MIN_SUB_INTERVAL);
    }

    /**
    Attempt a soft reset.
    @throws Exception   on error.
    */
    @Override
    public final void softReset() throws Exception {
    }

    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * This is meaningless here.  Sampling is considered always on.
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        mSampling = SAMPLING_ON;
    }
    
    
    public void extendedMethod(String method, JSONObject request) {
    }

    public void extendedReply(String method, HashMap<String, Object> results,
        HashMap<String, Boolean> changed) {
    }

    @Override
    public void put(HashMap<String,Object> params, BrokerMessage reply) {
        // loop through all requested parameters
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            // get current requested parameter and make sure it's valid
            Map.Entry<String, Object> param = iter.next();
            String ps = param.getKey();
            Object value = param.getValue();
            if (!checkParameter(ps)) {
                // unsupported, skip it
                reply.addError(ps, BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }
            if (ps.equals("function")) {
                reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
                continue;
            }
            if (JSONParameters.get(ps)[TYPE_INDEX].equals("RO")) {
                reply.addError(ps, BrokerError.E_SET_PARAM_RO);
                continue;
            }
            if (JSONParameters.get(ps)[TYPE_INDEX].equals("NI")) {
                reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
                continue;
            }
        
            // we have a valid requested parameter, set the value
            String [] fields = null;
            if(ps.startsWith("pin_")) {
                fields = ps.split("_");
                int port = fields[1].charAt(0) - 'a';
                int pin = Integer.parseInt(fields[2]);
                int newValue = ((Double)value).intValue();
                try {
                    if(!mSimulate) {
                        JAccessIO.putPin(mBase, port, pin, newValue);
                        reply.addResult(ps, "status", "OK", true);
                    } else {
                        System.out.println("would set "+ps+" to " + newValue);
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        }
//        reply.addTimestamp(System.currentTimeMillis());   is this used during set?
    }

    public void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
        // update the internal values if time
        synchronized(this) {
            if(cacheExpired()) {
                try {
                    mCache.cacheAll();
                    mLastUpdate = System.currentTimeMillis();
                } catch(Exception e) {
                    mLogger.log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                }
            }
        }

        // loop through all requested parameters
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            boolean changed = true;
            // get current requested parameter and make sure it's valid
            Map.Entry<String, Object> param = iter.next();
            String ps = param.getKey();
            Object lastO = param.getValue();
            if (!checkParameter(ps)) {
                // unsupported, skip it
                reply.addError(BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                continue;
            }
            // we have a valid requested parameter, grab the value
            Object newValue = null;
            String [] fields = null;
            if(ps.startsWith("pin_")) {
                fields = ps.split("_");
                int port = fields[1].charAt(0) - 'a';
                int pin = Integer.parseInt(fields[2]);
                try {
                    if(!mSimulate) {
                        newValue = Double.valueOf((mCache.mPort[port] >>> pin) & 1);
                    } else {
                        newValue = Double.valueOf(1);
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            } else if(ps.startsWith("adc_")) {
                fields = ps.split("_");
                int channel = Integer.parseInt(fields[1]);
                try {
                    if(!mSimulate) {
                        newValue = Double.valueOf(mCache.mAdc[channel]);
                    } else {
                        newValue = Double.valueOf(9.98);
                    }
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
            if(lastO instanceof Double) {
                double oldValue = ((Double)lastO).doubleValue();
                changed = !newValue.equals(oldValue);
            } else {
                changed = true;
            }
            param.setValue(newValue);
            reply.addResult(ps, "value", newValue, changed);
            reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(mLastUpdate), changed);
        }
    }

    public boolean isConnected() {
        return true;
    }
    private static final String[] arrayOf(String a, String b) {
        String[] rv = {a, b};
        return rv;
    }

    private Broker mBroker;

    static {
        JSONParameters.put("pin_a_0", arrayOf("binary", "RW"));
        JSONParameters.put("pin_a_1", arrayOf("binary", "RW"));
        JSONParameters.put("pin_a_2", arrayOf("binary", "RW"));
        JSONParameters.put("pin_a_3", arrayOf("binary", "RW"));
        JSONParameters.put("pin_a_4", arrayOf("binary", "RW"));
        JSONParameters.put("pin_a_5", arrayOf("binary", "RW"));
        JSONParameters.put("pin_a_6", arrayOf("binary", "RW"));
        JSONParameters.put("pin_a_7", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_0", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_1", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_2", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_3", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_4", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_5", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_6", arrayOf("binary", "RW"));
        JSONParameters.put("pin_b_7", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_0", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_1", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_2", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_3", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_4", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_5", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_6", arrayOf("binary", "RW"));
        JSONParameters.put("pin_c_7", arrayOf("binary", "RW"));
        JSONParameters.put("adc_0", arrayOf("volts", "RO"));
        JSONParameters.put("adc_1", arrayOf("volts", "RO"));
        JSONParameters.put("adc_2", arrayOf("volts", "RO"));
        JSONParameters.put("adc_3", arrayOf("volts", "RO"));
        JSONParameters.put("adc_4", arrayOf("volts", "RO"));
        JSONParameters.put("adc_5", arrayOf("volts", "RO"));
        JSONParameters.put("adc_6", arrayOf("volts", "RO"));
        JSONParameters.put("adc_7", arrayOf("volts", "RO"));
    } 

    /**
    Reads and sets user options from configuration.
    @param  p   Properties from user config file.
    */
    private void initUserOptions(final Properties p) throws Exception {
        String pre = mBroker.getAdapterName() + "_";

        // Get the base address for the AccesIO card
        String s = p.getProperty(pre + "base_address", "220");
        mBase = Integer.parseInt(s, 16);
        mLogger.log("Setting base address to 0x" + s + " (" + mBase + ")",
            this.getClass().getName(),  LogLevel.DEBUG);

        /* Does user want us to set port directions?  If yes and if the
         * direction is not already consistent with their desire, reset the
         * directions.
         * requested will be filled with 0 or 1 meaning output or input for
         * a, b, c_lo and c_hi, respectively
         */
        int [] requested = { 0, 0, 0, 0};
        if(p.getProperty(pre + "set_direction", "false").equals("true")) {
            // load requested from configuration file
            boolean needChange = false;
            StringBuffer msg = new StringBuffer(128);
            msg.append("Current port directions:");
            String [] ids = { "a", "b", "c_lo", "c_hi" };
            for(int i=0;i<4;i++) {
                String id = pre + "port_" + ids[i] + "_dir";
                requested[i] = Integer.parseInt(p.getProperty(id, "0"));
                int dir = JAccessIO.getPortDirection(mBase, i);
                msg.append("Port " + ids[i] + " is currently set to " + dir +
                        "\n");
                if(requested[i] != dir) {
                    needChange = true;
                }
            }
            mLogger.log(msg.toString(), this.getClass().getName(), LogLevel.DEBUG);
            if(needChange) {
                mLogger.log("Changing direction", this.getClass().getName(),
                        LogLevel.DEBUG);
                JAccessIO.setDirection(mBase, requested[0], requested[1],
                        requested[2], requested[3]);
            } else {
                mLogger.log("No direction change necessary",
                        this.getClass().getName(), LogLevel.DEBUG);
            }
        } else {
            mLogger.log("User requested not to change port directions",
                this.getClass().getName(), LogLevel.DEBUG);
        }

        /* Does user want us to set port values?  If yes and if the value is
         * not already set correctly, set it.
         */
        if(p.getProperty(pre + "set_value", "false").equals("true")) {
            // load requested from configuration file
            boolean needChange = false;
            for(char pc = 'a'; pc < 'd'; pc++) {
                String id = pre + "port_" + pc + "_value";
                int idx = pc - 'a';
                requested[idx] = Integer.parseInt(p.getProperty(id, "00000000"), 2);
                mLogger.log("User requested " + id + " set to "
                        + Integer.toBinaryString(requested[idx]),
                        this.getClass().getName(), LogLevel.DEBUG);
                int cur = JAccessIO.getPort(mBase, idx);
                mLogger.log("Current value of " + id + " set to "
                        + Integer.toBinaryString(cur),
                        this.getClass().getName(), LogLevel.DEBUG);
                if(requested[idx] != cur) {
                    JAccessIO.putPort(mBase, idx, requested[idx]);
                    mLogger.log("Setting " + id + " to "
                        + Integer.toBinaryString(requested[idx]),
                        this.getClass().getName(), LogLevel.DEBUG);
                } else {
                    mLogger.log("Port " + id + " requires no change ",
                        this.getClass().getName(), LogLevel.DEBUG);
                }
            }
        } else {
            mLogger.log("User requested not to change port values",
                this.getClass().getName(), LogLevel.DEBUG);
        }
    }

    /**
    Simulation.
    True if we should simulate, false if we should load the dynamic library
    and make real calls.  This is useful for testing without the jni library
    on the development platform.
    */
    private boolean mSimulate = false;
    private static final int MIN_SUB_INTERVAL = 100;
    private AioData mCache = new AioData();
    private long mLastUpdate = 0;
    public Timestamp getLastDataTime() { return new Timestamp(mLastUpdate); }
    public Timestamp getLastDbTime() { return new Timestamp(0); }   // no database
}
