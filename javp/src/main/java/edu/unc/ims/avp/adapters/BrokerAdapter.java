package edu.unc.ims.avp.adapters;

import edu.unc.ims.avp.BrokerMessage;
import edu.unc.ims.avp.BrokerRequest;
import edu.unc.ims.avp.BrokeredDeviceListener;
import edu.unc.ims.avp.BrokerSubscription;
import edu.unc.ims.avp.BrokerError;
import edu.unc.ims.avp.IoClient;
import org.json.JSONObject;
import java.util.HashMap;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import org.json.JSONException;
import java.sql.Timestamp;
import java.util.Objects;

/**
Adapters extend BrokerAdapter.  Provides code common to all adapters and defines
what methods are required to be written.
 */
public abstract class BrokerAdapter {

    Logger mLogger;         // Logger

    String mIoBrokerHost = null;   // null indicates no io
    int mIoBrokerPort;
    String mIoPort;          // AIO power port
    boolean mIoRelayLogic; // high or low relay logic
    
    // These values are set based on conf file values later
    public boolean POWER_ON = false;
    public boolean POWER_OFF = true;
    
    public final boolean SAMPLING_ON = true;
    public final boolean SAMPLING_OFF = false;
    protected boolean mSampling = SAMPLING_OFF;
    public boolean getSampling() { return mSampling; }

    public final boolean LOGGING_ON = true;
    public final boolean LOGGING_OFF = false;
    private boolean mLogging = LOGGING_OFF;
    public void setLogging(boolean l) { mLogging=l; }
    public boolean getLogging() { return mLogging; }

    private HashMap<String, BrokerSubscription> mSubs = new HashMap<String, BrokerSubscription>();  // list of subscriptions

    public static final int UNITS_INDEX = 0;
    public static final int TYPE_INDEX = 1;
    public static final HashMap<String, String[]> JSONParameters = new HashMap<String, String[]>();
    public final boolean checkParameter(String ps) {
        return JSONParameters.containsKey(ps);
    }

    /* Boolean value determines whether extendedMethod is restricted
    (i.e., only called by one control socket at a time) or not.  List must be
    created in the specific adapter code */
    protected static final HashMap<String, Boolean> extendedMethods = new HashMap<String, Boolean>();

    /* needs to kept in sync with Broker.isSuspended, especially to
     * notify subscriptions that we are suspended.
     */
    private boolean mSuspended = false;
    public boolean isSuspended() { return mSuspended; }
    public void setSuspended(boolean s) { mSuspended = s; }

    /* require reporting of time of last data and last database
     */
    public abstract Timestamp getLastDataTime();
    public abstract Timestamp getLastDbTime();
    
    
    /**
    Default constructor.
    Sets up the logging instance.
     */
    public BrokerAdapter() {
        mLogger = Logger.getLogger();
    }

    
    /**
    Extended constructor, sets up io broker connection.
    @param ioBrokerHost
    @param ioBrokerPort
    @param ioPort  Power port
     */
    public BrokerAdapter(String ioBrokerHost, int ioBrokerPort, String ioPort) {
        this();     // call default constructor
        mIoBrokerHost = ioBrokerHost;
        mIoBrokerPort = ioBrokerPort;
        mIoPort = ioPort;
    }

    /**
     * Broker should set these properties after (or upon) constructing this adapter
     * @param ioBrokerHost
     * @param ioBrokerPort
     * @param ioPort   Power port
     * @param ioRelayLogic true is 1 for on and 0 for off
     */
    public void setIoProperties(String ioBrokerHost, int ioBrokerPort, String ioPort,
            boolean ioRelayLogic) {
        mIoBrokerHost = ioBrokerHost;
        mIoBrokerPort = ioBrokerPort;
        mIoPort = ioPort;
        mIoRelayLogic = ioRelayLogic;
        if (ioRelayLogic == true) {
            POWER_ON = true;
            POWER_OFF = false;
        }else{
            POWER_ON = false;
            POWER_OFF = true;
        }
    }

    
    /**
    Connect to the instrument and initialize.
    Must be the first method called.
    @throws Exception   on error
     */
    public abstract void connect() throws Exception;
    public abstract boolean isConnected();

    
    /**
    Clean up any resources prior to object destruction.
    Gives the device a chance to gracefully release any resources it may use
    prior to it's destruction.
    @throws Exception   on error
     */
    public abstract void disconnect() throws Exception;

    
    /**
     * Subscriptions are uniquely identified by both the parameter and the listener.
     * The key in the internal hash map uses a combination of the parameter and the
     * string representation of the listener.
     * @param parameter
     * @param l     Brokered device listener
     * @param r     the subscription
     */
    public void addSubscription(String parameter, BrokeredDeviceListener l, BrokerSubscription r) {
        mSubs.put(parameter+"-Listener="+l.toString(), r);
    }

    /**
     * Subscriptions are uniquely identified by both the parameter and the listener.
     * The key in the internal hash map uses a combination of the parameter and the
     * string representation of the listener.
     * @param parameter
     * @param l     Brokered device listener
     * @return 
     */
    public boolean hasSubscription(String parameter, BrokeredDeviceListener l) {
        return mSubs.containsKey(parameter+"-Listener="+l.toString());
    }

    /**
     * Subscriptions are uniquely identified by both the parameter and the listener.
     * The key in the internal hash map uses a combination of the parameter and the
     * string representation of the listener.
     * @param parameter
     * @param l     Brokered device listener
     */
    public void dropSubscription(String parameter, BrokeredDeviceListener l) {
        BrokerSubscription sub = mSubs.remove(parameter+"-Listener="+l.toString());
        if (sub != null) {
            sub.unSubscribe(parameter);
        }
    }


    /**
     * Get a value from the specific broker adapter
     * @param params
     * @param reply 
     * @throws java.lang.Exception 
     */
    public abstract void get(HashMap<String, Object> params, BrokerMessage reply) throws Exception;

     /**
     * Set a value in the specific broker adapter
     * @param params
     * @param reply 
     * @throws java.lang.Exception 
     */
    public abstract void put(HashMap<String, Object> params, BrokerMessage reply) throws Exception;

    
    /**
    Returns minimum subscription update interval possible by the broker.
    This can be dynamic or static based on device characteristics.
     * @return 
     */
    public abstract int getMinSubInterval();


    /**
    Let the device attempt to reset to a known state.
    @throws Exception   on error
     */
    public abstract void softReset() throws Exception;

    
    /**
     * Starts or stops the device sampling if applicable.  Must keep the flag mSampling
     * in the correct state.
     * 
     * @param toOn 
     */
    public abstract void setSampling(boolean toOn);

    
    /**
    Custom command is called when broker.processRequest does not handle the request
    that came in on the command port.
    
    @param  request Custom command request JSON object
    @param  listener to receive custom command response
    @throws Exception   on error.
    */
    public void customCommand(JSONObject request, BrokeredDeviceListener listener) throws Exception {
        try {
            String method = request.optString("method");
            if (!method.isEmpty()) {
                new BrokerRequest(request, this, listener).execute();
            } else {
                BrokerMessage reply = new BrokerMessage();
                reply.addError(BrokerError.E_PARSE);
                listener.onData(reply.toJSONResponse());
            }
        } catch (JSONException e) {
            BrokerMessage reply = new BrokerMessage();
            reply.addError(BrokerError.E_PARSE);
            try {
                listener.onData(reply.toJSONResponse());
            } catch (JSONException ee) {
                mLogger.log("JSONException caught during customCommand " + ee.getMessage(),
                    this.getClass().getName(),  LogLevel.WARN);
            }
        }
    }

    
    /**
    extendedMethod handles broker requests that are specific to a particular instrument/adapter.
    <p>
    To implement extended methods, this method must be overridden.
    </p><p>
    If there are no such methods for this broker, calls to this method result
    in an error being sent over the JSON socket.

    @param method String representation of the method.
    @param request The original JSON request.
    @param listener the class (ControllerClientHandler) to which the reply should be sent
     * @throws java.lang.Exception
    */
    public void extendedMethod(String method, JSONObject request, BrokeredDeviceListener listener) throws Exception {
        BrokerMessage reply = new BrokerMessage(method);
        try {
            reply.setId(request.getInt("id"));
        } catch(JSONException j1) {
            mLogger.log("JSONException when setting ID in extended method: " + j1.getMessage(),
                    this.getClass().getName(), LogLevel.DEBUG);
        }
        reply.addError(BrokerError.E_UNSUPPORTED_METHOD);
        mLogger.log("Unsupported extended method.", this.getClass().getName(), LogLevel.WARN);
        try {
            listener.onData(reply.toJSONResponse());
        } catch (JSONException j2) {
            mLogger.log("JSONException when sending unsupported method error: " + j2.getMessage(),
                    this.getClass().getName(), LogLevel.DEBUG);
        }
    }

    
    /**
     * Determine if the method named requires the control token to run
     * @param s name of the method to check
     * @return  boolean
     */
    public boolean restrictedMethod(String s) {
        if (BrokerRequest.restrictedMethod(s)) {
            return true;
        } else return Objects.equals(extendedMethods.get(s), Boolean.TRUE);
    }

    /**
     * Turn on the power to this instrument, if this broker supports it.
     * 
     * @return  boolean is the power on?
     * @throws Exception 
     */
    public boolean power_on() throws Exception {
        boolean success;
        
        if (getPower()==POWER_OFF) {
            mLogger.log("The power port is OFF, attempting to turn ON", this.getClass().getName(), LogLevel.INFO);
            if(!setPower(POWER_ON)) {
                success = false;
            } else {
                mLogger.log("Power successfully turned ON", this.getClass().getName(), LogLevel.INFO);
                success = true;
            }
        } else {
            mLogger.log("The power port is already ON", this.getClass().getName(), LogLevel.INFO);
            success = true;
        }
        
        return success;
    }

    
    /**
     * Manipulate the power for this instrument.  Not sure if this code ever
     * gets used since power is handled in broker.processRequest
     * 
     * @param status
     * @param reply 
     */
    public final void power(String status, BrokerMessage reply) {
        try {
            switch (status) {
                case "on":
                    if (setPower(POWER_ON)) {
                        reply.addResult("ok");
                    } else {
                        reply.addError(BrokerError.E_POWER_SET_FAILED);
                    }   break;
                case "off":
                    if (setPower(POWER_OFF)) {
                        reply.addResult("ok");
                    } else {
                        reply.addError(BrokerError.E_POWER_SET_FAILED);
                    }   break;
                case "check":
                    if (getPower()==POWER_ON) {
                        reply.addResult("on");
                    } else {
                        reply.addResult("off");
                    }   break;
                default:
                    break;
            }
        } catch (Exception e) {
            reply.addError(BrokerError.E_EXCEPTION, e.getMessage());
        }
    }

    /**
    Sets power state
    Depends on ioBrokerHost, ioBrokerPort, ioPort, ioPin being set.
    @param powerValue POWER_ON or POWER_OFF
     * @return 
    @throws Exception
     */
    public final boolean setPower(boolean powerValue) throws Exception {
        if (mIoBrokerHost != null) {   // if there is no io host, assume the power is on
            try {
                IoClient io = new IoClient(mIoBrokerHost, mIoBrokerPort);
                boolean res = io.switchPin(mIoPort, powerValue);
                io.shutdown();
                return res;
            } catch (Exception e) {
                throw e;
            }
        } else {
            return POWER_ON;
        }
    }

    /**
    returns power state
    Depends on ioBrokerHost, ioBrokerPort, ioPort, ioPin being set.
    @return POWER_ON or POWER_OFF (can be true or false depending on relay logic)
    @throws Exception
     */
    public final boolean getPower() throws Exception {
        if (mIoBrokerHost != null) {   // if there is no io host, assume the power is on
            try {
                IoClient io = new IoClient(mIoBrokerHost, mIoBrokerPort);
                boolean res = io.isOn(mIoPort);
                io.shutdown();   // io client starts a thread that we don't need anymore
                return res;
            } catch (Exception e) {
                throw e;
            }
        } else {
            return POWER_ON;
        }
    }

}
