package edu.unc.ims.avp.adapters;

import java.util.Properties;
import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokerError;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import org.json.JSONObject;
import edu.unc.ims.avp.Logger.LogLevel;
import java.lang.reflect.Constructor;
import java.sql.Timestamp;
import edu.unc.ims.instruments.IO.*;

/**
Adapts from BrokeredDevice to Pi Plates.
The following configuration file properties are honored, with defaults:
<pre>

* </pre>
*/
public class IOAdapter extends BrokerAdapter {
    private final Broker mBroker;
    private static final int MIN_SUB_INTERVAL = 100;
    @Override public Timestamp getLastDataTime() { return new Timestamp(mIO.getIOTimeStamp()); }
    @Override public Timestamp getLastDbTime() { return new Timestamp(0); }   // no database
    private IOInstrument mIO;
    String mHost;   // host and port for future instruments
    int mPort;


    public IOAdapter(final Broker broker) throws Exception {
        mBroker = broker;
        
        String adapterName = getClass().getName().substring(getClass().getName().lastIndexOf('.')+1);
        mHost = mBroker.getProperties().getProperty(adapterName + "_inst_host", "localhost");
        mPort = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_inst_port", "55999"));
        
        
        // Load the instrument class
        Class<?> c = ClassLoader.getSystemClassLoader().loadClass(mBroker.getProperties().getProperty("instrument_class"));
        Constructor cst = c.getDeclaredConstructor(String.class, int.class, Broker.class);
        mIO = (IOInstrument)cst.newInstance(mHost, mPort, mBroker);
        
        // Set up JSONParameters
        int n = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_relays"));
        for (int i=0; i<n; i++ ) {
            JSONParameters.put("relay_"+i, arrayOf("binary", "RW"));
        }
        n = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_dout"));
        for (int i=0; i<n; i++ ) {
            JSONParameters.put("dout_"+i, arrayOf("binary", "RW"));
        }
        n = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_din"));
        for (int i=0; i<n; i++ ) {
            JSONParameters.put("din_"+i, arrayOf("binary", "RO"));
        }
        n = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_ain"));
        for (int i=0; i<n; i++ ) {
            JSONParameters.put("ain_"+i, arrayOf("volts", "RO"));
        }
        n = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_pwm"));
        for (int i=0; i<n; i++ ) {
            JSONParameters.put("pwm_"+i, arrayOf("binary", "RW"));
        }
        n = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_aout"));
        for (int i=0; i<n; i++ ) {
            JSONParameters.put("aout_"+i, arrayOf("volts", "RW"));
        }
    }
    
    /**
    Initialize the device.
    @throws Exception   on error
    */
    public final void connect() throws Exception {
        mLogger.log("Starting Analog-Digital I/O broker", this.getClass().getName(),  LogLevel.INFO);
        mIO.connect();
        
        Properties p = mBroker.getProperties();
        String pre = mBroker.getAdapterName() + "_";

        // Set initial port values if requested
        if(p.getProperty(pre + "set_value", "false").equals("true")) {
            // load requested values from configuration file
            int v=Integer.parseInt(p.getProperty(pre + "relay_value", "00000000"), 2);
            mLogger.log("Setting user requested relay value of " + Integer.toBinaryString(v),
                    this.getClass().getName(), LogLevel.DEBUG);
            mIO.setAllRelays(v);
            
            v=Integer.parseInt(p.getProperty(pre + "dout_value", "00000000"), 2);
            mLogger.log("Setting user requested digital output value of " + Integer.toBinaryString(v),
                    this.getClass().getName(), LogLevel.DEBUG);
            mIO.setAllDOut(v);
        } else {
            mLogger.log("User requested not to change port values",
                this.getClass().getName(), LogLevel.DEBUG);
        }
    }

    @Override
    public boolean isConnected() {
        return mIO.isConnected();
    }
    
    /**
    Free up any resources prior to destruction.
    @throws Exception   on error.
    */
    @Override
    public final void disconnect() throws Exception {
    }

    @Override
    public int getMinSubInterval() {
      return MIN_SUB_INTERVAL;
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
            fields = ps.split("_");
            String fn = fields[0];
            int pin = Integer.parseInt(fields[1]);
            int newValue = ((Double)value).intValue();
            try {
                if (fn.equals("relay")) {
                    mIO.setRelay(pin, newValue);
                } else
                if (fn.equals("dout")) {
                    mIO.setDOut(pin, newValue);
                } else
                if (fn.equals("pwm")) {
                    mIO.setPWM(pin, newValue);
                } else
                if (fn.equals("aout")) {
                    mIO.setAOut(pin, newValue);
                }                       
                reply.addResult(ps, "status", "OK", true);
            } catch (Exception e) {
                e.printStackTrace();    // shouldn't really happen
            }
        }
    }

    public void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
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
            fields = ps.split("_");
            String fn = fields[0];
            int pin = Integer.parseInt(fields[1]);
            if (fn.equals("relay")) {
                newValue = mIO.getRelay(pin);
            } else
            if (fn.equals("dout")) {
                newValue = mIO.getDOut(pin);
            } else
            if (fn.equals("din")) {
                newValue = mIO.getDIn(pin);
            } else
            if (fn.equals("ain")) {
                newValue = mIO.getAIn(pin);
            } else
            if (fn.equals("pwm")) {
                newValue = mIO.getPWM(pin);
            } else
            if (fn.equals("aout")) {
                newValue = mIO.getAOut(pin);
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
            reply.addResult(ps, "sample_time", BrokerMessage.tsValue(mIO.getIOTimeStamp()), changed);
        }
    }

    
    private static String[] arrayOf(String a, String b) {
        String[] rv = {a, b};
        return rv;
    }

}
