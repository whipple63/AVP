package edu.unc.ims.instruments.generic;

import java.net.Socket;
import java.net.SocketTimeoutException;
import java.io.InputStreamReader;
import java.util.Iterator;
import java.util.List;
import java.util.Vector;
import java.io.IOException;
import java.net.UnknownHostException;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.*;
import edu.unc.ims.avp.Broker;
import java.io.PrintWriter;

/**
<p>
Generic Data Stream code
</p><p>
This code listens to a port for data.  If it matches the expected format given in
the config file data will be available using the given names in the config file.
</p><p>
Upon receiving data, it is passed along to the onMeasurement() method of any registered class.
You must call connect() before calling any other methods.  Also, you must
call disconnect() in order to clear up resources (signals the run thread to exit),
otherwise your application may hang.
</p><p>
This minimalist example connects, receives measurements for 20 seconds,
then disconnects.
<pre>
public class Test implements SounderListener {
    public Test() throws Exception {
        SeaTalkSounder s = new SeaTalkSounder("office.dyndns.org", 55231);
        s.addListener(this);        // register to receive data
        s.connect();                // connect
        s.startCollection();        // start collecting data
        Thread.sleep(20000);        // sleep 20 seconds
        s.disconnect();             // MUST always call this!
    }

    public static void main(String [] args) throws Exception {
        new Test();
    }

    public void onMeasurement(SounderData m) {
        System.out.println(m);
        }
}
</pre>
 */
public final class GenericDataStream implements Runnable {

    private List<GenericDataStreamListener> mListeners = new Vector<GenericDataStreamListener>();   // List of Listeners.

    private Broker mBroker = null;
    
    protected int mState = S_DISCONNECTED;     // internal (broker) state
    protected static final int S_DISCONNECTED = 0;    // Disconnected state.
    protected static final int S_CONNECTED = 1;       // Cconnected state.
    protected void setState(int state) { mState = state; }
    public boolean isConnected() { return (mState == S_CONNECTED); }

    private String[] mColNames;   // to hold information about the data structure
    private String[] mColTypes;
    private String[] mColUnits;
    
    private DeviceState mDeviceState = DeviceState.DS_UNKNOWN;
    private boolean mShutdown = false;      // shutdown requested flag
    private String mHost;                   // hostname
    private int mPort;                      // port number
    private Socket mSocket;
    private int mSocketTimeout;            // in ms
    private boolean mSocketTimedOut = false;
    private InputStreamReader mReader;
    private Thread mReaderThread;
    private PrintWriter mWriter;    
    private long mLastCharTime = 0;
    private static long SOCKET_TEST_TIMEOUT = 3000;
    protected GenericDataStreamData mGDSData;
    enum DeviceState { DS_UNKNOWN, DS_OPERATING  };
    private final String mLock = "lock";

    private int mNumReplyLines = 0;
    private String mCommandReply;
    
    private boolean mDebugThis = false;

    /**
    Initialize host and port which came from the broker config file.
    @param  host    Hostname
    @param  port    Port number
    @see #connect
     */
    public GenericDataStream(final String host, final int port) {
        mHost = host;
        mPort = port;
    }

    /**
    Initialize host and port which came from the broker config file.
    @param  host    Hostname
    @param  port    Port number
    @see #connect
     */
    public GenericDataStream(Broker b, final String host, final int port) {
        mBroker = b;
        mHost = host;
        mPort = port;
        mColNames = mBroker.getProperties().getProperty("column_names").split("[ ,\t]+");
        mColTypes = mBroker.getProperties().getProperty("column_types").split("[ ,\t]+");
        mColUnits = mBroker.getProperties().getProperty("column_units").split("[ ,\t]+");
        // config value in minutes
        mSocketTimeout = Integer.valueOf(mBroker.getProperties().getProperty("socket_timeout", "10")) * 60000;
        if (mDebugThis) { System.out.println("Socket Timeout: "+ mSocketTimeout); }
    }

    
    /**
    Add a class to the list of listeners.  Classes must implement xxxListener,
    thereby having an onMeasurement method.
    
    @param  l   The listener
     */
    public void addListener(final GenericDataStreamListener l) {
        mListeners.add(l);
    }

    
    /**
    Calls each of the onMeasurement methods in the list of listeners.
    
    @param  data    Data to send.
     */
    protected void notifyListeners(GenericDataStreamData data) {
        Iterator<GenericDataStreamListener> i = mListeners.iterator();
        while (i.hasNext()) {
            GenericDataStreamListener l = i.next();
            l.onMeasurement(data);
        }
    }
    

    
    
    /**
    Connect starts the whole mechanism working.
    Connects to instrument port, create I/O streams, and starts the run thread.
    
    @throws UnknownHostException    Unknown host or bad IP
    @throws IOException             IO error
    @throws UnknownStateException   If state cannot be determined, a power cycle is probably required.
    @throws UnsupportedStateException   Check message for details.
     */
    public void connect() throws UnknownStateException, UnknownHostException, IOException, UnsupportedStateException {
        if (mState != S_DISCONNECTED) {
            throw new UnsupportedStateException("Already connected");
        }
        mSocket = new Socket(mHost, mPort);
        mReader = new InputStreamReader(mSocket.getInputStream());
        mReaderThread = new Thread(this, this.getClass().getName());
        mWriter = new PrintWriter(mSocket.getOutputStream());                
        
        try {   Thread.sleep(500); // buffered reader needs a sec to get going
            } catch (InterruptedException e) {
            }
        
        mReaderThread.start();
        try {
            setState(S_CONNECTED);
            reset();    // tries to wait for data to start flowing
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            setState(S_DISCONNECTED);
            try {
                disconnect();
            } catch (Exception ee) {
            }
            throw new UnknownStateException();
        }
    }

    /**
    Disconnect signals run thread to shut down.  Run thread will close the socket
    upon exiting.
     */
    public void disconnect() {
        synchronized (mLock) {
            mShutdown = true;
        }
        setState(S_DISCONNECTED);
    }


    /**
     Attempt to maintain the socket.
     <p>
     Some Info:<br>
     Socket.isConnected() really only tells if it *was* connected, not if it is broken.
     keep-alive is both too slow and will disconnect of the other side doesn't respond.
     </p><p>
     The most certain way is to write to the socket and if we get an EOF in return it has broken.
     Since that's not always a good idea with the connected device the implementation
     may be both instrument and context dependent.
     </p><p>
     If the instrument has spoken within a certain amount of time, we will assume the connection is good.
     If not it should be safe to send a character.  Do so.
     */
    private void checkSocket() {
        if ( mBroker.getProperties().getProperty("ok_to_write", "true").equalsIgnoreCase("true") ) {
            if (System.currentTimeMillis() > mLastCharTime+SOCKET_TEST_TIMEOUT) {
                try {
                    mLastCharTime = System.currentTimeMillis(); // first in case next line throws exception
                    mSocket.getOutputStream().write('\n');
                } catch (IOException e) {
                    try {
                        // Assume that the write failed because of a broken socket
                        Logger.getLogger().log("Generic Data Stream Socket not connected.  Attempting to reconnect.",
                                this.getClass().getName(), LogLevel.ERROR);
                        mSocket.close();
                        //setState(S_DISCONNECTED);
                    } catch (IOException ee) { /* so the close failed, move on */ }
                    try {
                        mSocket = new Socket(mHost, mPort);
                        mReader = new InputStreamReader(mSocket.getInputStream());
						mWriter = new PrintWriter(mSocket.getOutputStream());
                    } catch (Exception eee) {
                        Logger.getLogger().log("Generic Data Stream Socket reconnect failed: "+eee.getMessage(),
                                this.getClass().getName(), LogLevel.ERROR);
                    }
                }
            }
        } else { // if we can't write try reconnecting based on a socket timeout
            if (mSocketTimedOut) {
                try {
                    mSocket.close();
                    setState(S_DISCONNECTED);
                } catch (IOException ee) { /* so the close failed, move on */ }
                try {
                    mSocket = new Socket(mHost, mPort);
                    mReader = new InputStreamReader(mSocket.getInputStream());
					mWriter = new PrintWriter(mSocket.getOutputStream());
                } catch (Exception eee) {
                    Logger.getLogger().log("Generic Data Stream Socket reconnect failed: "+eee.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                }
                mSocketTimedOut = false;
            }
        }
    }


    /**
     * Start sampling does nothing with this instrument.
     * It is always sampling.
     * 
     * @return success
     */
    public boolean startSampling() { return true; }
    
    /**
     * Stop sampling does nothing with this instrument.
     * It is always sampling.
     * 
     * @return success
     */
    public boolean stopSampling() { return true; }

    public String sendCommand(String cmd, int numReplyLines) throws Exception  {
        // send command to instrument
        mWriter.print(cmd);
        mWriter.flush();
        
        // run method will gather up numReplyLines and place them in mCommandReply
        synchronized(mLock) { mCommandReply = ""; }    // clear the reply string
        mNumReplyLines = numReplyLines;     // signal the run method to accumulate this many lines
        waitForLines(30);       // wait up to 30 sec for the lines to be read
        return mCommandReply;
    }
                
    /*
    Wait for numReplyLines to go to zero.
    */
    private void waitForLines(final long ttl_secs) throws Exception {
        long totalSlept = 0;
        long sleepTime = 100;
        long maxSleep = ttl_secs * 1000;
        for(;;) {
            Thread.sleep(sleepTime);
            if (mNumReplyLines <= 0) { break; }
            totalSlept += sleepTime;
            if(totalSlept >= maxSleep) { throw new Exception("timeout waiting for lines"); }
            synchronized(mLock) { if (mShutdown == true) { return; } }
        }
    }


    /**
    Attempt a soft reset of the device.  Since a generic data stream accepts no commands, there
    is nothing that can be done apart from waiting until the run thread marks the 
    device as operating.
    
    @throws TimeoutException
    @throws UnsupportedStateException
     */
    public void reset() throws TimeoutException, UnsupportedStateException {
        int timeoutMillis = 10000;
        int resolutionMillis = 100;
        int sleepMillis = 0;
        boolean done = false;
        DeviceState s;
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }
        do {
            s = getDeviceState();
            if (s == DeviceState.DS_OPERATING) {
                done = true;
                break;
            }
            try {
                Thread.sleep(resolutionMillis);
                sleepMillis += resolutionMillis;
            } catch (InterruptedException e) {
            }
        } while (sleepMillis < timeoutMillis);
        if (!done) {
            throw new TimeoutException("Timeout resetting device.  Not receiving data.");
        }
    }

    
    /**
    Get the state of the device.
    @return state.
     */
    private synchronized DeviceState getDeviceState() {
        DeviceState s;
        synchronized (mLock) {
            s = mDeviceState;
        }
        return s;
    }

    
    /**
    Set state.
    @param  s   New state
     */
    private synchronized void setDeviceState(final DeviceState s) {
        synchronized (mLock) {
            if (mDeviceState != s) {
                mDeviceState = s;
            }
        }
    }

    
    /**
     * Run thread is started in connect() and stopped in disconnect().  Reads
     * data from the sounder and notifies registered listeners with each data packet.
     */
    public void run() {
        int c = 0;  // the char read
        
        // reset the shutdown flag
        synchronized (mLock) {
            mShutdown = false;
        }

        // flush buffered reader
        try {
            if (mDebugThis) { System.out.println("Flushing:"); }
            while(mReader.ready()) {    // flush buffer
                c = mReader.read();
                if (mDebugThis) { System.out.print((char)c); }
            }
            while(c != '\n') {     // read until a newline
                c = mReader.read();
            }
            if (mDebugThis) { System.out.println("Done flushing"); }
        } catch(IOException e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
        }
        
        mLastCharTime = System.currentTimeMillis();
        for (;;) {
            checkSocket();

            String l = "";
            try {
                if(mReader.ready()) {
                    // we should have data ready to read
                    
                    // This doesn't work on a buffered reader.  It is probably that readLine
                    // is using a non-blocking read.
                    mSocket.setSoTimeout(mSocketTimeout);
                    //System.out.println("socket timeout: " + mSocket.getSoTimeout());
                    
                    c = mReader.read();
                    while (c != '\n') {
                        l += (char)c;
                        c = mReader.read();
                    }
                    if (mDebugThis == true) { 
                        System.out.println("line read: "+l);
                        System.out.println("  Hex: "+bytArrayToHex(l.getBytes())); 
                    }
                    if (l == null) {
                        Logger.getLogger().log("Reader read a null", this.getClass().getName(), LogLevel.INFO);
                        continue;
                    } else if (l.contains("\000")) {
                        Logger.getLogger().log("Line read contains a null", this.getClass().getName(), LogLevel.INFO);
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
                        Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                    }
                    synchronized(mLock) {
                        // Has a graceful shutdown been requested?
                        if (mShutdown) {
                            // Yes, exit the thread
                            break;
                        }
                    }
                }
            } catch (SocketTimeoutException se) {
                mSocketTimedOut = true;
                Logger.getLogger().log(se.toString(), this.getClass().getName(), LogLevel.WARN);
            } catch(IOException e) {
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            }
            
            if (!mSocketTimedOut) {
                String [] fields = l.split("[ ,\t]+");
                if (l.equals("")) { // We can safely ignore blank lines
                    continue;
                }
                
                if (mNumReplyLines > 0) {   // if we are accumulating lines as a reply to a command
                    //System.out.println("Appending Line: "+l);
                    synchronized(mLock) { mCommandReply += l; }    // append the line
                    mNumReplyLines--;       // decrement the number to accumulate
                    continue;               // and continue
                }
                
                // first data check - are there the same number of fields as names
                if (fields.length == mColNames.length) {
                    setDeviceState(DeviceState.DS_OPERATING);
                } else { 
                    Logger.getLogger().log("Number of data fields doesn't match expected length. Data: " + l,
                            this.getClass().getName(), LogLevel.WARN);
                    continue; 
                }

                // try to create data with the line, a number format exception gets thrown if it doesn't convert
                try {
                    mGDSData = new GenericDataStreamData(mColNames, mColTypes, l.split("[ ,\t]+"));
                } catch (NumberFormatException nfe) {
                    Logger.getLogger().log("Number format exception converting data. Data: " + l,
                            this.getClass().getName(), LogLevel.WARN);
                    continue;
                }

                notifyListeners(mGDSData);
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

  String bytArrayToHex(byte[] a) {
   StringBuilder sb = new StringBuilder();
   for(byte b: a)
      sb.append(String.format("%02x ", b&0xff));
   return sb.toString();
}  
}

