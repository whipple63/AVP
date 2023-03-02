package edu.unc.ims.instruments.lisst;

import java.net.Socket;
import java.io.PrintWriter;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;
import java.net.UnknownHostException;
import java.util.List;
import java.util.Vector;
import java.util.Iterator;
import java.util.Date;
import java.text.SimpleDateFormat;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;

//this is only used to get config file information
import edu.unc.ims.avp.Broker;


public final class Lisst implements Runnable, LisstListener {

    // this enables many print statements displaying the exchange with the instrument
    private static final boolean mDebugThis = false;

    private static final int S_DISCONNECTED = 0;        /** Disconnected state. */
    private static final int S_CONNECTED = 1;           /** Connected state. */
    private int mState = S_DISCONNECTED;                /** Internal state. */

    private boolean mShutdown = false;  /** Shutdown requested (via finalize). */

    private String mHost;       /** Host name. */
    private int mPort;          /** Port number. */
    private Socket mSocket;     /** Socket. */

    private PrintWriter mWriter;        /** Writer.  */
    private BufferedReader mReader;     /** Reader. */
    private Thread mReaderThread;       /** Reader thread. */
    private static final long READ_TIMEOUT = 1000;
    private static final long SLEEP_INTERVAL = 20;

    /** List of Listeners. */
    private List<LisstListener> mListeners = new Vector<LisstListener>();
    private final String mLock = "lock";

    /** Internal copy of most recent data */
    public LisstData mLisstData;
    public boolean mLisstBusy = false;  // true when commands can't be issued

    private Broker mBroker = null;

    /** folder in which to keep files uploaded from the lisst */
    public String mLisstFileFolder = "/home/avp/lisst_files";

    /** some operations need timeout to defend against software problems
     *  (times are in ms)
     */
    private long mPumpStartTime  = 0;
    private int  mPumpMaxTime    = 600 * 1000;
    private long mSampleStartTime= 0;
    private int  mSampleMaxTime  = 600 * 1000;
    private long mFlushStartTime = 0;
    private int  mFlushMaxTime   = 20 * 1000;

    /**
     * main routine for testing only
     * @param args the command line arguments (are ignored)
     */
    public static void main(String[] args) throws UnknownHostException, InterruptedException,
            IOException, UnknownStateException, UnsupportedStateException, TimeoutException {
//        Lisst l = new Lisst("avp3.dyndns.org", 55236);
        Lisst l = new Lisst("198.85.230.125", 55236);
        l.addListener(l);        // register to receive data
        l.connect();               // connect
        System.out.println("Connected to lisst");
        Thread.sleep(2000);          // sleep

        // Try synchronizing the clocks
        l.clockSync();

        // The next lines are how start and stop clean water flush
        l.mLisstData.setCleanWaterFlush(true);  // indicate that it should happen
        l.cleanWaterFlush();                            // then make it happen
        System.out.println("Beginning clean water flush");
        Thread.sleep(5000);
        l.mLisstData.setCleanWaterFlush(false);
        l.cleanWaterFlush();
        System.out.println("Stopping clean water flush");

        Thread.sleep(2000);          // sleep

        // The next lines are how start and stop seawater pump
        l.mLisstData.setSeawaterPump(true);  // indicate that it should happen
        l.seawaterPump();                            // then make it happen
        System.out.println("Beginning seawater pump");
        Thread.sleep(5000);
        System.out.println("Beginning data collection");
        l.startCollection();

        System.out.println("Monitoring LISST output");
        // print whatever is coming for a while
        long bTime = System.currentTimeMillis();
        while (System.currentTimeMillis() - bTime < 30000) {
            while (l.mReader.ready()) {
                System.out.print( (char) l.mReader.read());
            }
        }

        // Because stopCollection takes the time to transfer the data, it is
        // better to stop the pump first
        System.out.println("Stopping seawater pump");
        l.mLisstData.setSeawaterPump(false);
        l.seawaterPump();
        System.out.println("Stopping data collection");
        l.stopCollection();
        System.out.println("\nData collected to:" + l.mLisstData.getDataFileName());

        Thread.sleep(2000);          // sleep

        // Rinse again
        l.mLisstData.setCleanWaterFlush(true);  // indicate that it should happen
        l.cleanWaterFlush();                            // then make it happen
        System.out.println("Beginning clean water flush");
        Thread.sleep(5000);
        l.mLisstData.setCleanWaterFlush(false);
        l.cleanWaterFlush();
        System.out.println("Stopping clean water flush");

        l.disconnect();            // must always call this!
    }
    public void onMeasurement(LisstData d) { // an example listener
        System.out.println("---lisst status---\n" + d.toString());
    }


    /**
    Creates the channel, but does not open it.
    @param  host    Host name
    @param  port    Port number
    @see #connect
     */
    public Lisst(final String host, final int port) {
        mHost = host;
        mPort = port;
    }
    public Lisst(Broker b, final String host, final int port) {
        mBroker = b;
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
    public void addListener(final LisstListener l) {
        mListeners.add(l);
    }

    /**
    Send data to listeners.
    @param  data    data to send.
     */
    private void notifyListeners(LisstData data) {
        Iterator<LisstListener> i = mListeners.iterator();
        while (i.hasNext()) {
            LisstListener l = i.next();
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
        mLisstData = new LisstData();
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

        // get config file info if exists
        if (mBroker != null) {
            mLisstFileFolder = mBroker.getProperties().getProperty("lisst_file_folder", "/home/avp/lisst_files");
            mPumpMaxTime   = Integer.parseInt(mBroker.getProperties().getProperty("pump_max_time",   "600")) * 1000;
            mSampleMaxTime = Integer.parseInt(mBroker.getProperties().getProperty("sample_max_time", "600")) * 1000;
            mFlushMaxTime  = Integer.parseInt(mBroker.getProperties().getProperty("flush_max_time",  "20" )) * 1000;
        }

        this.getStatus();
        if (mLisstData.getSerialNumber() == null) { // failed connection
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

    /**
    Attempt a soft reset.
    @throws Exception   on error.
     */
    public final void softReset() throws Exception {
        disconnect();
        Thread.sleep(1000);   // a little time to let run routine finish
        connect();
    }

    public void run() {
        // reset the shutdown flag
        synchronized (mLock) {
            mShutdown = false;
        }

        for (;;) {
            if (mSocket.isConnected()) {
                try {
                    // check the timeouts
                    if (mLisstData.getSeawaterPump() == true) {
                        if (System.currentTimeMillis() > mPumpStartTime + mPumpMaxTime ) {
                            Logger.getLogger().log("LISST pump timed out.",
                                    this.getClass().getName(), LogLevel.WARN);
                            mLisstData.setSeawaterPump(false);
                            seawaterPump();
                        }
                    }
                    if (mLisstData.getDataCollection() == true) {
                        if (System.currentTimeMillis() > mSampleStartTime + mSampleMaxTime ) {
                            Logger.getLogger().log("LISST data collection timed out.",
                                    this.getClass().getName(), LogLevel.WARN);
                            mLisstData.setDataCollection(false);
                            dataCollection();
                        }
                    }
                    if (mLisstData.getCleanWaterFlush() == true) {
                        if (System.currentTimeMillis() > mFlushStartTime + mFlushMaxTime ) {
                            Logger.getLogger().log("LISST clean water flush timed out.",
                                    this.getClass().getName(), LogLevel.WARN);
                            mLisstData.setCleanWaterFlush(false);
                            cleanWaterFlush();
                        }
                    }
                    Thread.sleep(1000); // not doing anything
                } catch (Exception e) { e.printStackTrace(); }
            } else {
                try {
                    Logger.getLogger().log("LISST Socket not connected.  Attempting reset.",
                            this.getClass().getName(), LogLevel.ERROR);
                    softReset();
                } catch (Exception e) {
                    Logger.getLogger().log("LISST Socket reset failed: "+e.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                }

            }
            synchronized (mLock) {
                // Has a graceful shutdown been requested?
                if (mShutdown) {
                    // Yes, exit the thread
                    break;
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

    public void startCollection() throws TimeoutException {
        clockSync();
        mSampleStartTime = System.currentTimeMillis(); // set the time before incurring overhead
        mLisstData.setDataCollection(true);
        dataCollection();
        //Mark whether this is a zero file - for now assume it is if the pump is off
        if (mLisstData.getSeawaterPump()==false) {
            mLisstData.setZeroFile(true);
        } else {
            mLisstData.setZeroFile(false);
        }
    }
    public void stopCollection() throws TimeoutException {
        mLisstData.setDataCollection(false);
        dataCollection();
    }

    /**
     * Turn on and off the seawater pump based on the value set in the data structure
     */
    public void seawaterPump() throws TimeoutException {
        try {
            mLisstBusy = true;
            mPumpStartTime = System.currentTimeMillis();    // one before overhead to avoid race in run routine
            getPrompt();
            while (mReader.ready()) {
                mReader.read(); // flush mReader
            }
            if (mLisstData.getSeawaterPump() == true) {
                mWriter.print("~R 11\n");
                mPumpStartTime = System.currentTimeMillis();    // reset here to correct time
            } else {
                mWriter.print("~R 10\n");
            }
            mWriter.flush();

        } catch(Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            disconnect();   // mark us as disconnected
            throw new TimeoutException("Instrument not responding.");
        } finally {
            mLisstBusy = false;
        }
    }

    /**
     * Turn on and off the clean water based on the value set in the data structure
     */
    public void cleanWaterFlush() throws TimeoutException {
        int c=0;
        try {
            mLisstBusy = true;
            mFlushStartTime = System.currentTimeMillis(); // before the overhead to avoid a race in run routine
            getPrompt();
            while (mReader.ready()) {
                c=mReader.read(); // flush mReader
                if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
            }
            if (mLisstData.getCleanWaterFlush() == true) {
                if (mDebugThis == true) { System.out.println("Sending: ~R 21\n"); }
                mWriter.print("~R 21\n");
                mFlushStartTime = System.currentTimeMillis();   // once more to correct the time
            } else {
                if (mDebugThis == true) { System.out.println("Sending: ~R 20\n"); }
                mWriter.print("~R 20\n");
            }
            mWriter.flush();
            if (mDebugThis == true) {
                System.out.println(readLine(READ_TIMEOUT));
                System.out.println(readLine(READ_TIMEOUT));
            }

        } catch(Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            disconnect();   // mark us as disconnected
            throw new TimeoutException("Instrument not responding.");
        } finally {
            mLisstBusy = false;
        }
    }

    /**
     * Turn on and off data collection based on the value set in the data structure
     * If turning on, get filename
     */
    public void dataCollection() throws TimeoutException {
        String sr = "";
        String[] tokens;
        int c=0;
        try {
            mLisstBusy = true;
            getPrompt();
            while (mReader.ready()) {
                c=mReader.read(); // flush mReader
                if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
            }
            if (mLisstData.getDataCollection() == true) {
//                // check the data file in case it failed before...(hopefully not)
//                if (mLisstData.getDataFileTransferred() == false &&
//                        mLisstData.getDataFileName()!=null) {
//                    Logger.getLogger().log("Data file has not been transferred.  Trying again.",
//                            this.getClass().getName(), LogLevel.WARN);
//                    for (int count=0; count < 3; count++) {
//                        if (getFile(mLisstData.getDataFileName()) == true) { break; }
//                        Thread.sleep(10000*count+1);    // wait longer and longer for another try
//                    }
//                }

                if (mDebugThis == true) { System.out.println("Sending: ~a 2\n"); }
                mWriter.print("~a 2\n");
                mWriter.flush();

                Thread.sleep(1000);     // allow time for the procedure to start
                
                do {
                    sr = readLine(READ_TIMEOUT);
                    if (mDebugThis == true) { System.out.println(sr); }
                } while (sr.contains("File") == false);
                tokens = sr.split("[ \t]+");
                mLisstData.setDataFileName(tokens[6]);
                mLisstData.setDataFileTransferred(false);
                mSampleStartTime = System.currentTimeMillis(); // reset the begin time

            } else {
                mWriter.print("\003");
                mWriter.flush();

//                // transfer the file if necessary
//                if (mLisstData.getDataFileTransferred() == false &&
//                        mLisstData.getDataFileName()!=null) {
//                    for (int count=0; count < 3; count++) {
//                        if (getFile(mLisstData.getDataFileName()) == true) {
//                            notifyListeners(mLisstData);  // we now have data
//                            break;
//                        }
//                        Thread.sleep(10000*count+1);    // wait longer and longer for another try
//                    }
//                }
            }

        } catch(TimeoutException e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            disconnect();   // mark us as disconnected
            throw new TimeoutException("Instrument not responding.");
        } catch(Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
        } finally {
            mLisstBusy = false;
        }
    }

    /**
     * Poll the lisst for its current status.
     */
    public void getStatus() throws TimeoutException {
        String sr = "";     // status reply
        String[] tokens;
        for (int count=3; count > 0; count--) { // willing to try three times, although first one should work
            try {
                mLisstBusy = true;
                getPrompt();
                while (mReader.ready()) {
                    mReader.read(); // flush mReader
                }
                mWriter.print("DS\n");
                mWriter.flush();

                mLisstData.setStatusTimeStamp(System.currentTimeMillis());

                do {
                    sr = readLine(READ_TIMEOUT);
                    if (mDebugThis == true) { System.out.println(sr); }
                } while (sr.contains("Serial") == false);
                tokens = sr.split("[ \t]+");
                mLisstData.setSerialNumber(tokens[4]);

                do {
                    sr = readLine(READ_TIMEOUT);
                    if (mDebugThis == true) { System.out.println(sr); }
                } while (sr.contains("Firmware") == false);
                mLisstData.setFirmwareVersion(sr.substring(19));

                do {
                    sr = readLine(READ_TIMEOUT);
                    if (mDebugThis == true) { System.out.println(sr); }
                } while (sr.contains("Measurements") == false);
                tokens = sr.split("[ \t%]+");
                mLisstData.setMeasPerAvg(Integer.valueOf(tokens[4]));

                do {
                    sr = readLine(READ_TIMEOUT);
                    if (mDebugThis == true) { System.out.println(sr); }
                } while (sr.contains("Tank") == false);
                tokens = sr.split("[ \t%]+");
                mLisstData.setCleanWaterLevel(Integer.valueOf(tokens[5]));

            } catch(Exception e) {
                if (count == 1) {   // out of tries
                    Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                    disconnect();   // mark us as disconnected
                    throw new TimeoutException("Instrument not responding.");
                }
                continue;       // keep trying
            } finally {
                mLisstBusy = false;
            }
            break;          // success
        }
    }

    /**
     * Synchronize the clock with the cpu clock
     */
    public void clockSync() throws TimeoutException {
        Date today;
        String formattedDate;
        SimpleDateFormat formatter;

        formatter = new SimpleDateFormat("MM/dd/yy HH:mm:ss");
        today = new Date();
        formattedDate = formatter.format(today);

        try {
            mLisstBusy = true;
            getPrompt();
            while (mReader.ready()) {
                mReader.read(); // flush mReader
            }
            String cmd = "SC " + formattedDate + "\n";
            mWriter.print(cmd);
            mWriter.flush();
            if (mDebugThis == true) {
                System.out.println(readLine(READ_TIMEOUT));
                System.out.println(readLine(READ_TIMEOUT));
                System.out.println(readLine(READ_TIMEOUT));
            }

        } catch(Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            disconnect();   // mark us as disconnected
            throw new TimeoutException("Instrument not responding.");
        } finally {
            mLisstBusy = false;
        }
    }


    /**
     * Connect to the instrument and look for a prompt.
     * Upon return the instrument will be ready to accept a command.
     */
    private void getPrompt() throws TimeoutException {
        String s = "";
        int c=0;
        String p = "\n";  // if already in command mode, try a lf
        // try three times or until we get the prompt
        for (int i=3; i>0 && c!='>'; i--) {
            mWriter.print(p);
            mWriter.flush();
            try {
                // Here we are expecting a prompt that contains '>' with no cr
                // Need to read until timeout or until find '>'
                long lcTime = System.currentTimeMillis();
                while (System.currentTimeMillis() - lcTime < READ_TIMEOUT) {
                    while (mReader.ready()) {
                        c = mReader.read();
                        if (mDebugThis == true) { System.out.print( (char) c); }
                        lcTime = System.currentTimeMillis();
                        if (c=='>') { break; }
                    }
                    if (c=='>') { break; }
                    Thread.sleep(10);
                }
                if (c!='>') { p = "\003"; }    // this time try a ctrl-c to get into command mode
            } catch(Exception e) {
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            }
        }
        if (c != '>') {
            Logger.getLogger().log("Couldn't get LISST prompt.", this.getClass().getName(), LogLevel.ERROR);
            throw new TimeoutException("LISST not responding - Are we rebooting?");
        }
        try {
            Thread.sleep(100);  // There is another prompt that may come.  Wait for it.
        } catch (Exception e) {
            e.printStackTrace();
        }
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
    private String readLine(long timeout) throws IOException, TimeoutException {
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
                } catch (InterruptedException e) {  }
            }
        } while (!done && (System.currentTimeMillis() < (issueTime + timeout)));

        if (!done) {
            throw new TimeoutException("Timed out waiting for crlf");
        } else {
            return retval;
        }
    }

    public boolean getFile(String lisst_file) throws TimeoutException {
        String sr = "";
        int c=0;
        boolean success = false;
        boolean wasbusy = false;

        Logger.getLogger().log("Transferring lisst data file.", this.getClass().getName(), LogLevel.DEBUG);
        try {
            if (mLisstBusy == true) {
                wasbusy = true;
            } else {
                mLisstBusy = true;
            }

            // first command sets the download baud rate
            getPrompt();
            while (mReader.ready()) {
                c = mReader.read(); // flush mReader
                if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
            }
            if (mDebugThis == true) { System.out.println("Sending: BR 9600\n"); }
            mWriter.print("BR 9600\n");
            mWriter.flush();
            Thread.sleep(100);  // give the system time to deal with this command

            getPrompt();
            while (mReader.ready()) {
                c = mReader.read(); // flush mReader
                if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
            }
            if (mDebugThis == true) { System.out.println("Sending: YS "+lisst_file+"\n"); }
            mWriter.print("YS "+lisst_file+"\n");
            mWriter.flush();

            do {
                sr = readLine(READ_TIMEOUT);
                if (mDebugThis == true) { System.out.println(sr); }
            } while (sr.contains("Sending") == false);

            // Start up a receiver class to get the file
            YModem ym = new YModem(mSocket.getInputStream(), mSocket.getOutputStream(), new PrintWriter(System.out));
            try {
                ym.receive(mLisstFileFolder+"/"+lisst_file);
                success = true; // if we got here
            } catch (Exception e) {
                success = false;
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            }

            // it doesn't seem to say anything after a send.  This may time out
            if (mDebugThis == true) {
                try {
                    System.out.println(readLine(READ_TIMEOUT * 10));
                } catch(TimeoutException e) { /* don't worry about it here */ }
            }

        } catch(TimeoutException e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            disconnect();   // mark us as disconnected
            throw new TimeoutException("Instrument not responding.");
        } catch(Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
        } finally {
            if (wasbusy == false) {
                mLisstBusy = false;
            }
        }
        
        // if successful
        if (mLisstData.getDataFileName()!=null && mLisstData.getDataFileTransferred()==false) { // only log data once
            notifyListeners(mLisstData);    // now we can log to the db, etc
            deleteFile(lisst_file);         // remove the file from the lisst (still on local system at this point)
        }
        mLisstData.setDataFileTransferred(success);
        if (success) {
            Logger.getLogger().log("Lisst file transfer successful.", this.getClass().getName(), LogLevel.DEBUG);
        }
        return success;    // to indicate success
    }

    public void deleteFile(String lisst_file) throws TimeoutException {
        int c=0;
        try {
            mLisstBusy = true;
            getPrompt();
            while (mReader.ready()) {
                c = mReader.read(); // flush mReader
                if (mDebugThis == true) { System.out.print(String.valueOf( (char) c)); }
            }
            if (mDebugThis == true) { System.out.println("Sending: DL "+lisst_file+"\n"); }
            mWriter.print("DL "+lisst_file+"\n");
            mWriter.flush();

            // Here we are expecting a prompt that contains ']' with no cr
            // Need to read until timeout or until find ']'
            long lcTime = System.currentTimeMillis();
            while (System.currentTimeMillis() - lcTime < READ_TIMEOUT) {
                while (mReader.ready()) {
                    c = mReader.read();
                    if (mDebugThis == true) { System.out.print( (char)c ); }
                    lcTime = System.currentTimeMillis();
                    if (c==']') { break; }
                }
                if (c==']') { break; }
                Thread.sleep(10);
            }
            Thread.sleep(100);  // give it a little time
            mWriter.print("Y\n"); // acknowledge the yes/no challenge
            mWriter.flush();
            
            if (mDebugThis == true) {
                System.out.println(readLine(READ_TIMEOUT*10));
                System.out.println(readLine(READ_TIMEOUT*10));
            }

        } catch(TimeoutException e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            disconnect();   // mark us as disconnected
            throw new TimeoutException("Instrument not responding.");
        } catch(Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
        } finally {
            mLisstBusy = false;
        }
    }
}

