    package edu.unc.ims.instruments.wind.young32500;

import java.net.Socket;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.io.IOException;
import java.net.UnknownHostException;
import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;
import edu.unc.ims.instruments.wind.*;
import java.util.Arrays;


/**
Young 32500 Compass with attachments.
You must call connect() before calling any other methods.  Also, you must
call disconnect() in order to clear up resources, otherwise your application
may hang.
<p>
This minimalist example connects, receives measurements for 20 seconds,
changes the default measurement rate, waits 10 seconds, then disconnects.
<pre>
public class Test implements WindListener {
    public Test() throws Exception {
        Young32500 y = new Young32500("my.host.com", 5555);
        y.addListener(this);        // register to receive data
        y.connect();                // connect
        y.startCollection();        // start collecting data
        Thread.sleep(20000);        // sleep 20 seconds
        y.setOutputRate(Young32500.OutputRate.RATE_15); // collect data at 15Hz
        Thread.sleep(10000);        // sleep 10 seconds
        y.disconnect();             // MUST always call this!
    }
    public static void main(String [] args) throws Exception {
        new Test();
    }
    public void onMeasurement(WindData m) {
        System.out.println(m);
    }
}
</pre>
*/
public final class Young32500  extends WindInstrument implements Runnable{
    private boolean mDebugThis = false;

    private Broker mBroker;
    
    public static enum IfType {UNKNOWN, MENU, CMD_LINE};
    private IfType mInterfaceType = IfType.UNKNOWN;

    private DeviceState mDeviceState = DeviceState.DS_UNKNOWN;  // Internal device state

    private boolean mShutdown = false;  // Flag to indicate that a shutdown has been requested (via finalize)

    private OutputRate mRate = OutputRate.RATE_UNKNOWN; // Internal output rate
    private Damping mDamping = Damping.DAMPING_SLOW;    // Internal compass damping speed

    private Socket mSocket;
    private String mHost;
    private int mPort;
    private BufferedReader mReader;
    private PrintWriter mWriter;

    private Thread mReaderThread;
    
    public static enum Damping { DAMPING_NONE, DAMPING_FAST, DAMPING_SLOW };    // Compass damping

    // Device states.
    enum DeviceState { DS_UNKNOWN, DS_MENU_MAIN, DS_OPERATING, DS_OUTPUT_RATE,
        DS_COMPASS_DAMPING, DS_CMD_LINE, DS_EVALUATING_CMD, DS_NOT_UNKNOWN };

    // State labels.
    private static final String [] DS_LABELS = {"UNKNOWN", "MAIN_MENU",
        "OPERATING", "OUTPUT_RATE", "COMPASS_DAMPING", "NOT_UNKNOWN" };

    
    private static enum OutputRate { RATE_15, RATE_0_1, RATE_2, RATE_UNKNOWN };  // Output data rates

    private String mLock = "lock";

    
    /**
    Create a compass communication channel.
    Creates the channel, but does not open it.

    @param  host    Hostname
    @param  port    Port number

    @see #connect
    */
    public Young32500(final String host, final int port, final Broker broker) {
        mHost = host;
        mPort = port;
        mBroker = broker;
        OUTPUT_RATES = Arrays.asList(0.1, 2.0, 15.0);     // possible output rates
    }

    
    /**
    Connect to the compass.
    Attempts to open a connection to the compass, makes a best-effort attempt
    to determine current state of the device and puts it into a known state.
    <p>
    If successful, the state will be as described in the reset() method.
    <p>
    <b>You must call disconnect() to free up resources!</b>

    @see #reset
    @throws UnknownHostException    Unknown host or bad IP.
    @throws IOException IO error.
    @throws UnknownStateException    If state cannot be determined, a power
        cycle is probably required.
    @throws UnsupportedStateException   Check message for details.
    */
    @Override
    public void connect() throws UnknownStateException, UnknownHostException,
        IOException, UnsupportedStateException {
        if (mState != S_DISCONNECTED) {
            throw new UnsupportedStateException("You must call disconnect()");
        }
        mSocket = new Socket(mHost, mPort);
        mReader = new BufferedReader(new InputStreamReader(
            mSocket.getInputStream()));
        mReaderThread = new Thread(this, this.getClass().getName());
        mReaderThread.start();
        mWriter = new PrintWriter(mSocket.getOutputStream());
        try {
            mInterfaceType = IfType.UNKNOWN;
            setState(S_CONNECTED);
            reset();
        } catch(Exception e) {
            Logger.getLogger().log(e.toString(),
                this.getClass().getName(), LogLevel.ERROR);
            setState(S_DISCONNECTED);
            try {
                disconnect();
            } catch(Exception ee) {};
            throw new UnknownStateException();
        }
    }

    /**
    Disconnect.
    */
    @Override
    public void disconnect() {
        synchronized(mLock) {
            mShutdown = true;
        }
        setState(S_DISCONNECTED);
    }

    /**
    Attempt to change the state of the device.

    @param  cmd Command to send to the device.
    @param  targetState The desired state.
    @param  maxRetries Number of times to re-send command before error.

    @throws TimeoutException I/O or timeout
    */
    private void changeState(final String cmd, final DeviceState targetState,
        final int maxRetries) throws TimeoutException {
        int retryNum;
        int retryTtlMillis = 1000;
        int retryResolutionMillis = 50;
        int totalSleepMillis;
        boolean done = false;
        /*
        Special case for going into operational mode.  Since we want known
        states, we require that we get data back from the device to confirm
        the transition took place.  In the case of going into OPERATING,
        the response time will depend on the rate set, so we must respect
        it.
        */
        if ((targetState == DeviceState.DS_OPERATING) || (getDeviceState() ==
            DeviceState.DS_UNKNOWN)) {
            retryTtlMillis = 10000;
        }
        for (retryNum = 0; ((retryNum < maxRetries) && (!done));
            retryNum++) {
            mWriter.print(cmd+"\r\n");  // wind expects CRLF as line terminator
            mWriter.flush();
            if (getDeviceState() == DeviceState.DS_CMD_LINE) { setDeviceState(DeviceState.DS_EVALUATING_CMD); }
            if (mDebugThis == true) {System.out.println(cmd);}
            totalSleepMillis = 0;
            while (totalSleepMillis < retryTtlMillis) {
                DeviceState s = getDeviceState();
                if ((targetState == DeviceState.DS_NOT_UNKNOWN) && (s !=
                    DeviceState.DS_UNKNOWN)) {
                    done = true;
                    break;
                } else if (s == targetState) {
                    done = true;
                    break;
                }
                try {
                    Thread.sleep(retryResolutionMillis);
                    totalSleepMillis += retryResolutionMillis;
                } catch(InterruptedException e) {
                }
            }
        }
        if (!done) {
            throw new TimeoutException("Timeout waiting for state change to "
                + getDeviceStateLabel(targetState));
        }
    }

    /**
    Pauses the data stream.

    It is often useful to pause the data stream.  This puts the device at it's
    main menu.

    @throws TimeoutException   On timeout, try again.
    @throws UnknownStateException   Must cycle power.
    @throws UnsupportedStateException   Check message for details.
    */
    private void pause() throws TimeoutException, UnknownStateException,
        UnsupportedStateException {
        /*
        Send three esc characters followed by newline to pause and enter
        menu.
        */
        DeviceState targetState;
        if (mInterfaceType == IfType.CMD_LINE) {
            targetState = DeviceState.DS_CMD_LINE;
        } else {
            targetState = DeviceState.DS_MENU_MAIN;
        }
        if (getDeviceState() == targetState) {
            // already paused
            return;
        } else if (getDeviceState() == DeviceState.DS_OPERATING) {
            changeState("\u001B\u001B\u001B", targetState, 3);
        } else {
            throw new UnknownStateException("Unsupported state, cycle power: "
            + getDeviceStateLabel(getDeviceState()));
        }
    }

    /**
    Go into operational mode and collect data.

    @throws UnsupportedStateException   Check message for details.
    @throws TimeoutException Timeout
    */
    @Override
    public boolean startSampling() {
        DeviceState targetState;
        String stateCmd;
        boolean retval = false;

        if (mState == S_CONNECTED) {
            if (mInterfaceType == IfType.CMD_LINE) {
                targetState = DeviceState.DS_CMD_LINE;
                stateCmd = "CMD100";
            } else {
                targetState = DeviceState.DS_MENU_MAIN;
                stateCmd = "X";
            }

            if (getDeviceState() == targetState) {
                try {
                    changeState(stateCmd, DeviceState.DS_OPERATING, 5);
                } catch (Exception e) {
                    Logger.getLogger().log("Exception during startSampling: " + e.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                }
                retval = true;
            }
        }
        return retval;
    }

    
    /**
    Go into pause mode, stop collecting data.

    @throws UnsupportedStateException   Check message for details.
    @throws TimeoutException   Timeout
    @throws UnknownStateException   Check message for details.
    */
    @Override
    public boolean stopSampling() {
        boolean retval = false;

        if (mState == S_CONNECTED) {
            if (getDeviceState() == DeviceState.DS_MENU_MAIN) {
                return true;
            }
            try {
                pause();
            } catch (Exception e) {
                Logger.getLogger().log("Exception during stopSampling: " + e.getMessage(),
                        this.getClass().getName(), LogLevel.ERROR);
            }
        }
        
        return retval;
    }

   /**
     * Sets the output rate.
     * @param    rs    One of 0.1, 2, 15, all in Hz.
     * @throws Exception on error.
     */
    @Override
    public void setOutputRate(final double rs) throws Exception {
        OutputRate r;
        if (rs == 0.1) {
            r = OutputRate.RATE_0_1;
        } else if (rs == 15.0) {
            r = OutputRate.RATE_15;
        } else if (rs == 2.0) {
            r = OutputRate.RATE_2;
        } else {
            return;
        }
        setOutputRate(r);
    }

    /**
    Set output rate.
    Set the the rate at which data will be transmitted from the device when
    collecting data.

    @param  rate   Rate value
    @throws TimeoutException Timeout, try again.
    @throws UnsupportedStateException Try a reset() first.
    @throws UnknownStateException Corrupt state, power cycle.
    */
    private void setOutputRate(final OutputRate rate) throws TimeoutException,
        UnknownStateException, UnsupportedStateException {
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }
        String cmd = "A";
        if (rate == OutputRate.RATE_15) {
            if (mInterfaceType == IfType.CMD_LINE) { cmd = "0"; }
            else { cmd = "A"; }
        } else if (rate == OutputRate.RATE_2) {
            if (mInterfaceType == IfType.CMD_LINE) { cmd = "2"; }
            else { cmd = "B"; }
        } else if (rate == OutputRate.RATE_0_1) {
            if (mInterfaceType == IfType.CMD_LINE) { cmd = "1"; }
            else { cmd = "C"; }
        }
        DeviceState s = getDeviceState();
        if (s == DeviceState.DS_OPERATING) {
            pause();
            if (mInterfaceType == IfType.CMD_LINE) {
                changeState("CMD220 "+cmd, DeviceState.DS_CMD_LINE, 5);
                changeState("CMD100", DeviceState.DS_OPERATING, 5);
            } else {
                changeState("R", DeviceState.DS_OUTPUT_RATE, 5);
                changeState(cmd, DeviceState.DS_MENU_MAIN, 5);
                changeState("X", DeviceState.DS_OPERATING, 5);
            }
            mRate = rate;
        } else if (s == DeviceState.DS_MENU_MAIN) {
            changeState("R", DeviceState.DS_OUTPUT_RATE, 5);
            changeState(cmd, DeviceState.DS_MENU_MAIN, 5);
            mRate = rate;
        } else if (s == DeviceState.DS_CMD_LINE) {
            changeState("CMD220 "+cmd, DeviceState.DS_CMD_LINE, 5);
            mRate = rate;
        } else {
            throw new UnsupportedStateException("setOutputRate: Unsupported "
                + "intial state: " + getDeviceStateLabel(s));
        }
    }

    @Override
    public double getOutputRateAsDouble() {
        if (mRate == OutputRate.RATE_15) {
            return 15.0;
        } else if (mRate == OutputRate.RATE_2) {
            return 2.0;
        } else {
            return 0.1;
        }
    }

    /**
    Set damping.
    Determines the amount of averaging applied to the compass measurement.

    @param  damping   Damping value
    @throws TimeoutException Timeout, try again.
    @throws UnsupportedStateException Try a reset() first.
    @throws UnknownStateException Corrupt state, power cycle.
    */
    public void setDamping(final Damping damping) throws TimeoutException,
        UnknownStateException, UnsupportedStateException {
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }
        String cmd = "N";
        if (damping == Damping.DAMPING_NONE) {
            if (mInterfaceType == IfType.CMD_LINE) { cmd = "0"; }
            else { cmd = "N"; }
        } else if (damping == Damping.DAMPING_FAST) {
            if (mInterfaceType == IfType.CMD_LINE) { cmd = "1"; }
            else { cmd = "F"; }
        } else if (damping == Damping.DAMPING_SLOW) {
            if (mInterfaceType == IfType.CMD_LINE) { cmd = "2"; }
            else { cmd = "S"; }
        }
        DeviceState s = getDeviceState();
        if (s == DeviceState.DS_OPERATING) {
            pause();
            if (mInterfaceType == IfType.CMD_LINE) {
                changeState("CMD200 "+cmd, DeviceState.DS_CMD_LINE, 5);
                changeState("CMD100", DeviceState.DS_OPERATING, 5);
            } else {
                changeState("D", DeviceState.DS_COMPASS_DAMPING, 5);
                changeState(cmd, DeviceState.DS_MENU_MAIN, 5);
                changeState("X", DeviceState.DS_OPERATING, 5);
            }
            mDamping = damping;
        } else if (s == DeviceState.DS_MENU_MAIN) {
            changeState("D", DeviceState.DS_COMPASS_DAMPING, 5);
            changeState(cmd, DeviceState.DS_MENU_MAIN, 5);
            mDamping = damping;
        } else if (s == DeviceState.DS_CMD_LINE) {
            changeState("CMD200 "+cmd, DeviceState.DS_CMD_LINE, 5);
            mDamping = damping;
        } else {
            throw new UnsupportedStateException("setDamping: Unsupported "
                + "intial state: " + getDeviceStateLabel(s));
        }
    }

    /**
    Reset to a known state.
    Attempts to do a soft reset, putting the instrument into a known state.
    <ul>
    <li>Device will be paused.
    <li>Output rate set to 2Hz.
    <li>Compass damping set to slow.
    </ul>

    @throws IOException I/O error.
    @throws UnknownStateException We can't reset in this state, power cycle.
    @throws UnsupportedStateException Shouldn't happen, try again.
    @throws TimeoutException Try again.
    */
    @Override
    public void reset() throws IOException, UnknownStateException,
        TimeoutException, UnsupportedStateException {
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }
        // Prompt device to update our current understanding of it's state.
        changeState("", DeviceState.DS_NOT_UNKNOWN, 5);
        DeviceState s = getDeviceState();
        if (s == DeviceState.DS_OPERATING) {
            try {
                pause();
            } catch(UnsupportedStateException e) {};
        } else if (s == DeviceState.DS_OUTPUT_RATE) {
            changeState("X", DeviceState.DS_MENU_MAIN, 5);
        } else if (s == DeviceState.DS_COMPASS_DAMPING) {
            changeState("X", DeviceState.DS_MENU_MAIN, 5);
        } else {
            if (s != DeviceState.DS_MENU_MAIN && s != DeviceState.DS_CMD_LINE) {
                throw new UnknownStateException(
                    "Soft reset currently not supported in "
                    + "this state: " + getDeviceStateLabel(getDeviceState()));
            }
        }
        setOutputRate(OutputRate.RATE_2);
        mRate = OutputRate.RATE_2;
        setDamping(Damping.DAMPING_SLOW);
        mDamping = Damping.DAMPING_SLOW;
    }

    /**
    Set state.

    @param  s   New state
    */
    private synchronized void setDeviceState(final DeviceState s) {
        synchronized(mLock) {
            if (mDeviceState != s) {
                mDeviceState = s;
            }
        }
    }

    /**
    Get state.

    @return state.
    */
    private synchronized DeviceState getDeviceState() {
        DeviceState x;
        synchronized(mLock) {
            x = mDeviceState;
        }
        return x;
    }

    /**
    Reader loop.
    */
    @Override
    public void run() {
        // reset the shutdown flag
        synchronized(mLock) {
            mShutdown = false;
        }
        /*
        Try to devine the current device state and reflect it internally.
        Pull out relevant data if operational and trigger listeners.
        */
        int localState = 0;
        for (;;) {
            // First check that the socket is connected
            if (mSocket.isConnected() == false) {
                try {
                    Logger.getLogger().log("Wind Socket not connected.  Attempting reset.",
                            this.getClass().getName(), LogLevel.ERROR);
                    disconnect();
                    connect();
                } catch (Exception e) {
                    Logger.getLogger().log("Wind Socket reset failed: "+e.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                }
            }

            String l = "";
            try {
                if(mReader.ready()) {
                    // we should have data ready to read
                    l = mReader.readLine();
                    if (mDebugThis == true) { System.out.println(l); }
                    if (l == null) {
                        Logger.getLogger().log("Reader read a null",
                            this.getClass().getName(), LogLevel.INFO);
                        continue;
                    } else if (l.contains("\000")) {
                        Logger.getLogger().log("Line read contains a null",
                            this.getClass().getName(), LogLevel.INFO);
                        continue;
                    }

                } else {
                    /*
                    No data ready to read, sleep a bit and see if we need
                    to gracefully shutdown.
                    */
                    try {
                        Thread.sleep(50);
                    } catch(InterruptedException e) {
                        Logger.getLogger().log(e.toString(),
                            this.getClass().getName(), LogLevel.ERROR);
                    }
                    synchronized(mLock) {
                        // Has a graceful shutdown been requested?
                        if (mShutdown) {
                            // Yes, exit the thread
                            break;
                        }
                    }
                }
            } catch(IOException e) {
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            }
            // Heuristically try to figure out the state.
            String [] fields = l.split(" ");
            if (l.equals("")) {
                // We can safely ignore blank lines
                continue;
            }
            // Use a state machine since some messages span multiple lines
            if (localState == 0) {
                if (l.equals("COMMANDS")) {
                    localState = 1;
                    mInterfaceType = IfType.MENU;
                } else if (l.equals("OUTPUT RATE")) {
                    localState = 2;
                    mInterfaceType = IfType.MENU;
                } else if (l.equals("COMPASS DAMPING")) {
                    localState = 3;
                    mInterfaceType = IfType.MENU;
                } else if ( l.startsWith("*") || l.startsWith(">") ) {
                    mInterfaceType = IfType.CMD_LINE;
                    if (fields.length == 8) {
                        setDeviceState(DeviceState.DS_OPERATING);
                    } else {
                        setDeviceState(DeviceState.DS_CMD_LINE);
                    }
                } else if (fields.length == 8) {
                    /* We use the ASCII mode which has 8 integers */
                    for(int i = 0; i < 8; i++) {
                        try {
                            Integer.parseInt(fields[i]);
                        } catch(NumberFormatException nfe) {
                            // uh oh, we don't know what this is
                            continue;
                        }
                    }
                    try {
                        WindData d = new WindData(l);
                        notifyListeners(d);
                    } catch(Exception e) {
                        Logger.getLogger().log(e.toString(),
                            this.getClass().getName(), LogLevel.ERROR);
                    }
                    setDeviceState(DeviceState.DS_OPERATING);
                } else {
                    if (getDeviceState() == DeviceState.DS_OPERATING) {
                        Logger.getLogger().log("Wind broker read a line with an unkown format: '"+l+"'",
                                this.getClass().getName(), LogLevel.WARN);
                        try {
                            Logger.getLogger().log("Wind broker sending instrument 3 ctl-x",
                                    this.getClass().getName(), LogLevel.WARN);
                            changeState("\u0018\u0018\u0018", DeviceState.DS_OPERATING, 1);
                        } catch (Exception e) {}
                    }
                    setDeviceState(DeviceState.DS_UNKNOWN);
                }
            } else if (localState == 1) {
                if (l.equals("X) EXIT TO OPERATE MODE")) {
                    setDeviceState(DeviceState.DS_MENU_MAIN);
                    localState = 0;
                }
            } else if (localState == 2) {
                if (l.equals("X) EXIT")) {
                    setDeviceState(DeviceState.DS_OUTPUT_RATE);
                    localState = 0;
                }
            } else if (localState == 3) {
                if (l.equals("X) EXIT")) {
                    setDeviceState(DeviceState.DS_COMPASS_DAMPING);
                    localState = 0;
                }
            }
        }
        // We're gracefully exiting, try to close the socket on the way out
        try {
            mSocket.close();
        } catch(Exception e) {
            Logger.getLogger().log(e.toString(),
                this.getClass().getName(), LogLevel.ERROR);
        }
    }

    /**
    Get the state in human readable form.
    @return label
    */
    private String getDeviceStateLabel(DeviceState s) {
        return DS_LABELS[s.ordinal()];
    }

}
