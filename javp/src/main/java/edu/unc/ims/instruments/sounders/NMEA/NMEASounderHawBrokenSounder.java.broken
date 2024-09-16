package edu.unc.ims.instruments.sounders.NMEA;

import java.net.Socket;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;
import java.net.UnknownHostException;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;
import edu.unc.ims.instruments.sounders.*;

/**
<p>
NMEA Depth Sounder Instrument code
</p><p>
This code was tested with a generic NMEA sounder issuing SDDBT, SDDPT and YXMTW strings for
depth and temperature.
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
        NMEASounder s = new NMEASounder("office.dyndns.org", 55231);
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
public final class NMEASounder extends SounderInstrument implements Runnable {

    enum NEMAType { SDDPT, SDDBT, YXMTW, INVALID };     // NEMA message type.
    enum DeviceState {DS_UNKNOWN, DS_OPERATING };
    private final String mLock = "lock";
    private DeviceState mDeviceState = DeviceState.DS_UNKNOWN;
    private boolean mShutdown = false;  // Flag to indicate that a shutdown has been requested (via finalize).
    private String mHost;
    private int mPort;
    private Socket mSocket;
    private BufferedReader mReader;
    private Thread mReaderThread;
    private long mLastCharTime = 0;
    private static long SOCKET_TEST_TIMEOUT = 3000;

    /**
    Initialize host and port which came from the broker config file.
    @param  host    Hostname
    @param  port    Port number
    @see #connect
     */
    public NMEASounder(final String host, final int port) {
        mHost = host;
        mPort = port;
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
        mReader = new BufferedReader(new InputStreamReader(mSocket.getInputStream()));
        mReaderThread = new Thread(this, this.getClass().getName());
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
            Logger.getLogger().log("Set mShutdown to true", this.getClass().getName(), LogLevel.DEBUG);
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
        if (System.currentTimeMillis() > mLastCharTime+SOCKET_TEST_TIMEOUT) {
            try {
                mLastCharTime = System.currentTimeMillis(); // first in case next line throws exception
                mSocket.getOutputStream().write('\n');
            } catch (IOException e) {
                try {
                    // Assume that the write failed because of a broken socket
                    Logger.getLogger().log("Sounder Socket not connected.  Attempting to reconnect.",
                            this.getClass().getName(), LogLevel.ERROR);
                    mSocket.close();
                    setState(S_DISCONNECTED);
                } catch (IOException ee) { /* so the close failed, move on */ }
                try {
                    mSocket = new Socket(mHost, mPort);
                    mReader = new BufferedReader(new InputStreamReader(mSocket.getInputStream()));
                } catch (Exception eee) {
                    Logger.getLogger().log("Sounder Socket reconnect failed: "+eee.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                }
            }
        }
    }



    /**
     * Start sampling does nothing with this instrument.
     * It is always sampling.
     * 
     * @return success
     */
    @Override
    public boolean startSampling() { return true; }
    
    /**
     * Stop sampling does nothing with this instrument.
     * It is always sampling.
     * 
     * @return success
     */
    @Override
    public boolean stopSampling() { return true; }

    
    /**
    Attempt a soft reset of the device.  Since the sounder accepts no commands, there
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
        // reset the shutdown flag
        synchronized (mLock) {
            mShutdown = false;
        }
        /*
        Try to devine the current device state and reflect it internally.
        Pull out relevant data if operational and trigger listeners.
         */
        int localState = 0;
        double localDepthM = 0;
        double localDepthf = 0;
        double localDepthF = 0;
        double localTempC = 0;
        for (;;) {
            //checkSocket();

            String l = "";
            try {
                if (mReader.ready()) {
                    // we should have data ready to read
                    l = mReader.readLine();
                    mLastCharTime = System.currentTimeMillis();
                    if (l == null) {
                        Logger.getLogger().log("Reader read a null", this.getClass().getName(), LogLevel.INFO);
                        continue;
                    }
                } else {
                    /*
                    No data ready to read, sleep a bit and see if we need
                    to gracefully shutdown.
                     */
                    try {
                        Thread.sleep(50);
                    } catch (InterruptedException e) {
                        Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                    }
                    synchronized (mLock) {
                        // Has a graceful shutdown been requested?
                        if (mShutdown) {
                            // Yes, exit the thread
                            break;
                        }
                    }
                }
            } catch (IOException e) {
                Logger.getLogger().log(e.toString(),
                        this.getClass().getName(), LogLevel.ERROR);
            }
            // Figure out the state.
            String[] fields = l.split(",");
            if (l.equals("")) {
                // We can safely ignore blank lines
                continue;
            }
            /* try block to catch arrayindexoutofbounds exception */
            try {
                String messageString = fields[0];
//                if (messageString.contains("$SDDPT")) {
                if (messageString.contains("DPT")) {
                    if (!fields[1].equals("")) {
                        try {
                            localDepthM = Double.parseDouble(fields[1]);
                        } catch (NumberFormatException nfe) {
                            continue;
                        }
                    } else {
                        localDepthM = Double.NaN;
                    }
                    localState = 1;
//                } else if ((localState == 1) && (messageString.contains("$SDDBT"))) {
                } else if ((localState == 1) && (messageString.contains("DBT"))) {
                    if (!fields[1].equals("")) {
                        try {
                            localDepthf = Double.parseDouble(fields[1]);
                        } catch (NumberFormatException nfe) {
                            continue;
                        }
                    } else {
                        localDepthf = Double.NaN;
                    }
                    if (!fields[3].equals("")) {
                        try {
                            localDepthF = Double.parseDouble(fields[3]);
                        } catch (NumberFormatException nfe) {
                            continue;
                        }
                    } else {
                        localDepthF = Double.NaN;
                    }
//                    localState = 2;
//                } else if ((localState == 2) && (messageString.equals(
//                        "$YXMTW"))) {
//                    if (!fields[1].equals("")) {
//                        try {
//                            localTempC = Double.parseDouble(fields[1]);
//                        } catch (NumberFormatException nfe) {
//                            continue;
//                        }
//                    } else {
                        localTempC = Double.NaN;
//                    }
                    localState = 0;
//        if (mCollecting == true) {
                    try {
                        notifyListeners(new SounderData(localDepthM,
                                localDepthf, localDepthF, localTempC));
                    } catch (Exception e) {
                        Logger.getLogger().log(e.toString(),
                                this.getClass().getName(), LogLevel.ERROR);
                    }
//        }
                    setDeviceState(DeviceState.DS_OPERATING);
                } else {
                    setDeviceState(DeviceState.DS_UNKNOWN);
                }
            } catch (Exception f) {
                Logger.getLogger().log("Exception: " + f.toString() +
                        "Received from device: " + l,
                        this.getClass().getName(), LogLevel.ERROR);
            } /* primarily catching arrayindexoutofbounds exceptions... */
        } // for(;;)
        // We're gracefully exiting, try to close the socket on the way out
        try {
            Logger.getLogger().log("Closing socket", this.getClass().getName(), LogLevel.DEBUG);
            mSocket.close();
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(),
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }

}
