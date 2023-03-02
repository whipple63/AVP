package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokeredDeviceListener;
import edu.unc.ims.instruments.motionmind3.MM3;
import java.io.IOException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;
import org.json.JSONObject;
import org.json.JSONException;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.avp.BrokerError;
import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import java.sql.Timestamp;
import edu.unc.ims.avp.IoClient;

/**
Adapts from BrokeredDevice to the Young 32500 compass/wind device.
 */
public class MotionMind3Adapter extends BrokerAdapter {

    /**
    The motor controller device class.
     */
    private MM3 mMM3;
    /**
    Default P term.
     */
    private int mDefaultPTerm = 20000;
    /**
    Default I term.
     */
    private int mDefaultITerm = 20;
    /**
    Default D term.
     */
    private int mDefaultDTerm = 0;
    /**
    Reference to the controlling Broker.
     */
    private Broker mBroker;
//
//    /**
//    Adapter states.
//     */
//    /**
//    Disconnected state.
//     */
//    private static final int S_DISCONNECTED = 0;
//    /**
//    Connected, not initialized state.
//     */
//    private static final int S_CONNECTED = 1;
//    /**
//    Initialized state.
//     */
//    private static final int S_INITIALIZED = 2;
//    /**
//    Processing.
//     */
//    private static final int S_PROCESSING = 3;
    private static final int MIN_SUB_INTERVAL = 500;
    /**
    Constants for the position of the "return position", "return veolocity", and
    "return time" bits within the 16-bit function register.

    The output format is more complicated when these functions are on, so
    we make sure they are off and stay off.
     */
    private static final int RETPOS_POS = 1;
    private static final int RETVEL_POS = 2;
    private static final int RETTIME_POS = 3;
    private static final int RETPOS_MASK = 1 << RETPOS_POS;
    private static final int RETVEL_MASK = 1 << RETVEL_POS;
    private static final int RETTIME_MASK = 1 << RETTIME_POS;
    
    public MotionMind3Adapter(final Broker broker) {
        mBroker = broker;
    }
    
    /**
    Initialize the device.
    @throws Exception   on error
     */
    public synchronized final void connect() throws Exception {
        // First thing we do is turn on the power (for mm3 this is actually a reset
        // that operates when grounded with setPower(false), so we set to true)
        setPower(true);
        
        // Second, we need to be certain that the limit switch start enabled
//        if (mAioBrokerHost != null) {
//            IoClient aio = new IoClient(mAioBrokerHost, mAioBrokerPort);
//            aio.switchPin('b', 3, false);   // pin b3 to 0=false=not set
//            aio.shutdown();
//        }


        String host = mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_host", "localhost");
        int port = Integer.parseInt(mBroker.getProperties().getProperty(mBroker.getAdapterName() + "_port", "55232"));
        mLogger.log("Using tcp socket to connect to MM3.", "MotionMind3Adapter", LogLevel.INFO);
        mMM3 = new MM3(host, port);

        mLogger.log("Using binary mode to connect to MM3.", "MotionMind3Adapter", LogLevel.INFO);
        mMM3.connect();
        mLogger.log("Connected to MotionMind3", "MotionMind3Adapter", LogLevel.INFO);

        setPIDTerms(mBroker.getProperties().getProperty("p_term", Integer.toString(mDefaultPTerm)),
                mBroker.getProperties().getProperty("i_term", Integer.toString(mDefaultITerm)),
                mBroker.getProperties().getProperty("d_term", Integer.toString(mDefaultDTerm)));
        turnOffRetPVT();
        mLogger.log("MotionMind3 PID terms set.", "MotionMind3Adapter", LogLevel.INFO);
        
        // could put these values in the config file
        setSampling(true);  // always sampling
        setLogging(false);   // never logging
    }

    
    /**
    Sets the PID terms.
    @param  ps p-term
    @param  is i-term
    @param  ds d-term
    @throws Exception on error.
     */
    private void setPIDTerms(final String ps, final String is, final String ds)
            throws Exception {
        int p = Integer.parseInt(ps);
        int i = Integer.parseInt(is);
        int d = Integer.parseInt(ds);
        if ((p < 0) || (p > 65535)) {
            return;
        }
        if ((i < 0) || (i > 65535)) {
            return;
        }
        if ((d < 0) || (d > 65535)) {
            return;
        }
        mLogger.log("Setting MotionMind3 PID terms to: "
                + "P: " + p + " I: " + i + " D: " + d, "MotionMind3Adapter",
                LogLevel.INFO);
//        try {
        mMM3.setPIDTerms(p, i, d);
//        } catch (Exception e) {
//            mLogger.log(e.toString(),
//                    this.getClass().getName(), LogLevel.ERROR);
//        }

    }

    /**
    Turns off MM3 functions that return position, velocity, and time. This
    method ensures MM3 replies are in the expected format.
    @throws Exception in case of I/O or other low-level errors.
     */
    // TODO: this probably wouldn't work if RetPVT were set, because the output from readRegister will not be clean
    private void turnOffRetPVT() throws Exception {
        int currentValue, nextValue;
        currentValue = mMM3.readRegister("function");
        nextValue = currentValue & ~RETPOS_MASK & ~RETVEL_MASK
                & ~RETTIME_MASK;
        boolean result = mMM3.write("function", nextValue);
        if (result) {
            mLogger.log("MotionMind3 function register set.",
                    "MotionMind3Adapter", LogLevel.INFO);
        } else {
            mLogger.log("MotionMind3 failed to set function register.",
                    "MotionMind3Adapter", LogLevel.INFO);
        }
    }

    /**
    Free up any resources prior to destruction.
    @throws Exception   on error.
     */
    public final void disconnect() throws Exception {
        if ( mMM3 != null && isConnected()) {
            mMM3.disconnect();
        }
    }

    public int getMinSubInterval() {
        return MIN_SUB_INTERVAL;
    }


    /**
    allows methods with non-standard JSON reply formats to be serviced.

    Since there are no such methods for this broker, calls to this method result
    in an error being sent over the JSON socket.

    @param method String representation of the method.
    @param request The original JSON request.
     */
    public void extendedMethod(String method, JSONObject request,
            BrokeredDeviceListener listener) throws Exception {
        BrokerMessage reply = new BrokerMessage(method);
        try {
            reply.setId(request.getInt("id"));
        } catch (JSONException j1) {
        }
        if (method.equals("restore")) {
            try {
                restore();
            } catch (Exception e) {
                reply.addError(BrokerError.E_EXCEPTION, e.getMessage());
                mLogger.log("Exception when sending restore: " + e.getMessage(),
                        this.getClass().getName(), LogLevel.ERROR);
            }
        } else if (method.equals("reset")) {
            try {
                softReset();
            } catch (Exception e) {
                reply.addError(BrokerError.E_EXCEPTION, e.getMessage());
                mLogger.log("Exception when sending softReset: "
                        + e.getMessage(),
                        this.getClass().getName(), LogLevel.ERROR);

            }
        } else {
            reply.addError(BrokerError.E_UNSUPPORTED_METHOD);
            mLogger.log("Unsupported extended method.",
                    this.getClass().getName(), LogLevel.ERROR);
        }
        try {
            listener.onData(reply.toJSONResponse());
        } catch (JSONException j2) {
            mLogger.log("JSONException when sending unsupported method error: " + j2.getMessage(),
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }

    /**
    Attempt a soft reset.
    @throws Exception   on error.
     */
    public final void softReset() throws Exception {
        mMM3.reset();
    }

    /**
    Attempt a restore.
    @throws Exception   on error.
     */
    public final void restore() throws Exception {
        mMM3.restore();
    }

    public final boolean isConnected() {
        if (mMM3 != null) {
            return mMM3.isConnected();
        } else { return false; }
    }
    private String[] cache = new String[32];
    private long lastUpdate = 0;

    private HashMap<String, Object> regLocation(String ps) {
        HashMap<String, Object> retval = new HashMap<String, Object>();
        int index;
        if (checkParameter(ps)) {
            index = getFieldIndex(ps);
//            Logger.getLogger().log("Got field index " + index
//                    + " for parameter " + ps + ".", this.getClass().getName(),
//                    Logger.LogLevel.DEBUG);
            if (index < getFieldIndex("pos_pwr_up")) {
                retval.put("register", ps);
                retval.put("position", index);
                retval.put("sub", false);
            } else if (index < getFieldIndex("freq_div2")) {
                retval.put("register", "function");
                retval.put("position", index - getFieldIndex("pos_pwr_up"));
                retval.put("sub", true);
            } else if (index < getFieldIndex("neg_limit_switch")) {
                retval.put("register", "function2");
                retval.put("position", index - getFieldIndex("freq_div2"));
                retval.put("sub", true);
            } else {
                retval.put("register", "status");
                retval.put("position", index - getFieldIndex("neg_limit_switch"));
                retval.put("sub", true);
            }
        }
        return retval;
    }
    int shouldWait = 0;
    static final int DEFAULT_SLEEPTIME = 100;

    public void get(HashMap<String, Object> params, BrokerMessage reply) {
        while (shouldWait > 0) {
            try {
                Thread.sleep(DEFAULT_SLEEPTIME);
            } catch (InterruptedException ie) {
                Logger.getLogger().log(
                        "Interrupted exception during get sleep.", this.getClass().
                        toString(),
                        LogLevel.INFO);
            }
        }
        shouldWait++;
        sGet(params, reply);
        shouldWait--;
    }

    public synchronized void sGet(HashMap<String, Object> params,
            BrokerMessage reply) {
        boolean toe, ioe, use;
        String rs = "";
        toe = false;
        ioe = false;
        use = false;
        String[] fields;
//        Iterator iter;
        String ps;
        HashMap<String, Object> location = new HashMap<String, Object>();
        boolean changed;
        double newValue;
        int position;
        boolean sub; // is this a subregister (single bit) of a full register
        String register;
        Object lastO;
        HashMap<String, Integer> results = new HashMap<String, Integer>();
        Iterator<String> iter1 = params.keySet().iterator();
        while (iter1.hasNext()) {
            ps = iter1.next();
            location = regLocation(ps);
            if (!location.isEmpty()) {
//                    Logger.getLogger().log("Adding register " + location.get(
//                            "register") + " to results.",
//                            this.getClass().getName(),
//                            Logger.LogLevel.DEBUG);
                results.put((String) location.get("register"),
                        new Integer(0));
            }
        }
//        reply.addTimestamp(System.currentTimeMillis());
        try {
//                Logger.getLogger().log("Calling mMM3.read.", this.getClass().
//                        getName(),
//                        Logger.LogLevel.DEBUG);
            mMM3.read(results);
//                Logger.getLogger().log(
//                        "Returned from mMM3.read without exception.", this.
//                        getClass().
//                        getName(),
//                        Logger.LogLevel.DEBUG);
            Iterator<Map.Entry<String, Object>> iter2 = params.entrySet().
                    iterator();
            while (iter2.hasNext()) {
                Map.Entry<String, Object> entry = iter2.next();
                ps = entry.getKey();
                location = regLocation(ps);
                lastO = entry.getValue();
                if (location.isEmpty()) {
                    reply.addError(ps,
                            BrokerError.E_UNSUPPORTED_STATUS_PARAM);
                    continue;
                }
                register = (String) location.get("register");
                position = (Integer) location.get("position");
                sub = (Boolean) location.get("sub");
                if (sub) {
                    newValue = (results.get(register) >> position) & 0x01;
                } else {
                    if (ps.equals("amps") || ps.equals("amps_limit")) {
                        newValue = results.get(ps) * 20;
                    } else if (ps.equals("temperature")) {
                        newValue = (results.get(ps) - 1104) * -.165;
                    } else {
                        newValue = results.get(ps);
                    }
                }
                if (lastO instanceof Double) {
                    double oldValue = ((Double) lastO).doubleValue();
                    changed = oldValue != newValue;
                } else {
                    changed = true;
                }
                entry.setValue(Double.valueOf(newValue));
//                    Logger.getLogger().log("Adding result (" + ps + " : "
//                            + newValue + ") to reply.", this.getClass().
//                            getName(),
//                            Logger.LogLevel.DEBUG);
                reply.addResult(ps, "value", newValue, changed);
                reply.addResult(ps, "units", JSONParameters.get(ps)[UNITS_INDEX], changed, true);   // forVerbose
                reply.addResult(ps, "sample_time", BrokerMessage.tsValue(mMM3.mLastReadTime), changed);
            }
        } catch (Exception e) {
            if (e instanceof TimeoutException) {
                reply.addError(BrokerError.E_TIMEOUT);
                Logger.getLogger().log("mMM3.read timed out.", this.getClass().
                        getName(),
                        Logger.LogLevel.DEBUG);
            } else if (e instanceof IOException) {
                reply.addError(BrokerError.E_IO);
                Logger.getLogger().log("mMM3.read got IO exception.", this.
                        getClass().
                        getName(),
                        Logger.LogLevel.DEBUG);
            } else if (e instanceof UnsupportedStateException) {
                reply.addError(BrokerError.E_CONNECTION);
                Logger.getLogger().log(
                        "mMM3.read got unsupported state exception.", this.
                        getClass().
                        getName(),
                        Logger.LogLevel.DEBUG);
            } else {
                reply.addError(BrokerError.E_EXCEPTION);
                Logger.getLogger().log("mMM3.read got exception: " + e.
                        getMessage(), this.getClass().
                        getName(),
                        Logger.LogLevel.DEBUG);
            }
        }
    }

    public void put(HashMap<String, Object> params, BrokerMessage reply) throws Exception {
        shouldWait++;
        sPut(params, reply);
        shouldWait--;
    }

    /**
    Adapter method to set parameters on the instrument. An Iterator processes
    the parameter HashMap (of parameter names and values). For each parameter,
    putSingle is called with the parameter, value, and BrokerReply as arguments.
    The BrokerReply is updated with errors if they occur.
    @param params A HashMap of parameters and their requested values.
    @param reply The running BrokerReply for this JSON request.
     */
    public synchronized void sPut(HashMap<String, Object> params,
            BrokerMessage reply) throws Exception {
        boolean write_store = false;
        
        // Check for the write_store param.  Set a flag and remove it
        // from the hash map.
        if (params.containsKey("write_store")) {
            write_store = (Boolean) params.get("write_store");
            params.remove("write_store");
        }
            
        Iterator<Map.Entry<String, Object>> iter = params.entrySet().iterator();
        while (iter.hasNext()) {
            Map.Entry<String, Object> entry = iter.next();
            String ps = entry.getKey();
            Object o = entry.getValue();
            if (o instanceof Double) {
                double value = ((Double) o).doubleValue();
                if (!checkParameter(ps)) {
                    reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
                } else {
                    putSingle(ps, (int) value, write_store, reply);
                }
            } else {
                reply.addError(ps, BrokerError.E_BAD_COMMAND); //TODO: bad value error
            }
        }
    }

    /**
    Set a single parameter.

    MotionMind3 parameters are divided into write, function, function2,
    moveAt, moveRel, and moveAbs methods.

    Modifies parameter values for "amps" and "amps_limit" to allow operator
    to specify milliamps rather than digital counts.

    @param ps String representation of the parameter to be set.
    @param value Value that the parameter will be set to.
    @param reply The running BrokerReply for this JSON request.
     */
    private void putSingle(String ps, int value, boolean write_store, BrokerMessage reply) throws Exception {
        if (ps.equals("function")) {
            long op = RETPOS_MASK | RETVEL_MASK | RETTIME_MASK;
            if ((value & op) > 0) {
                reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
                return;
            }
        }
        if (JSONParameters.get(ps)[TYPE_INDEX].equals("RO")) {
            reply.addError(ps, BrokerError.E_SET_PARAM_RO);
            return;
        }
        if (JSONParameters.get(ps)[TYPE_INDEX].equals("NI")) {
            reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
            return;
        }
        if (JSONParameters.get(ps)[TYPE_INDEX].equals("RW") && (getFieldIndex(ps) >= getFieldIndex(
                "position")) && (getFieldIndex(ps) <= getFieldIndex(
                "temperature"))) {
            if (ps.equals("amps") || ps.equals("amps_limit")) {
                value = (int) Math.floor(value / 20);
            }
            write(ps, value, write_store, reply);
            return;
        }
        if ((getFieldIndex(ps) >= getFieldIndex("pos_pwr_up")) && (getFieldIndex(
                ps) <= getFieldIndex("disable_blink"))) {
            function(ps, value, write_store, reply);
            return;
        }
        if ((getFieldIndex(ps) >= getFieldIndex("freq_div2")) && (getFieldIndex(
                ps) <= getFieldIndex(
                "over_temp"))) {
            function2(ps, value, write_store, reply);
            return;
        }
        if (ps.equals("move_at")) {
            moveAt(value, reply);
            return;
        }
        if (ps.equals("move_to_rel")) {
            moveRel(value, reply);
            return;
        }
        if (ps.equals("move_to_absolute")) {
            moveAbs(value, reply);
            return;
        }
        reply.addError(ps, BrokerError.E_UNSUPPORTED_SET_PARAM);
        return;
    }

    /**
    Writes a setting to the Motion Mind 3.
    @param ps String representation of the parameter to be set.
    @param value The value the parameter will be set to.
    @param reply The running reply for the request.
     */
    private void write(String ps, int value, boolean write_store, BrokerMessage reply) throws Exception {
        try {
            boolean res;
            if (write_store) {
                res = mMM3.writeStore(ps, value);
            } else {
                res = mMM3.write(ps, value);
            }
            if (res) {
                reply.addResult(ps, "status", "ok");
            } else {
                reply.addError(ps, BrokerError.E_INST_RESPONSE);
                mLogger.log("Unexpected instrument response on write, parameter: "
                        + ps + ", value: " + value + ".",
                        this.getClass().getName(),
                        LogLevel.WARN);
            }
        } catch (TimeoutException te) {
            reply.addError(ps, BrokerError.E_TIMEOUT);
            mLogger.log("Timeout occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (IOException ioe) {
            reply.addError(ps, BrokerError.E_IO);
            mLogger.log("IO exception occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (UnsupportedStateException use) {
            reply.addError(ps, BrokerError.E_CONNECTION);
            mLogger.log("Unsupported state exception.",
                    this.getClass().getName(), LogLevel.WARN);
        }
    }

    /**
    Move at a requested velocity.
    @param value The requested motor velocity.
    @param reply Running reply to this JSON request.
     */
    private void moveAt(int value, BrokerMessage reply) throws Exception {

        boolean result;
        try {
            if (mMM3.moveAt(value)) {
                reply.addResult("move_at", "status", "ok");
            } else {
                reply.addError("move_at", BrokerError.E_INST_RESPONSE);
                mLogger.log("Unexpected instrument response on move_at, value: "
                        + value + ".",
                        this.getClass().getName(),
                        LogLevel.WARN);
            }
        } catch (TimeoutException te) {
            reply.addError("move_at", BrokerError.E_TIMEOUT);
            mLogger.log("Timeout occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (IOException ioe) {
            reply.addError("move_at", BrokerError.E_IO);
            mLogger.log("IO exception occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (UnsupportedStateException use) {
            reply.addError("move_at", BrokerError.E_CONNECTION);
            mLogger.log("Unsupported state exception.",
                    this.getClass().getName(), LogLevel.WARN);
        }
    }

    /**
    Move to a position relative to the current position.
    @param value The relative position to move to.
    @param reply Running reply to this JSON request.
     */
    private void moveRel(int value, BrokerMessage reply) throws Exception {
        boolean result;
        try {
            if (mMM3.moveRel(value)) {
                reply.addResult("move_rel", "status", "ok");
            } else {
                reply.addError("move_to_rel", BrokerError.E_INST_RESPONSE);
                mLogger.log("Unexpected instrument response on move_to_rel, value: "
                        + value + ".",
                        this.getClass().getName(),
                        LogLevel.WARN);
            }
        } catch (TimeoutException te) {
            reply.addError("move_to_rel", BrokerError.E_TIMEOUT);
            mLogger.log("Timeout occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (IOException ioe) {
            reply.addError("move_to_rel", BrokerError.E_IO);
            mLogger.log("IO exception occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (UnsupportedStateException use) {
            reply.addError("move_to_rel", BrokerError.E_CONNECTION);
            mLogger.log("Unsupported state exception.",
                    this.getClass().getName(), LogLevel.WARN);
        }
    }

    /**
    Move to an absolute position.
    @param value The position to move to.
    @param reply Running reply to this JSON request.
     */
    private void moveAbs(int value, BrokerMessage reply) throws Exception {
        boolean result;
        try {
            if (mMM3.moveAbs(value)) {
                reply.addResult("move_to_absolute", "status", "ok");
            } else {
                reply.addError("move_to_absolute",
                        BrokerError.E_INST_RESPONSE);
                mLogger.log("Unexpected instrument response on move_to_absolute, value: "
                        + value + ".",
                        this.getClass().getName(),
                        LogLevel.WARN);
            }
        } catch (TimeoutException te) {
            reply.addError("move_to_absolute", BrokerError.E_TIMEOUT);
            mLogger.log("Timeout occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (IOException ioe) {
            reply.addError("move_to_absolute", BrokerError.E_IO);
            mLogger.log("IO exception occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (UnsupportedStateException use) {
            reply.addError("move_to_absolute", BrokerError.E_CONNECTION);
            mLogger.log("Unsupported state exception.",
                    this.getClass().getName(), LogLevel.WARN);
        }
    }

    /**
    Change an MM3 "function" parameter.

    "pos_pwr_up", "ret_pos", "ret_vel", "ret_time", "sat_prot", "save_pos",
    "velocity_limit_enable", "active_stop", "last_rc", "ad_step", "ad_serial",
    "enable_db", "rc_pos_enc_fdbck", "virtual_limit", "disable_pid", and
    "disable_blink" are all single-bit settings determined by the MM3's
    function register.

    This method polls the register, changes the requested bit, and rewrites
    the calculated value back to the register on the MM3.

    @param ps The parameter to be changed.
    @param value The requested value (1 or 0)
    @param reply Running reply to this JSON request.
     */
    private void function(String ps, long value, boolean write_store, BrokerMessage reply) throws Exception {
        int currentValue, nextValue, position;
        position = (Integer) regLocation(ps).get("position");
        try {
            currentValue = mMM3.readRegister("function");
            nextValue = (value > 0) ? currentValue | (1 << position) : currentValue
                    & ~(1 << position);

            boolean res;
            if (write_store) {
                res = mMM3.writeStore("function", nextValue);
            } else {
                res = mMM3.write("function", nextValue);
            }

            if (res) {
                reply.addResult(ps, "status", "ok");
            } else {
                reply.addError(ps, BrokerError.E_INST_RESPONSE);
                mLogger.log("Unexpected instrument response on function register change, parameter: "
                        + ps + ", value: " + value + ".",
                        this.getClass().getName(),
                        LogLevel.WARN);
            }
        } catch (TimeoutException te) {
            reply.addError(ps, BrokerError.E_TIMEOUT);
            mLogger.log("Timeout occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (IOException ioe) {
            reply.addError(ps, BrokerError.E_IO);
            mLogger.log("IO exception occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (UnsupportedStateException use) {
            reply.addError(ps, BrokerError.E_CONNECTION);
            mLogger.log("Unsupported state exception.",
                    this.getClass().getName(), LogLevel.WARN);
        }
    }

    /**
    Change an MM3 "function2" parameter.

    "freq_div2", "freq_x2", "ad_x2", "ad_x4", "ad_x8", "ad_x16", "ad_x32",
    "ad_x64", "over_temp" are all single-bit settings determined by the MM3's
    function2 register.

    "f2_9", "f2_10", "f2_11", "f2_12", "f2_13", "f2_14", "f2_15" are place
    holders that represent bits 9 through 15 of the function2 register. They
    are not used.

    This method polls the register, changes the requested bit, and rewrites
    the calculated value back to the register on the MM3.

    @param ps The parameter to be changed.
    @param value The requested value (1 or 0)
    @param reply Running reply to this JSON request.
     */
    private void function2(String ps, long value, boolean write_store, BrokerMessage reply) throws Exception {
        int currentValue, nextValue, position;
        position = (Integer) regLocation(ps).get("position");
        try {
            currentValue = mMM3.readRegister("function2");
            nextValue = (value > 0) ? currentValue | (1 << position) : currentValue
                    & ~(1 << position);

            boolean res;
            if (write_store) {
                res = mMM3.writeStore("function2", nextValue);
            } else {
                res = mMM3.write("function2", nextValue);
            }

            if (res) {
                reply.addResult(ps, "status", "ok");
            } else {
                reply.addError(ps, BrokerError.E_INST_RESPONSE);
                mLogger.log("Unexpected instrument response on function2 register change, parameter: "
                        + ps + ", value: " + value + ".",
                        this.getClass().getName(),
                        LogLevel.WARN);
            }
        } catch (TimeoutException te) {
            reply.addError(ps, BrokerError.E_TIMEOUT);
            mLogger.log("Timeout occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (IOException ioe) {
            reply.addError(ps, BrokerError.E_IO);
            mLogger.log("IO exception occurred.", this.getClass().getName(),
                    LogLevel.WARN);
        } catch (UnsupportedStateException use) {
            reply.addError(ps, BrokerError.E_CONNECTION);
            mLogger.log("Unsupported state exception.",
                    this.getClass().getName(), LogLevel.WARN);
        }
    }

    /**
    When a readall is executed on the MM3, the retrieved data are organized
    in a comma-separated string of 32 values. This method returns the position
    of the parameter within that string by: pulling a parameter triplet from
    the JSONParameters HashMap and referencing element number (FIELD_INDEX) from
    the triplet.
    @param parameter
    @return the field number in which the parameter value will appear.
     */
    private static final int getFieldIndex(String parameter) {
        return Integer.parseInt(JSONParameters.get(parameter)[FIELD_INDEX]);
    }
    /**
    The index at which the MM3 field index resides within the JSONParameters
    array for any parameter.
     */
    static final int FIELD_INDEX = 2;

    private long mLastDataTime = 0;
    public Timestamp getLastDataTime() {
        if (mMM3 != null) {
            mLastDataTime = mMM3.mLastReadTime;
        }
        return new Timestamp(mLastDataTime);
    }
    public Timestamp getLastDbTime() { return new Timestamp(0); }   // no database

    
    /**
     * Turns sampling on or off if applicable.  Maintains mSampling flag.
     * Means nothing to mm3.  Always sampling.
     * @param toOn boolean
     */
    @Override
    public void setSampling(boolean toOn) {
        mSampling = SAMPLING_ON;
    }
    

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
        JSONParameters.put("position", arrayOf("counts", "RW", "0"));
        JSONParameters.put("velocity_limit", arrayOf("counts/s", "RW", "1"));
        JSONParameters.put("velocity_ff", arrayOf("", "RW", "2"));
        JSONParameters.put("function", arrayOf("", "RW", "3"));
        JSONParameters.put("p_term", arrayOf("", "RW", "4"));
        JSONParameters.put("i_term", arrayOf("", "RW", "5"));
        JSONParameters.put("d_term", arrayOf("", "RW", "6"));
        JSONParameters.put("address", arrayOf("", "RW", "7"));
        JSONParameters.put("pid_scalar", arrayOf("", "RW", "8"));
        JSONParameters.put("timer", arrayOf("ms", "RW", "9"));
        JSONParameters.put("rcmax", arrayOf("ns", "RW", "10"));
        JSONParameters.put("rcmin", arrayOf("ns", "RW", "11"));
        JSONParameters.put("rcband", arrayOf("ns", "RW", "12"));
        JSONParameters.put("rccount", arrayOf("ns", "RW", "13"));
        JSONParameters.put("velocity", arrayOf("counts/s", "RW", "14"));
        JSONParameters.put("time", arrayOf("ms", "RW", "15"));
        JSONParameters.put("status", arrayOf("", "RO", "16"));
        JSONParameters.put("revision", arrayOf("", "RW", "17"));
        JSONParameters.put("mode", arrayOf("", "RW", "18"));
        JSONParameters.put("analog_con", arrayOf("mV", "RW", "19"));
        JSONParameters.put("analog_fbck", arrayOf("mV", "RW", "20"));
        JSONParameters.put("pwm_out", arrayOf("", "RW", "21"));
        JSONParameters.put("index_pos", arrayOf("counts", "RW", "22"));
        JSONParameters.put("vir_neg_limit", arrayOf("counts", "RW", "23"));
        JSONParameters.put("vir_pos_limit", arrayOf("counts", "RW", "24"));
        JSONParameters.put("PWM_limit", arrayOf("", "RW", "25"));
        JSONParameters.put("deadband", arrayOf("mV", "RW", "26"));
        JSONParameters.put("desired_position", arrayOf("counts", "RW", "27"));
        JSONParameters.put("amps_limit", arrayOf("mA", "RW", "28"));
        JSONParameters.put("amps", arrayOf("mA", "RO", "29"));
        JSONParameters.put("function2", arrayOf("", "RW", "30"));
        JSONParameters.put("temperature", arrayOf("degC", "RO", "31"));
        JSONParameters.put("pos_pwr_up", arrayOf("", "RW", "32"));
        JSONParameters.put("ret_pos", arrayOf("", "RW", "33"));
        JSONParameters.put("ret_vel", arrayOf("", "RW", "34"));
        JSONParameters.put("ret_time", arrayOf("", "RW", "35"));
        JSONParameters.put("sat_prot", arrayOf("", "RW", "36"));
        JSONParameters.put("save_pos", arrayOf("", "RW", "37"));
        JSONParameters.put("velocity_limit_enable", arrayOf("", "RW", "38"));
        JSONParameters.put("active_stop", arrayOf("", "RW", "39"));
        JSONParameters.put("last_rc", arrayOf("", "RW", "40"));
        JSONParameters.put("ad_step", arrayOf("", "RW", "41"));
        JSONParameters.put("ad_serial", arrayOf("", "RW", "42"));
        JSONParameters.put("enable_db", arrayOf("", "RW", "43"));
        JSONParameters.put("rc_pos_enc_fdbck", arrayOf("", "RW", "44"));
        JSONParameters.put("virtual_limit", arrayOf("", "RW", "45"));
        JSONParameters.put("disable_pid", arrayOf("", "RW", "46"));
        JSONParameters.put("disable_blink", arrayOf("", "RW", "47"));
        JSONParameters.put("freq_div2", arrayOf("", "RW", "48"));
        JSONParameters.put("freq_x2", arrayOf("", "RW", "49"));
        JSONParameters.put("ad_x2", arrayOf("", "RW", "50"));
        JSONParameters.put("ad_x4", arrayOf("", "RW", "51"));
        JSONParameters.put("ad_x8", arrayOf("", "RW", "52"));
        JSONParameters.put("ad_x16", arrayOf("", "RW", "53"));
        JSONParameters.put("ad_x32", arrayOf("", "RW", "54"));
        JSONParameters.put("ad_x64", arrayOf("", "RW", "55"));
        JSONParameters.put("over_temp", arrayOf("", "RW", "56"));
        JSONParameters.put("f2_9", arrayOf("", "NI", "57"));
        JSONParameters.put("f2_10", arrayOf("", "NI", "58"));
        JSONParameters.put("f2_11", arrayOf("", "NI", "59"));
        JSONParameters.put("f2_12", arrayOf("", "NI", "60"));
        JSONParameters.put("f2_13", arrayOf("", "NI", "61"));
        JSONParameters.put("f2_14", arrayOf("", "NI", "62"));
        JSONParameters.put("f2_15", arrayOf("", "NI", "63"));
        JSONParameters.put("neg_limit_switch", arrayOf("", "RO", "64"));
        JSONParameters.put("pos_limit_switch", arrayOf("", "RO", "65"));
        JSONParameters.put("brake", arrayOf("", "RO", "66"));
        JSONParameters.put("index", arrayOf("", "RO", "67"));
        JSONParameters.put("bad_rc", arrayOf("", "RO", "68"));
        JSONParameters.put("neg_limit_virtual", arrayOf("", "RO", "69"));
        JSONParameters.put("pos_limit_virtual", arrayOf("", "RO", "70"));
        JSONParameters.put("current_limit", arrayOf("", "RO", "71"));
        JSONParameters.put("PWM_limited", arrayOf("", "RO", "72"));
        JSONParameters.put("in_position", arrayOf("", "RO", "73"));
        JSONParameters.put("temp_fault", arrayOf("", "RO", "74"));
        JSONParameters.put("s_11", arrayOf("", "NI", "75"));
        JSONParameters.put("s_12", arrayOf("", "NI", "76"));
        JSONParameters.put("s_13", arrayOf("", "NI", "77"));
        JSONParameters.put("s_14", arrayOf("", "NI", "78"));
        JSONParameters.put("s_15", arrayOf("", "NI", "79"));
        JSONParameters.put("move_at", arrayOf("counts/s", "WO", "80"));
        JSONParameters.put("move_to_rel", arrayOf("counts", "WO", "81"));
        JSONParameters.put("move_to_absolute", arrayOf("counts", "WO", "82"));
        JSONParameters.put("write_store", arrayOf("boolean", "WO", "83"));
    }
}
