package edu.unc.ims.instruments.isco;

import java.net.Socket;
import java.io.PrintWriter;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;
import java.net.UnknownHostException;
import java.util.List;
import java.util.Vector;
import java.util.Iterator;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;

public final class Isco implements Runnable, IscoListener {

    private static final boolean mDebugThis = true;

    private static final int S_DISCONNECTED = 0;        /** Disconnected state. */
    private static final int S_CONNECTED = 1;           /** Connected state. */
    private int mState = S_DISCONNECTED;                /** Internal state. */

    private boolean mSampling = false;  /** are we sampling */
    private boolean mShutdown = false;  /** Shutdown requested (via finalize). */

    private String mHost;       /** Host name. */
    private int mPort;          /** Port number. */
    private Socket mSocket;     /** Socket. */

    private PrintWriter mWriter;        /** Writer.  */
    private BufferedReader mReader;     /** Reader. */
    private Thread mReaderThread;       /** Reader thread. */
    private static final long READ_TIMEOUT = 2000;
    private static final long SLEEP_INTERVAL = 20;

    private static final int DEFAULT_SAMPLE_VOLUME = 1000;

    /** List of Listeners. */
    private List<IscoListener> mListeners = new Vector<IscoListener>();
    private final String mLock = "lock";

    /** Internal copy of most recent data */
    public IscoData mIscoData;


    /**
     * main routine for testing only
     * @param args the command line arguments (are ignored)
     */
    public static void main(String[] args) throws UnknownHostException, InterruptedException,
            IOException, UnknownStateException, UnsupportedStateException, TimeoutException {
//        Isco isc = new Isco("eddy.ims.unc.edu", 55235);
        Isco isc = new Isco("avp3.dyndns.org", 55235);
        isc.addListener(isc);        // register to receive data
        isc.connect();               // connect
        System.out.println("Connected to ISCO");
        Thread.sleep(2000);          // sleep 10 seconds
        isc.softPowerSampler();      // turn isco on at panel if it was off and get status
        System.out.println("ISCO soft power on");
        isc.onMeasurement(isc.mIscoData);   // print the status
        Thread.sleep(10000);         // sleep
        System.out.println("Taking ISCO sample");
        isc.takeSample();            // take a sample -- CHECK THE STATUS TO MAKE SURE IT WORKED!
        isc.onMeasurement(isc.mIscoData);   // print the status
        Thread.sleep(10000);
        for (int i=0; i<30; i++) {
            isc.pollStatus();
            isc.onMeasurement(isc.mIscoData);   // print the status
            Thread.sleep(10000);
        }
        isc.disconnect();            // must always call this!
    }
    public void onMeasurement(IscoData d) {
        System.out.println("---isco status---\n" + d.toString());
    }


    /**
    Creates the channel, but does not open it.
    @param  host    Host name
    @param  port    Port number
    @see #connect
     */
    public Isco(final String host, final int port) {
        mHost = host;
        mPort = port;
    }

    public boolean isConnected() {
        return (mState == S_CONNECTED);
    }

    /**
    Listen for measurements.
    @param  l   The listener
     */
    public void addListener(final IscoListener l) {
        mListeners.add(l);
    }

    /**
    Send data to listeners.
    @param  data    data to send.
     */
    private void notifyListeners(IscoData data) {
        /*
        Only send data if we're in collection mode.
         */
        Iterator<IscoListener> i = mListeners.iterator();
        while (i.hasNext()) {
            IscoListener l = i.next();
            l.onMeasurement(data);
        }
    }

    /**
    Create a communication channel.
    @throws UnknownHostException    Unknown host or bad IP.
    @throws IOException IO error.
    @throws UnknownStateException    If state cannot be determined.
    @throws UnsupportedStateException   Check message for details.
     */
    public void connect() throws UnknownStateException, UnknownHostException,
            IOException, UnsupportedStateException, TimeoutException {
        if (mState != S_DISCONNECTED) {
            throw new UnsupportedStateException("Already connected.");
        }
        mIscoData = new IscoData();
        mSocket = new Socket(mHost, mPort);
        mWriter = new PrintWriter(mSocket.getOutputStream());
        mReader = new BufferedReader(new InputStreamReader(mSocket.getInputStream()));
        mReaderThread = new Thread(this, this.getClass().getName());
        mReaderThread.start();
        try {
            mState = S_CONNECTED;
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            mState = S_DISCONNECTED;
            try {
                disconnect();
            } catch (Exception ee) {
            }
            throw new UnknownStateException();
        }

        // turn on sampler and get the status
        this.softPowerSampler();
        if (mIscoData.getStatusTimestamp() == null) { // failed connection
            throw new UnknownStateException();
        }
    }

    /**
    Disconnect.
     */
    public void disconnect() {
        synchronized (mLock) {
            mShutdown = true;
        }
        mState = S_DISCONNECTED;
    }

    // If we are sampling, watch for completion then notify listeners of the status
    public void run() {
        // reset the shutdown flag
        synchronized (mLock) {
            mShutdown = false;
        }

        for (;;) {
            try {
            Thread.sleep(1000);
            }
            catch (Exception e) {
                e.printStackTrace();
            }
            synchronized (mLock) {
                // Has a graceful shutdown been requested?
                if (mShutdown) {
                    // Yes, exit the thread
                    break;
                }
            }
            if (mSocket.isConnected()) {    // monitor the socket to keep our connection
                if (mSampling == true) {
                    try {
                        pollStatus();
                    } catch (TimeoutException e) {
                        Logger.getLogger().log("ISCO timeout on pollStatus call during sampling: "+e.getMessage(),
                                this.getClass().getName(), LogLevel.ERROR);
                    }
                    if (mIscoData.getSampleStatus() != 12) { // 12=sample in progress
                        Logger.getLogger().log("ISCO sample complete.  Status: "+mIscoData.getSampleStatus().toString(),
                                this.getClass().getName(), LogLevel.DEBUG);
                        mSampling = false;
                        notifyListeners(mIscoData);
                    }
                }
            } else {
                try {
                    Logger.getLogger().log("ISCO Socket not connected.  Attempting reset.",
                            this.getClass().getName(), LogLevel.ERROR);
                    softReset();
                } catch (Exception e) {
                    Logger.getLogger().log("ISCO Socket reset failed: "+e.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                }
            }
        } // for(;;)

        // We're gracefully exiting, try to close the socket on the way out
        try {
            mSocket.close();
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
        }
    }

    /**
    Attempt a soft reset.
    @throws Exception   on error.
     */
    public final void softReset() throws Exception {
        disconnect();
        Thread.sleep(1000);   // a little time to let run routine finish
        connect();
    }

    /**
     * Poll the ISCO for its current status.
     */
    public synchronized void pollStatus() throws TimeoutException {
        int c=0;
        String sr = "";     // status reply
        for (int count=3; count > 0; count--) { // willing to try three times, although first one should work
            try {
                readBanner();
                while (mReader.ready()) {
                    c=mReader.read(); // flush mReader
                    if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
                }
                mWriter.print("STS,1\r\n");
                mWriter.flush();
                // Here we want to read until the line contains the chars 'MO'
                do {
                    sr = readLine(READ_TIMEOUT);
                    if (mDebugThis == true) { System.out.println(sr); }
                } while (sr.contains("MO") == false);
            } catch(Exception e) {
                if (count == 1) {   // out of tries
                    Logger.getLogger().log(e.toString()+" called from pollStatus ", this.getClass().getName(), LogLevel.ERROR);
                    disconnect();   // mark us as disconnected
                    throw new TimeoutException("Instrument not responding.");
                }
                continue;       // keep trying
            }
            break;          // success
        }
        parseStatus(sr);
    }

    /**
     * Connect to the instrument and read the banner string.
     * Upon return the instrument will be ready to accept a command.
     *
     * TODO: Test what will happen if ISCO is in menu when called.
     */
    private synchronized void readBanner() throws TimeoutException {
        String s = "";
        int c=0;
        boolean doQuestionMarks = false;
        // if we already have read a banner, try a cr and see if we get a prompt
        if (mIscoData.getModel() != null) {
            mWriter.print("\r\n");
            mWriter.flush();
            try {
                // Here we are expecting a '>' prompt with no cr
                // Need to read until timeout or until find '>'
                long lcTime = System.currentTimeMillis();
                while (System.currentTimeMillis() - lcTime < READ_TIMEOUT) {
                    while (mReader.ready()) {
                        c = mReader.read();
                        lcTime = System.currentTimeMillis();
                        if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
                        if (c=='>') { break; }
                    }
                    if (c=='>') { break; }
                    Thread.sleep(10);
                }
                if (c!='>') { doQuestionMarks = true; }
            } catch(Exception e) {
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            }
        }
        else {  // must get banner
            doQuestionMarks = true;
        }

        // if we need to get a banner
        if (doQuestionMarks){
            for (int count=3; count > 0; count--) { // willing to try three times, although first one should work
                mWriter.print("???");
                mWriter.flush();
                try {
                    // Here we want to read until we see the word 'Model'
                    do {
                        s = readLine(READ_TIMEOUT);
                        if (mDebugThis == true) { System.out.println(s); }
                    } while (s.contains("Model") == false);
                } catch(TimeoutException e) {
                    continue;       // if we time-out go back to the for loop and try again
                } catch(IOException e) {
                    Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                }
                if (count==1) {
                    throw new TimeoutException("Timed out in readBanner waiting for crlf");
                }
                break;  // if we have read a line we should have the banner
            }
        parseBanner(s);     //Parse the banner and save the vars
        }
    }

    /**
     * Parse the banner string and set the member variables
     * @param s
     */
    private void parseBanner(String s) {
        String[] tokens = s.split("[ \t]+");
        if (tokens.length == 11) {
            mIscoData.setModel(tokens[2]);
            mIscoData.setHardwareRevision(tokens[5]);
            mIscoData.setSoftwareRevision(tokens[8]);
            mIscoData.setID(tokens[10]);
        }
    }

    /**
     * parse the status string and set member variables.
     */
    private void parseStatus(String s) {
        String[] tokens = s.split("[,]+");
        if (tokens.length == 10 || tokens.length == 18) {   // 10=No sample info available
            mIscoData.setStatusTimeStamp(System.currentTimeMillis());

            mIscoData.setModel(tokens[1]);
            mIscoData.setID(tokens[3]);
            mIscoData.setIscoStatusTime(Double.valueOf(tokens[5]));
            mIscoData.setIscoStatus(Integer.valueOf(tokens[7]));

            // set these to nonsense values here.  will get set below if avail
            mIscoData.setIscoSampleTime(0.0);
            mIscoData.setBottleNum(0);
            mIscoData.setSampleVolume(0);
            mIscoData.setSampleStatus(0);
        }
        if (tokens.length == 18) {
            mIscoData.setIscoSampleTime(Double.valueOf(tokens[9]));
            mIscoData.setBottleNum(Integer.valueOf(tokens[11]));
            mIscoData.setSampleVolume(Integer.valueOf(tokens[13]));
            mIscoData.setSampleStatus(Integer.valueOf(tokens[15]));
        }
    }

    /**
     * Turns on sampler through its software interface.
     */
    public synchronized void softPowerSampler() throws TimeoutException {
        int c=0;
        String sr = "";     // status reply
        for (int count=3; count > 0; count--) { // willing to try three times, although first one should work
            try {
                readBanner();
                while (mReader.ready()) {
                    c=mReader.read(); // flush mReader
                    if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
                }
                mWriter.print("STS,2\r\n");
                mWriter.flush();
                // Here we want to read until the line contains the chars 'MO'
                do {
                    sr = readLine(READ_TIMEOUT);
                    if (mDebugThis == true) { System.out.println(sr); }
                } while (sr.contains("MO") == false);
            } catch(Exception e) {
                if (count == 1) {   // out of tries
                    Logger.getLogger().log(e.toString()+" called from softPowerSampler ", this.getClass().getName(), LogLevel.ERROR);
                    disconnect();   // mark us as disconnected
                    throw new TimeoutException("Instrument not responding.");
                }
                continue;   // keep trying
            }
            break;      // success
        }
        parseStatus(sr);
    }

    /**
     * Default to next bottle, and full volume
     */
    public void takeSample() throws TimeoutException {
        int bnum;
        if (mIscoData.getBottleNum() == null) {
            bnum = 1;
        }
        else {
            bnum = mIscoData.getBottleNum() + 1;
        }
        if (bnum > 0 && bnum <= 24) {
            takeSample(bnum, DEFAULT_SAMPLE_VOLUME);
        }

    }
    public synchronized void takeSample(Integer bottleNum, Integer sampleVolume) throws TimeoutException {
        int c=0;
        String sr = "";     // status reply
        try {
            readBanner();
            while (mReader.ready()) {
                mReader.read(); // flush mReader
                if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
            }
            String cmd = "BTL,"+bottleNum.toString()+",SVO,"+sampleVolume.toString()+"\r\n";
            mWriter.print(cmd);
            mWriter.flush();
            mSampling = true;   // indicate the the isco is sampling (run thread wil reset)
            // Here we want to read until the line contains the chars 'MO'
            do {
                sr = readLine(READ_TIMEOUT);
                if (mDebugThis == true) { System.out.println(sr); }
            } while (sr.contains("MO") == false);
        } catch(Exception e) {
            Logger.getLogger().log(e.toString()+" called from takeSample ", this.getClass().getName(), LogLevel.ERROR);
            disconnect();   // mark us as disconnected
            throw new TimeoutException("Instrument not responding.");
        }
        parseStatus(sr);
    }

    /**
     * Read a line using a timeout.  Don't want to get stuck if newline never comes.
     * Pulled from MM3 code.  Waits for <cr><lf>
     *
     * @param timeout
     * @return String as read
     * @throws IOException
     * @throws TimeoutException
     */
    private synchronized String readLine(long timeout) throws IOException, TimeoutException {
        int c;
        int crval = 0x0D;
        int lfval = 0x0A;
        String retval = "";
        long issueTime = System.currentTimeMillis();
        boolean cr = false;
        boolean lf = false;
        boolean sleptOnce = false;
        boolean done = false;

        do {
            if (mReader.ready()) {      // if there is something to read
                mReader.mark(2);        // mark our spot before reading
                c = mReader.read();     // read
                lf = (c == lfval);      // is this linefeed?
                if (cr) {               // if we have already read a cr
                    done = true;        // if the previous char was cr we're done
                    if (!lf) {          // if this char isn't lf, put it back
                        mReader.reset();
                    }
                }
                cr = (c == crval);      // is this a cr?
                if (!cr && !lf) {       // if neither cr or lf, save chars
                    retval += (char) c;
                }
            } else if (cr) {            // if reader isn't ready and we've read cr, wait once for lf, then we're done
                if (sleptOnce == false) {
                    try {
                        Thread.sleep(SLEEP_INTERVAL);
                    } catch (InterruptedException e) {  }
                    sleptOnce = true;
                } else {
                    done = true;
                }
            } else {                    // reader isn't ready - let's wait a bit
                try {
                    Thread.sleep(SLEEP_INTERVAL);
                } catch (InterruptedException e) {
                }
            }
        } while (!done && (System.currentTimeMillis() < (issueTime + timeout)));

        if (!done) {
            throw new TimeoutException("Timed out in readLine waiting for crlf");
        } else {
            return retval;
        }
    }

}

