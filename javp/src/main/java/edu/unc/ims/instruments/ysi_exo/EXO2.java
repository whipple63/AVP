package edu.unc.ims.instruments.ysi_exo;

import java.net.Socket;
import java.net.SocketTimeoutException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.io.IOException;
import java.net.UnknownHostException;
import java.util.List;
import java.util.Vector;
import java.util.Iterator;
import java.util.Date;
import java.text.DateFormat;
import java.text.SimpleDateFormat;
import java.text.ParseException;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;

//this is only used to get config file information
import edu.unc.ims.avp.Broker;


/**
YSI 6-Series Sonde.
This class expects a YSI 6-Series Sonde on a TCP socket connection.  For
example, the Linux 'socat' application bridges a TCP socket to a
sonde-connected serial port.  This class is suitable for using the front-facing
TCP socket to communicate with the sonde.

One must call connect() before calling any other methods.  Also, disconnect()
must be called to clear up resources, otherwise the calling application may
hang.
<p>
This minimalist example connects, receives measurements for 20 seconds,
disconnects.
<pre>
import edu.unc.ims.instruments.ysi.*;
public class Test implements Sonde6Listener {
    public Test() throws Exception {
        Sonde6 y = new Sonde6("my.host.com", 5555);
        y.addListener(this);        // register to receive data
        y.connect();                // connect
        y.startSampling();          // start sampling data
        Thread.sleep(20000);        // sleep 20 seconds
        y.disconnect();             // MUST always call this!
    }
    public static void main(String [] args) throws Exception {
        new Test();
    }
    public void onMeasurement(Sonde6Data m) {
        System.out.println(m);
    }
}
</pre>
*/
public final class EXO2 implements Runnable {
    /**
    Create a sonde communication channel.
    Creates the channel, but does not open it.

    @param  host    Hostname
    @param  port    Port number

    @see #connect
    */
    public EXO2(final String host, final int port) {
        mHost = host;
        mPort = port;
        mLogger = Logger.getLogger();
    }
    public EXO2(Broker b, final String host, final int port) {
        mBroker = b;
        mHost = host;
        mPort = port;
        mLogger = Logger.getLogger();
    }
    protected void finalize() throws Throwable {
        disconnect();
    }

    /**
    Connect to the sonde.
    Attempts to open a connection to the sonde, makes a best-effort attempt
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
    public void connect() throws UnknownStateException, UnknownHostException,
        IOException, UnsupportedStateException, TimeoutException {
        mLogger.log("Connecting to sonde", this.getClass().getName(),  LogLevel.DEBUG);

        if (mState != S_DISCONNECTED) {
            throw new UnsupportedStateException("You must call disconnect()");
        }
        mSocket = new Socket(mHost, mPort);
        mReader = new InputStreamReader(mSocket.getInputStream());
        mReaderThread = new Thread(this, this.getClass().getName());
        mReaderThread.start();
        mWriter = new PrintWriter(mSocket.getOutputStream());
        try {
            changeState("\033\r", DeviceState.DS_MENU_MAIN, 5);   // in case it is running
            setState(S_CONNECTED);
            reset();
        } catch(Exception e) {
            e.printStackTrace();
            setState(S_DISCONNECTED);
            try {
                disconnect();
            } catch(Exception ee) {};
            throw new UnknownStateException();
        }
        mLogger.log("Connected to sonde", this.getClass().getName(),  LogLevel.DEBUG);

        // get config file info if exists
        if (mBroker != null) {
            mSamplingMaxTime = Integer.parseInt(mBroker.getProperties().getProperty("sampling_max_time", "3600")) * 1000;
        }

        // get values for the sonde data that is kept out of run-time
        // I am assuming that during a sonde swap the state will become disconnected
        // and then re-connected calling this code again.
        try {
            clockSync();
            mConnectTime = System.currentTimeMillis();

            mWipesLeft = 0;     // set with wipesLeft method
            mSondeID = readSondeID();
            mSondeSN = readSondeSN();
            setSampleInterval(1000.0);  // in ms for the EXO sonde
            mSamplePeriod = readSampleInterval();// not yet implemented

        } catch (Exception e) { e.printStackTrace(); }
    }

    /**
    Disconnect.
    */
    public void disconnect() {
        synchronized(mLock) {
            mShutdown = true;
        }
        setState(S_DISCONNECTED);
    }

    /**
    Reset to a known state.
    Attempts to do a soft reset, putting the instrument into a known state.
    <ul>
    <li>Device will be paused.
    </ul>

    @throws IOException I/O error.
    @throws UnknownStateException We can't reset in this state, power cycle.
    @throws UnsupportedStateException Shouldn't happen, try again.
    @throws TimeoutException Try again.
    */
    public void reset() throws IOException, UnknownStateException,
        TimeoutException, UnsupportedStateException, Exception {
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }
        // Prompt device to update our current understanding of it's state.
        changeState("\r", DeviceState.DS_NOT_UNKNOWN, 5);
        DeviceState s = getDeviceState();
        if (s == DeviceState.DS_OPERATING) {
            try {
                pause();
                para();
            } catch(UnsupportedStateException e) {};
        } else {
            if (s != DeviceState.DS_MENU_MAIN) {
                synchronized(mLock) {
                    // Has a graceful shutdown been requested?
                    if (!mShutdown) {
                        throw new UnknownStateException( "Soft reset currently not supported in "
                            + "this state: " + getDeviceStateLabel(getDeviceState()));
                    }
                }
            }
            para();
        }
        clearExpectBuffer();
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
        UnsupportedStateException, Exception {
        if(getDeviceState() != DeviceState.DS_OPERATING) {
            return;
        }
        expect("\033\r", 10, "#");
        int maxTries = 5;
        for(int i=0;i<maxTries;i++) {
            try {
                synchronized(mLock) { if(mShutdown == true) { return; } }
                expect("\033\r", 10, "#");
                Thread.sleep(5000);
                setDeviceState(DeviceState.DS_MENU_MAIN);
                break;
            }catch(Exception e) {
                if(i==maxTries) { throw e; }
            }
        }
        clearExpectBuffer();
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
        int retryNum = 0;
        int retryTtlMillis = 1000;
        int retryResolutionMillis = 50;
        int totalSleepMillis = 0;
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
        boolean shutdown = false;
        
        // Need to wake instrument if it has gone to sleep
        mWriter.print("\r");
        mWriter.flush();

        // If the instrument was asleep this will wake it up, but time out
        // If it was awake it will read one prompt
        try { waitForLines(2, 1);   // 1 line, 1 second
        } catch (Exception e) { /* do nothing if this times out */ }
        clearExpectBuffer();
        
        for (retryNum = 0; ((retryNum < maxRetries) && (!done) && (!shutdown)); retryNum++) {
//            mWriter.print(cmd + "\r");
            mWriter.print("\b\b" + cmd);
            mWriter.flush();
//            System.out.println("'\nWriting: '\b\b" + cmd + "'\nReading: '");
            totalSleepMillis = 0;
            while (totalSleepMillis < retryTtlMillis) {
                DeviceState s = getDeviceState();
                if ((targetState == DeviceState.DS_NOT_UNKNOWN) && (s != DeviceState.DS_UNKNOWN)) {
                    done = true;
                    break;
                } else if (s == targetState) {
                    done = true;
                    break;
                }
                try {
                    Thread.sleep(retryResolutionMillis);
                    totalSleepMillis += retryResolutionMillis;
                    synchronized(mLock) {
                        // Has a graceful shutdown been requested?
                        if (mShutdown) {
                            // Yes, exit the thread
                            shutdown = true;
                            break;
                        }
                    }
                } catch(InterruptedException e) {  }
            }
        }
        if(shutdown) {
            return;
        }
        if (!done) {
            throw new TimeoutException("Timeout waiting for state change to "
                + getDeviceStateLabel(targetState));
        }
    }

    /**
    Go into operational mode and collect data.

    @throws UnsupportedStateException   Check message for details.
    @throws TimeoutException Timeout
    */
    public boolean startSampling() {
        boolean retval = false;
        
        if (!mBroker.getBrokeredDevice().getSampling()) { // if already sampling, ignore
            if (mState == S_CONNECTED) {    // must be connected
                if (getWipesLeft() == 0) {  // can't be wiping
                    try {
                        if (System.currentTimeMillis() > mSamplingStartTime + mClockSyncPeriod ) {
                            clockSync();
                        }
                        changeState("run\r", DeviceState.DS_OPERATING, 3);
                    } catch (Exception e) {
                        mLogger.log("Exception during startSampling: " + e.getMessage(),
                                this.getClass().getName(),  LogLevel.ERROR);
                    }
                    mSamplingStartTime = System.currentTimeMillis();
                    retval = true;
                }
            }
        } else {
            mLogger.log("Sonde already sampling - doing nothing.", this.getClass().getName(), LogLevel.DEBUG);
        }
        
        return retval;
    }
    
    
    /**
    Go into pause mode, stop sampling.

    @throws UnsupportedStateException   Check message for details.
    @throws TimeoutException   Timeout
    @throws UnknownStateException   Check message for details.
    */
//    public void stopSampling() throws UnsupportedStateException,
//        TimeoutException, UnknownStateException, Exception {
//        mSampling = false;
//        if (mState != S_CONNECTED) {
//            throw new UnsupportedStateException("You must call connect()");
//        }
//        if (getDeviceState() == DeviceState.DS_MENU_MAIN) {
//            return;
//        }
//        pause();
//    }
    public boolean stopSampling() {
        boolean retval = false;

        if (mState == S_CONNECTED) {    // must be connected
            if (mBroker.getBrokeredDevice().getSampling()) {
                try {
                    //pause();
                    changeState("\033\r", DeviceState.DS_MENU_MAIN, 5);
                    retval = true;
                } catch(Exception e) {
                    mLogger.log("Exception during stopSampling: " + e.getMessage(),
                            this.getClass().getName(),  LogLevel.ERROR);
                }
            } else {
                retval = true;
            }
        }
        return retval;
    }

    /*
    Run para command.
    */
    private void para() throws Exception {
        expect("para\r", 30, "#");
        synchronized(mLines) {
            /* Should return something like:
                para
                52, 43, 23
                #
            Where the numbers are data element identifiers
            */
            Iterator<String> it = mLines.iterator();
            while(it.hasNext()) {
                String s = it.next();
                String [] ids = s.split(" ");
                if(ids.length <= 1) {  continue; }
                try {
                    Integer.parseInt(ids[0]);
                }catch (Exception e) {
                    continue;
                }
                mIdentifiers = new Vector<String>();
                for (int i = 0; i < ids.length; i++) {
                
                    // The EXO sonde has a parameter vertical_pos which represents unfiltered depth
                    // values.  Since that is what we want depth_m to represent, I change 240 (vertical pos)
                    // to 22 (depth_m).  If both exist in the data stream, whichever comes last will overwrite
                    // the earlier value.
                    if (ids[i].contentEquals("240")) {
                        ids[i] = "22";
                    }

                    mIdentifiers.add(ids[i]);
                }
                mNumParams = ids.length;
                mPrettyIds = EXO2Data.mapParaIdsToPrettyIds(mIdentifiers);
                String x = "";
                Iterator<String> j = mPrettyIds.iterator();
                while(j.hasNext()) {
                    String y = j.next();
                    x += y + ", ";
                }
            }
        }
    }

    // Because there is not date command with the EXO sonde, we will assume that the date 
    // is correct.
    public Long readSondeDateTime() throws Exception {
        Date today;
        DateFormat dateFormatter;
        SimpleDateFormat ft = new SimpleDateFormat ("MM/dd/yy H:mm:ss");
        Long lt = 0L;
                
        dateFormatter = DateFormat.getDateInstance(DateFormat.SHORT);
        today = new Date();
        String sDateTime = dateFormatter.format(today);

        String cmd = "time\r";
        expect(cmd, 30, "#");
        synchronized(mLines) {
            /* Should return something like:
                time
                09:36:49
                #
            */
            if (mLines.size() >= 3) { sDateTime = sDateTime.trim() + " " + mLines.get(1).trim(); }
        }
        clearExpectBuffer();
        
        try {
            lt = ft.parse(sDateTime).getTime();
        } catch (ParseException e) { 
            mLogger.log("Sonde date/time parse exception: " + sDateTime, this.getClass().getName(),  LogLevel.WARN);
        }
        return lt;
    }


    public String readSondeID() throws Exception {
        String sID = "EXO Sonde";
        return sID;
    }

    public String readSondeSN() throws Exception {
        String sSN = "";
        String cmd = "sn\r";
        expect(cmd, 30, "#");
        synchronized(mLines) {
            /* Should return something like:
                sn
                0167BF55
                #
            */
            if (mLines.size() >= 3) { sSN = mLines.get(1); }
        }
        clearExpectBuffer();
        return sSN;
    }

    public void setSampleInterval(double interval) throws Exception {
        String cmd = "Setperiod " + interval + "\r";
        expect(cmd, 30, "#");
        clearExpectBuffer();
    }

    public Double readSampleInterval() throws Exception {
        Double sint = -99.0;
        String cmd = "Setperiod\r";
        expect(cmd, 30, "#");
        synchronized(mLines) {
            /* Should return something like:
                sinterval
                1
                #
            */
            if (mLines.size() >= 3) { sint = Double.valueOf(mLines.get(1)); }
        }
        clearExpectBuffer();
        return sint;
    }


// Command not avilable with DCP2    
//    public void deviceReset() throws Exception {
//        clearExpectBuffer();
//        expect("reset\r", 30, "#");
//        synchronized(mLines) {
//            /* These lines are available in mLines after reset:
//            reset
//            OK
//            YSI Water Quality Systems Model 6600EDS
//            Version 3.06 03-06-2007 11:11:36
//            Copyright (c) 1992-2006 YSI Incorporated.
//            All rights reserved.
//
//            Type MENU<Enter> for instrument menu.
//            #
//            */
//            clearExpectBuffer();
//        }
//    }

    public void wipe() throws Exception {
        expect("Twipeb\r", 60, "#");
        clearExpectBuffer();
        try { mWipesLeft = wipesLeft();     // init wipes left
        } catch (Exception ee) { ee.printStackTrace(); }
    }
    
    private Integer wipesLeft() throws Exception {
        expect("Hwipesleft\r", 30, "#");
        Integer wl=99; // wipes left
        synchronized(mLines) {
            /* Should return something like:
                Hwipesleft
                1 193
                #
            We wait until there is a single digit == 0, indicating done
            */
            if (mLines.size() >= 3) {
                String [] fields = mLines.get(1).split(" ");
                wl = Integer.parseInt(fields[0]);
            }
        }
        clearExpectBuffer();
        return wl;
    }

// Calibration is not avilable with the DCP 2    
//    public void calibratePressure() throws Exception {
//        calibrate(3, 0.000);
//    }
//
//    public void calibrate(final int target, final double value) throws Exception {
//        String cmd = "calibrate " + target + " " + value + "\r";
//        expect(cmd, 30, "#");
//        clearExpectBuffer();
//    }

    public void clockSync() throws Exception {
        Date today;
        String dateOut, timeOut;
        DateFormat dateFormatter;
        SimpleDateFormat timeFormatter;
        
        dateFormatter = DateFormat.getDateInstance(DateFormat.SHORT);
        today = new Date();
        dateOut = dateFormatter.format(today);

        Long sysTime = today.getTime();
        Long sondeTime = readSondeDateTime();
        
        
        Logger.getLogger().log("ClockSync read sonde clock as: " +
                new Date(sondeTime).toString() + ", system time is: " + today.toString(),
                this.getClass().getName(), LogLevel.DEBUG);
        
        if ( Math.abs(sondeTime - today.getTime()) > 300000 ) {  // 5 minutes
            Logger.getLogger().log("Sonde clock more than 5 minutes from system clock.", this.getClass().getName(), LogLevel.WARN);
        }

        // set clock if necessary
        if ( Math.abs(sondeTime - sysTime) > 2000 ) {  // 2 seconds
            Logger.getLogger().log("Setting Sonde clock.", this.getClass().getName(), LogLevel.DEBUG);

            today = new Date();
            dateOut = dateFormatter.format(today);
            timeFormatter = new SimpleDateFormat("H:mm:ss");
            timeOut = timeFormatter.format(new Date(today.getTime() + 1000)); // add 1 sec to deal with delays
            
            String cmd = "time " + timeOut + "\r";
            expect(cmd, 30, "#");
            clearExpectBuffer();

// Unfortunately with the DCP, the date command isnt available            
//            cmd = "date " + dateOut + "\r";
//            expect(cmd, 30, "#");
//            clearExpectBuffer();
        }        
    }

    /*
    Set internal state.
    */
    private void setState(int state) {
        mState = state;
    }

    /*
    Set device state.
    @param  s   New state
    */
    private synchronized void setDeviceState(final DeviceState s) {
        synchronized(mLock) { if (mDeviceState != s) { mDeviceState = s; } }
    }

    /*
    Get device state.
    @return state.
    */
    private synchronized DeviceState getDeviceState() {
        DeviceState x;
        synchronized(mLock) { x = mDeviceState; }
        return x;
    }

    public boolean isConnected() {
        if (mState == S_CONNECTED) { return true; }
        else { return false; }
    }

    /**
    Reader loop.
    */
    public void run() {
        synchronized(mLock) { mShutdown = false; }      // reset the shutdown flag
        /*
        Try to divine the current device state and reflect it internally.
        Pull out relevant data if operational and trigger listeners.
        */
        int localState = 0;
        boolean shutdown = false;
        while (!shutdown) {
            // check the timeouts
            if ( mBroker.getBrokeredDevice().getSampling() ) { // is sampling
                if (System.currentTimeMillis() > mSamplingStartTime + mSamplingMaxTime ) {
                    Logger.getLogger().log("Sonde sampling timed out.", this.getClass().getName(), LogLevel.WARN);
//                    try { stopSampling(); } catch (Exception e) { /* nothing */ }
                    try { mBroker.getBrokeredDevice().setSampling( false ); } catch (Exception e) { /* nothing */ }
                }
            }

            // Try to read a line
            String l = "";
            boolean error = false;
            boolean readLine = false;
            while ((!readLine) && (!error)) {
                try {
                    // Has a graceful shutdown been requested?
                    synchronized(mLock) { if (mShutdown) { shutdown = true; break; } }

                    mSocket.setSoTimeout(500);
                    int c = mReader.read();
//                    System.out.print( (char) c);    // for debugging
                    
                    if (c == '#') {
                        mReader.read(); // read the following space
                        
                        // YSI's interface prints a prompt during run mode.  Here we will
                        // wait for a little more than 1 second and if we get a character
                        // we may have data
                        mSocket.setSoTimeout(1500);
                        try { c = mReader.read(); } 
                        catch(Exception e) {
                            if (e instanceof SocketTimeoutException) {
                                l = "#";
                                readLine = true;
                            } else {
                                e.printStackTrace();
                                error = true;
                                break;
                            }
                        }
                        if (!readLine) {    // if we didn't time out (got a char)
                            l += "# " + (char)c;
//                            System.out.print( (char) c);    // for debugging
                            continue;
                        }

                    } else if (c == -1) {
                        shutdown = true;
                        error = true;
                    } else if (c == '\n') {
                        readLine = true;
                    } else {
                        l += (char)c;
                        continue;
                    }
                } catch(Exception e) {
                    if (e instanceof SocketTimeoutException) {
                        continue;
                    } else {
                        e.printStackTrace();
                        error = true;
                        break;
                    }
                }
            }

            if (error) { continue; }

            l = l.trim();
            addExpectLine(l);
            // Heuristically try to figure out the state.
            // need regex here to parse the data output
            String [] fields = l.split(" ");
            if (l.equals("")) { continue; }     // We can safely ignore blank lines
            if (l.contains("***")) { continue; }    // This is not a data line
            if (l.contains("\000")) {
                // watch for null characters in the data stream
                mLogger.log("Line contains null.", this.getClass().getName(),  LogLevel.INFO);
                continue;
            }
            // Use a state machine since some messages span multiple lines
            if (localState == 0) {
                if (l.equals("#")) {
                    setDeviceState(DeviceState.DS_MENU_MAIN);
//                    System.out.println("set device state DS_MENU_MAIN");
                } else if ((l.startsWith("*")) || (fields.length > mNumParams)) {
                    try {
                        // try to create data, getting rid of that pesky prompt,
                        // and adding '/' and ':' back in the date and time
                        String ll = l.substring(2,4) + "/" + l.substring(4,6) + "/" + l.substring(6,8);
                        ll += l.substring(8,11) + ":" + l.substring(11,13) + ":" + l.substring(13);
//                        System.out.println(ll);
                        EXO2Data sd = new EXO2Data(mIdentifiers, ll);
                        if (sd.mConstructorSuccess == true) {
                            notifyListeners(sd);
                        }
                    } catch(Exception e) {
                        e.printStackTrace();
                    }
                    setDeviceState(DeviceState.DS_OPERATING);
//                    System.out.println("set device state DS_OPERATING");
                } else {
                    setDeviceState(DeviceState.DS_UNKNOWN);
                }
            }
        }
        // We're gracefully exiting, try to close the socket on the way out
        try {
            mSocket.close();
        } catch(Exception e) {
            e.printStackTrace();
        }
    }

    /*
    Keeps track of lines read by the reader thread.
    */
    private void addExpectLine(String l) {
        synchronized(mLines) { mLines.add(l); }
    }

    private void clearExpectBuffer() {
        synchronized(mLines) { mLines.clear(); }
    }

    /**
     * Sends cmd to sonde and waits for expected reply.
     *
     * @param cmd
     * @param ttl_secs
     * @param target
     * @throws Exception
     */
    private void expect(final String cmd, final long ttl_secs, final String target) throws Exception { 
        if ( !mBroker.getBrokeredDevice().getSampling() ) { // not if we are already sampling
            // Need to wake instrument if it has gone to sleep
            int maxTries = 10;
            for(int i=0;i<maxTries;i++) {
                clearExpectBuffer();

//                System.out.println("Sending cr #" + i);
                mWriter.print("sn\r");  // anything to force a response
                mWriter.flush();

                // If the instrument was asleep this will wake it up, but time out
                // If it was awake it will read one prompt
                try { waitForLines(2, 1);   // # lines, 1 second
                } catch (Exception e) { /* keep trying if this times out */
                    continue;
                }
                clearExpectBuffer();
                break;  // if we get here we are done
            }
        }
        
//        System.out.println("Sending command:" + cmd);
        mWriter.print("\b\b" + cmd);
        mWriter.flush();
//        System.out.println("'\nWrote: '\b\b" + cmd + "'\nReading: '");
        boolean done = false;
        while(!done) {
            waitForLines(2, ttl_secs);
            synchronized(mLock) { if(mShutdown == true) { return; } }
            synchronized(mLines) { if(mLines.contains(target)) { done = true; } }
        }
    }

    /*
    Wait for a certain number of lines to be read.
    */
    private void waitForLines(final int cnt, final long ttl_secs) throws Exception {
        long totalSlept = 0;
        long sleepTime = 100;
        long maxSleep = ttl_secs * 1000;
        for(;;) {
            Thread.sleep(sleepTime);
            synchronized(mLines) { if(mLines.size() >= cnt) { break; } }
            totalSlept += sleepTime;
            if(totalSlept >= maxSleep) { throw new Exception("timeout waiting for lines"); }
            synchronized(mLock) { if (mShutdown == true) { return; } }
        }
    }


    /**
    Listen for measurements.
    @param  l   The listener
    */
    public void addListener(EXO2Listener l) {
        mListeners.add(l);
    }

    /**
    Send data to listeners.
    @param  data    data to send.
    */
    private void notifyListeners(EXO2Data data) {
        synchronized (mListeners) {
            if ( !mBroker.getBrokeredDevice().getSampling() ) { return; } // Only send data if we're in collection mode.
            Iterator <EXO2Listener>i = mListeners.iterator();
            while(i.hasNext()) {
                EXO2Listener l = i.next();
                l.onMeasurement(data);
            }
        }
    }

    /**
    Get data identifiers.
    @return list of data element identifiers (integers) supported by the Sonde.
    */
    public List<String> getDataIdentifiers() {
        return mPrettyIds;
    }

    /**
    Get the state in human readable form.
    @return label
    */
    private String getDeviceStateLabel(DeviceState s) {
        return DS_LABELS[s.ordinal()];
    }
    /** Device states. */
    enum DeviceState { DS_UNKNOWN, DS_MENU_MAIN, DS_OPERATING, DS_NOT_UNKNOWN };
    /** State labels. */
    private static final String [] DS_LABELS = {"UNKNOWN", "MAIN_MENU",
        "OPERATING", "NOT_UNKNOWN" };

    /**
    Disconnected state.
    */
    private static final int S_DISCONNECTED = 0;

    /**
    Connected state.
    */
    private static final int S_CONNECTED = 1;

    /**
    Sampling mode.
    True if user has requested sampling mode, false if not.
    */
//    private boolean mSampling = false;
//    public boolean isSampling() {
//        return mSampling;
//    }
    
    /**
    List of Listeners.
    */
    private List<EXO2Listener> mListeners = new
        Vector<EXO2Listener>();

    private String mLock = "lock";
    private List<String> mLines = new Vector<String>();

    /**
    Identifiers.
    Contains a list of data element identifiers (integers) supported by the
    Sonde.
    */
    private List<String> mIdentifiers = new Vector<String>();
    private List<String> mPrettyIds = new Vector<String>();

    /**
    Internal device state.
    */
    private DeviceState mDeviceState = DeviceState.DS_UNKNOWN;

    /**
    Internal state.
    */
    private int mState = S_DISCONNECTED;

    /**
    Flag to indicate that a shutdown has been requested (via finalize).
    */
    private boolean mShutdown = false;

    /**
    Hostname.
    */
    private String mHost;

    /**
    Port number.
    */
    private int mPort;

    private Broker mBroker = null;

    /**
    Socket.
    */
    private Socket mSocket;

    /**
    Reader.
    */
    private InputStreamReader mReader;

    /**
    Writer.
    */
    private PrintWriter mWriter;

    /**
    Reader thread.
    */
    private Thread mReaderThread;

    /**
    Line.
    */
    private String mLine;

    private Logger mLogger;

    // Since the sonde data class is designed for data that is collected during
    // run mode, this is where we will keep data that is collected out of run mode
    // such as the serial number, ID name etc.
    private Long mConnectTime;  /** time of connection - and when these data are read */
    public Long getConnectTime() { return mConnectTime; }
    private Boolean mFilter;    /** sonde data filtering option */
    private Double mFilterTC;   /** filter time constant */
    private Integer mWipesLeft; /** wipes remaining in sensor wipe cycle */
    private String mSondeID;    /** ID name of sonde */
    private String mSondeSN;   /** sonde serial number */
    private Double mSamplePeriod; /** run time sample period in seconds */
    // access
    public Boolean getFilter() { return mFilter; }
    public Double getFilterTC() { return mFilterTC; }
    public Integer getWipesLeft() {
        if (getDeviceState() != DeviceState.DS_OPERATING) {
            try { mWipesLeft = wipesLeft();
            } catch (Exception ee) { ee.printStackTrace(); }
        }
        return mWipesLeft;
    }
    public String getSondeID() { return mSondeID; }
    public String getSondeSN() { return mSondeSN; }
    public Double getSamplePeriod() { return mSamplePeriod; }

    /** some operations need timeouts to defend against software problems
     *  (times are in ms)
     */
    private long mSamplingStartTime= 0;
    private int  mSamplingMaxTime  = 3600 * 1000;

    private int mClockSyncPeriod = 900 * 1000;  // sync the clock if 15 mins have passed
    private int mNumParams = 99;    // number of parameters, returned by the para command
}
