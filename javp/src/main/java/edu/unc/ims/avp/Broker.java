package edu.unc.ims.avp;

import java.io.File;
import java.io.FileInputStream;
import java.util.Properties;
import java.lang.reflect.Constructor;
import java.util.List;
import java.util.Iterator;
import java.util.ArrayList;
import java.util.HashMap;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.avp.adapters.BrokerAdapter;
import org.json.JSONObject;
import java.sql.Timestamp;
import java.io.InputStreamReader;
import java.io.BufferedReader;

/**
<p>
Data brokers handle the details of collecting data from a specific data source.  
Data sources are dynamically loaded classes that extend BrokerAdapter and are
specified in a config file.  Broker-level code connects to the attached adapter and
manages a communication interface where requests are passed down to the appropriate 
code level.
</p><p>
The levels of code from broker to specific instrument are as follows:<br>
<ul>
<li>Broker dynamically loads a BrokerAdapter
<li>(InstrumentCategory)Adapter extends BrokerAdapter, (e.g. SounderAdapter)
<li>Adapter directly loads instrument class, or dynamically loads a (device)Instrument (e.g. SounderInstrument)
<li>If dynamic, instrument class extends (device)Instrument
</ul>
Therefore each running instance of a broker operates a specific instrument as specified
in its config file.
</p><p>
Command processing is handled as follows:<br>
<ul>
<li>Broker starts a BrokerControllerServer thread to listen on a config-file specified socket for connections
<li>For each connection a ControllerClientHandler thread is started
<li>ControllerClientHandler reads requests in JSON format and tries to parse
<li>Request is passed to broker's processRequest method which handles
    <ul>
    <li> token acquire
    <li> token forceAcquire
    <li> token release
    <li> power (on|off|status)
    <li> shutdown
    <li> connect
    <li> disconnect
    <li> suspend
    <li> resume
    <li> broker_status
    <li> softreset
    </ul>
<li> Other requests are passed to BrokerAdapter.customCommand
</p>
 */
public class Broker {
    private final long mBrokerStartTime = System.currentTimeMillis();
    public long getStartTime() { return mBrokerStartTime; }

    private Properties mProperties = new Properties();  // Configuration properties
    public final Properties getProperties() { return mProperties; }

    private BrokerAdapter mBrokeredDevice;      // The dynamically loaded device adapter
    public BrokerAdapter getBrokeredDevice() { return mBrokeredDevice; }
    private String mAdapterName;
    public String getAdapterName() { return mAdapterName; }
    public Boolean isDeviceConnected() { return mBrokeredDevice.isConnected(); }
    
    private Boolean mSuspended = false;         // Is broker suspended
    public Boolean isSuspended() { return mSuspended; }
    
    private BrokerControllerServer mBrokerControllerServer; // Controller server (listener)
    private Thread mBrokerControllerServerThread;           // Controller server (listener) thread
    private List<ControllerClientHandler> mClients = new ArrayList<ControllerClientHandler>(); // List of connected data clients.
    
    ControlToken token = new ControlToken();
    
    private Db mDb = null;                      // Database connection
    public final Db getDb() { return mDb; }
    private boolean mDbEnabled;
    private Logger mLogger;

    // setting mState to CONNECTING tells watchdog thread to try to connect
    public static enum State { DISCONNECTED, CONNECTED, CONNECTING };
    private State mState = State.DISCONNECTED; // Device state
    synchronized public void setState(State s) { mState = s;  }
    synchronized public State getState() { return mState; }

    // watchdog thread tries to connect unless suspended
    private BrokerWatchdog mWatchdog;
    private Thread mBrokerWatchdogThread;

    
    /**
    Check the config file(s) and construct the broker.
    @param  args    list of config files
    @throws Exception   on error
     */
    public static void main(final String[] args) throws Exception {
        Thread t = Thread.currentThread();
        t.setName("Broker-main");

        if (args.length < 1) {
            System.err.println("usage: " + Broker.class.getName() + "<configuration_file> [<configuration_file>]");
            System.exit(1);
        }
        List<File> cfs = new ArrayList<File>();
        for (int i = 0; i < args.length; i++) {
            File cf = new File(args[i]);
            if (!cf.exists()) {
                System.err.println("Configuration file does not exist: " + cf);
                System.exit(2);
            }
            if (!cf.canRead()) {
                System.err.println("Unable to read configuration file: " + cf);
                System.exit(3);
            }
            cfs.add(cf);
        }
        new Broker(cfs);
    }

    
    /**
    Constructor also creates a Logger, a Db object, a watchDog thread, and a controller server thread.
    @param  configurationFiles   Configuration files.
     */
    public Broker(final List<File> configurationFiles) {
        try {
            // load configuration file
            Iterator<File> i = configurationFiles.iterator();
            while (i.hasNext()) {
                mProperties.load(new FileInputStream(i.next()));
            }

            mLogger = Logger.getLogger();
            mLogger.setLevel(mProperties.getProperty("log_level", "FATAL"));
            mLogger.setLogFile(mProperties.getProperty("log_file", "-"));
            mLogger.log("Broker starting...", this.getClass().getName(), LogLevel.INFO);

            // (Optionally) establish a connection to the database.  This
            // connection is for broker data, logging gets it's own connection.
            mDbEnabled = Boolean.parseBoolean(mProperties.getProperty("db_enabled", "true"));
            if (mDbEnabled) {
                // Check the db table prefix.  If it doesn't exist in the config
                // then set it to 'hostname'. This assumes that the hostname command exists.
                if ( mProperties.getProperty("db_table_prefix", "default").equals("default") ) {
                    Process proc = Runtime.getRuntime().exec("hostname");
                    BufferedReader stdInput = new BufferedReader(new InputStreamReader(proc.getInputStream()));
                    mProperties.setProperty("db_table_prefix",  stdInput.readLine());
                    mLogger.log("Property db_table_prefix not found. Setting to result of hostname command as: "
                            + mProperties.getProperty("db_table_prefix"), this.getClass().getName(), LogLevel.INFO );
                }
                mDb = new Db(mProperties);
                // use a separate JDBC connection. ?? was new Db(mProperties) instead of mDb
                mLogger.setDatabase(mDb, mProperties.getProperty("db_table_prefix"));
            } else {
                mLogger.log("Database is disabled.", this.getClass().getName(), LogLevel.WARN);
            }

            mSuspended = Boolean.parseBoolean(mProperties.getProperty("suspended", "false"));
            if (mSuspended) {
                mLogger.log("Broker is starting suspended.", this.getClass().getName(), LogLevel.WARN);
            }

            
            // Load the adapter class
            Class<?> c = ClassLoader.getSystemClassLoader().loadClass(mProperties.getProperty("adapter_class"));
            Constructor cst = c.getDeclaredConstructor(Broker.class);
            mBrokeredDevice = (BrokerAdapter) cst.newInstance(this);    // call constructor with broker as argument
            mAdapterName = mBrokeredDevice.getClass().getName().substring(
                mBrokeredDevice.getClass().getName().lastIndexOf('.')+1);

            mLogger.log("Loaded adapter: " + mBrokeredDevice.getClass().getName(), this.getClass().getName(),
                    LogLevel.DEBUG);
            mWatchdog = new BrokerWatchdog(this, mBrokeredDevice.getClass().getName());

            mBrokeredDevice.setSuspended(mSuspended);   // maintain sync with brokered device flag

            mBrokeredDevice.setIoProperties(
                    mProperties.getProperty("IoAdapter_host", null),
                    Integer.parseInt(mProperties.getProperty("IoAdapter_ctrl_port", "0")),
                    mProperties.getProperty("Io_power_port", "a"),
                    Boolean.parseBoolean(mProperties.getProperty("Io_relay_logic_high", "true"))
                    );

            // By default, we try to connect and start collecting.

            /* The BrokerWatchdog is for fault-tolerance.  For example, if
             * the broker is unable to establish a connection to the device
             * at start time, we don't want the broker to exit.  Instead,
             * we want the broker to continue trying to connect by itself.
             * Also, if there are communications failures during operation,
             * we want the broker to automatically reconnect.  The watchdog
             * is responsible for monitoring and handling these issues.
             */
            mBrokerWatchdogThread = new Thread(mWatchdog, mBrokeredDevice.getClass().getName()+"-Watchdog");
            mBrokerWatchdogThread.start();

            // Prod the watchdog into connecting (unless suspended)
            setState(State.CONNECTING);

            // Start a controller server
            mBrokerControllerServer = new BrokerControllerServer(this);
            mBrokerControllerServerThread = new Thread(mBrokerControllerServer,
                    mBrokeredDevice.getClass().getName()+"-ControllerServer");
            mBrokerControllerServerThread.start();
            mLogger.log("Controller server thread started", this.getClass().getName(), LogLevel.DEBUG);
        } catch (Exception e) {
            e.printStackTrace();
            mLogger.log(e.toString(), this.getClass().getName(), LogLevel.FATAL);
        }
    }

    
    /**
    The watchdog thread calls this to connect to brokered device unless suspended.
    Attempts to establish a connection to the brokered device.  On success,
    the internal state is set to State.CONNECTED.  On error, an exception is
    thrown.

    @throws Exception   On error
    */
    protected final void connect() throws Exception {
        mLogger.log("Connecting to brokered device...", this.getClass().getName(), LogLevel.DEBUG);
        try {
            if(mBrokeredDevice == null) {
                return;
            }
            mBrokeredDevice.connect();
            setState(State.CONNECTED);
            mLogger.log("connected to " + mWatchdog.getLabel(), this.getClass().getName(), LogLevel.DEBUG);
        } catch(Exception e) {
            mBrokeredDevice.disconnect();  //not broker.disconnect because state needs to stay connecting
            e.printStackTrace();
            mLogger.log("connect() to " + mWatchdog.getLabel() + " failed: " + e.toString(),
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }

    
    /**
    Disconnect.
    @throws Exception   On error
     */
    protected final void disconnect() throws Exception {
        if (getState() == State.CONNECTED) {
            mBrokeredDevice.disconnect();
        }
        setState(State.DISCONNECTED);
    }


    /**
    Process client request.
    Callback called by child thread when a client request has been successfully
    read.  Response (if any) is sent back to the client.

    (token) acquire, forceAcquire, release, power, shutdown, connect, disconnect,
    suspend, resume, broker_status and softreset
    are handled within this method. Other requests are passed to 
    BrokerAdapter.customCommand, which creates a BrokerRequest that
    executes the command.

    @param  request The request object, which includes the method.
    @param  handler The client handler to receive the response object.  Id already set.
    @return result  boolean - set false on shutdown
     */
    public boolean processRequest(JSONObject request, ControllerClientHandler handler) {

        mLogger.log(request.toString(), this.getClass().getName(), LogLevel.DEBUG);

        boolean result = true;
        JSONObject response = new JSONObject();

        try {
            String s;
            BrokeredDeviceListener listener = (BrokeredDeviceListener) handler;
            String methodString = request.getString("method");
            BrokerMessage reply = new BrokerMessage(methodString);
            reply.setId(request.getInt("id"));
            response.put("id", request.get("id"));

            // Check the token if the method requires a token
            if (!handler.hasToken() && restrictedMethod(methodString)) {
                reply.addError(BrokerError.E_TOKEN_REQUIRED);

                // If we're not blocked because of a token problem check to see if it is a token command.
                // These next command can be called whether the broker is suspended or not.
            } else if(methodString.startsWith("token")) {
                token.processJSONRequest(handler, request, reply);

                // power
            } else if (methodString.equals("power")) {
                if (request.has("params")) { // status either on or off
                    JSONObject params = request.getJSONObject("params");
                    if (params.getString("status").toLowerCase().equals("on")) {
                        mBrokeredDevice.setPower(mBrokeredDevice.POWER_ON);
                    } else if (params.getString("status").toLowerCase().equals("off")) {
                        mBrokeredDevice.setPower(mBrokeredDevice.POWER_OFF);
                    }
                }
                reply.addResult(mBrokeredDevice.getPower()==mBrokeredDevice.POWER_ON?"on":"off");

                // sampling
            } else if (methodString.equals("sampling")) {
                if (request.has("params")) { // status either on or off
                    JSONObject params = request.getJSONObject("params");
                    if (params.getString("status").toLowerCase().equals("on")) {
                        mBrokeredDevice.setSampling(mBrokeredDevice.SAMPLING_ON);
                    } else if (params.getString("status").toLowerCase().equals("off")) {
                        mBrokeredDevice.setSampling(mBrokeredDevice.SAMPLING_OFF);
                    }
                }
                reply.addResult(mBrokeredDevice.getSampling()?"on":"off");

                // logging
            } else if (methodString.equals("logging")) {
                if (request.has("params")) { // status either on or off
                    JSONObject params = request.getJSONObject("params");
                    if (params.getString("status").toLowerCase().equals("on")) {
                        mBrokeredDevice.setLogging(mBrokeredDevice.LOGGING_ON);
                    } else if (params.getString("status").toLowerCase().equals("off")) {
                        mBrokeredDevice.setLogging(mBrokeredDevice.LOGGING_OFF);
                    }
                }
                reply.addResult(mBrokeredDevice.getLogging()?"on":"off");

                // shutdown
            } else if (methodString.equals("shutdown")) {
                shutdown();
                result = false;
                reply.addResult("ok");

                // suspend
            } else if (methodString.equals("suspend")) {
                mSuspended = true;
                mBrokeredDevice.setSuspended(true);
                disconnect();
                reply.addResult("ok");

                // resume
            } else if (methodString.equals("resume")) {
                if (mSuspended) {
                    mSuspended = false;
                    mBrokeredDevice.setSuspended(false);
                    // connect(); this will be handled by the watchdog
                    setState(State.CONNECTING);

                    // allow time, then check to see if connect succeeded
                    int loopCounter = 0;
                    while (mState != State.CONNECTED && loopCounter < 45) {
                        Thread.sleep(1000);
                        loopCounter = loopCounter + 1;
                    }
                }
                if (mState != State.CONNECTED) {
                    reply.addError(BrokerError.E_CONNECTION);
                } else {
                    reply.addResult("ok");
                }

                // broker status
            } else if (methodString.equals("broker_status")) {
                // report whether the broker is suspended
                reply.addResult("suspended", mSuspended.toString());
                // report whether the instrument power is on
                if (mProperties.getProperty("AioAdapter_host") == null && mProperties.getProperty("IoAdapter_host") == null) {
                    reply.addResult("power_on", "unknown");
                } else {
                    reply.addResult("power_on", 
                            ((Boolean) mBrokeredDevice.getPower())==mBrokeredDevice.POWER_ON?"true":"false");
                }
                // report whether the instrument/device is connected
                reply.addResult("instr_connected", ((Boolean)mBrokeredDevice.isConnected()).toString());
                // TODO: make this reflect whether the db is really connected rather than just enabled
                reply.addResult("db_connected", ((Boolean)mDbEnabled).toString());
                // report the broker start time
                reply.addResult("start_time", (new Timestamp(mBrokerStartTime)).toString() );
                // Report the last time data was received by the instrument
                if (mBrokeredDevice.getLastDataTime().equals(new Timestamp(0))) { s = "none"; }
                else { s = mBrokeredDevice.getLastDataTime().toString(); }
                reply.addResult("last_data_time", s );
                // Report the last time data was logged to the database
                if (mBrokeredDevice.getLastDbTime().equals(new Timestamp(0))) { s = "none"; }
                else { s = mBrokeredDevice.getLastDbTime().toString(); }
                reply.addResult("last_db_time", s );

                // connect
            } else if (methodString.equals("connect") && !mSuspended) {
                connect();
                reply.addResult("ok");

                // disconnect
            } else if (methodString.equals("disconnect") && !mSuspended) {
                disconnect();
                reply.addResult("ok");

                // soft reset
            } else if (methodString.equals("softReset") && !mSuspended) {
                softReset();
                reply.addResult("ok");

                // if the broker is not suspended, unhandled commands are passed
                // to BrokerAdapter.customCommand.
            } else if (!mSuspended){
                mBrokeredDevice.customCommand(request, listener);

            } else {
                reply.addError(BrokerError.E_BROKER_IS_SUSPENDED);
            }

            if (reply.hasNew()) {
                handler.onData(reply.toJSONResponse()); // issue the reply
            }
        } catch (Exception e) {
            e.printStackTrace();
            mLogger.log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            try {
                response.put("result", e.toString());
                handler.onData(response);
            } catch(Exception ee) {
                ee.printStackTrace();
            }
        }
        return result;
    }


    /**
    Soft reset.
    @throws Exception   On error
     */
    protected final void softReset() throws Exception {
        if (getState() != State.CONNECTED) {
            throw new Exception("Invalid state change requested");
        }
        mBrokeredDevice.softReset();
    }

    
    /**
    Reload.
    @throws Exception   On error
     */
    protected void reloadConfiguration() throws Exception {
    }

    
    /**
    Register in client handler list.  As far as I can tell this is only used
    to shut down each thread.
    @param  d   Item to register.
     */
    public final void register(final ControllerClientHandler d) {
        synchronized (mClients) {
            mClients.add(d);
        }
    }

    /**
    Unregister from client handler list
    @param  d   Item to unregister.
     */
    public final void unregister(final ControllerClientHandler d) {
        if (d.hasToken()) {
            token.take();
        }
        synchronized (mClients) {
            mClients.remove(d);
        }
    }


    /**
    Shutdown.
     */
    protected final void shutdown() {
        try {
            mBrokeredDevice.disconnect();
            mBrokerControllerServer.shutdown();
            Iterator<ControllerClientHandler> i = mClients.iterator();
            while (i.hasNext()) {
                ControllerClientHandler h = i.next();
                try {
                    h.shutdown();
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
            if (mDbEnabled) {
                mDb.shutdown();
            }
            mWatchdog.shutdown();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    
    private static final HashMap<String, Boolean> methods = new HashMap<String, Boolean>();
    /**
     T or F does this method require a token to be called
     */
    static {
        methods.put("shutdown",          Boolean.TRUE);
        methods.put("connect",           Boolean.TRUE);
        methods.put("disconnect",        Boolean.TRUE);
        methods.put("softReset",         Boolean.TRUE);
        methods.put("tokenAcquire",      Boolean.FALSE);
        methods.put("tokenRelease",      Boolean.TRUE);
        methods.put("tokenForceAcquire", Boolean.FALSE);
        methods.put("tokenOwner",        Boolean.FALSE);
        methods.put("suspend",           Boolean.TRUE);
        methods.put("resume",            Boolean.TRUE);
        methods.put("power",             Boolean.TRUE);
        methods.put("sampling",          Boolean.TRUE);
        methods.put("logging",           Boolean.TRUE);
    }
    private final boolean restrictedMethod(String s) {
        if (methods.get(s) == Boolean.TRUE) {
            return true;
        } else {
            return mBrokeredDevice.restrictedMethod(s);
        }
    }
}

