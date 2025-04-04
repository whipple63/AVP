package edu.unc.ims.instruments.wind.NMEA;

import java.net.Socket;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.IOException;
import java.net.UnknownHostException;
import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;
import edu.unc.ims.instruments.wind.*;
import java.io.PrintWriter;
import java.net.ServerSocket;
import java.net.SocketTimeoutException;
import java.util.Arrays;

/**
<p>
NMEA Wind Instrument code
</p><p>
This code was tested with Airmar 200wx and based on the NMEA sounder code.
</p><p>
Upon receiving data, it is passed along to the onMeasurement() method of any registered class.
You must call connect() before calling any other methods.  Also, you must
call disconnect() in order to clear up resources (signals the run thread to exit),
otherwise your application may hang.
</p><p>
This minimalist example connects, receives measurements for 20 seconds,
then disconnects.
<pre>
public class Test implements WindListener {
    public Test() throws Exception {
        Airmar200ws s = new Airmar200wx("officeavp.dyndns.org", 55231);
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
public final class Airmar200wx extends WindInstrument implements Runnable {

    // GPS data are available but will be handled by GPSD and the GPS broker
    enum NEMAType { HCHDG, WIMDA, INVALID };     // NEMA message type.
    enum DeviceState {DS_UNKNOWN, DS_OPERATING };
    private final String mLock = "lock";
    private DeviceState mDeviceState = DeviceState.DS_UNKNOWN;
    private boolean mShutdown = false;  // Flag to indicate that a shutdown has been requested (via finalize).
    private String mHost;
    private int mPort;
    private Socket mSocket;
    private BufferedReader mReader;
    private PrintWriter mWriter;
    private Thread mReaderThread;
    private long mLastCharTime = System.currentTimeMillis();    // init to current time
    private static long SOCKET_TEST_TIMEOUT = 10000;
    private ServerSocket mGPSSocket;
    private Broker mBroker;
    private int MAX_SENTENCES_WITHOUT_WIND = 100;

    /**
    Initialize host and port which came from the broker config file.
    @param  host    Hostname
    @param  port    Port number
    @see #connect
     */
    public Airmar200wx(final String host, final int port, final Broker broker) {
        mHost = host;
        mPort = port;
        mBroker = broker;
        // Output rates with this instrument are variable to the tenth of a second
        // and programmable for each NMEA string.  For now, I will leave the default
        // rates, so this list does nothing.
        OUTPUT_RATES = Arrays.asList(0.1, 2.0, 15.0);     // possible output rates
    }

    /**
    Connect starts the whole mechanism working.
    Connects to instrument port, create I/O streams, and starts the run thread.
    
    @throws UnknownHostException    Unknown host or bad IP
    @throws IOException             IO error
    @throws UnknownStateException   If state cannot be determined, a power cycle is probably required.
    @throws UnsupportedStateException   Check message for details.
     */
    @Override
    public void connect() throws UnknownStateException, UnknownHostException, IOException, UnsupportedStateException {
        if (mState != S_DISCONNECTED) {
            throw new UnsupportedStateException("Already connected");
        }
        mSocket = new Socket(mHost, mPort);
        mReader = new BufferedReader(new InputStreamReader(mSocket.getInputStream()));
        mWriter = new PrintWriter(mSocket.getOutputStream());        

        mGPSSocket = new ServerSocket(Integer.parseInt(mBroker.getProperties().getProperty(mBroker.getAdapterName()
            + "_gps_port", "55240")));

        mReaderThread = new Thread(this, this.getClass().getName());
        mReaderThread.start();
        try {
            setState(S_CONNECTED);
            initInstrument();    // inits instrument and tries to wait for data to start flowing
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
    @Override
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
                Logger.getLogger().log("Socket timeout.  Testing by writing a CR.",
                    this.getClass().getName(), LogLevel.WARN);
                mSocket.getOutputStream().write('\n');
            } catch (IOException e) {
                try {
                    // Assume that the write failed because of a broken socket
                    Logger.getLogger().log("Wind Socket not connected.  Attempting to reconnect.",
                            this.getClass().getName(), LogLevel.ERROR);
                    mSocket.close();
                    //setState(S_DISCONNECTED);
                } catch (IOException ee) { /* so the close failed, move on */ }
                try {
                    mSocket = new Socket(mHost, mPort);
                    mReader = new BufferedReader(new InputStreamReader(mSocket.getInputStream()));
                } catch (Exception eee) {
                    Logger.getLogger().log("Wind Socket reconnect failed: "+eee.getMessage(),
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
    Set output rate.
    Set the the rate at which data will be transmitted from the device when
    collecting data.
    * 
    * For now, with the airmar this does nothing.

    @param  rate   Rate value
    @throws TimeoutException Timeout, try again.
    @throws UnsupportedStateException Try a reset() first.
    @throws UnknownStateException Corrupt state, power cycle.
    */
    @Override
    public void setOutputRate(final double rate) throws TimeoutException,
        UnknownStateException, UnsupportedStateException {
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }
        // Do whatever the airmar needs to set the output rate.
        // The code below is from the young wind instrument
//        String cmd = "A";
//        if (rate == OutputRate.RATE_15) {
//            if (mInterfaceType == IfType.CMD_LINE) { cmd = "0"; }
//            else { cmd = "A"; }
//        } else if (rate == OutputRate.RATE_2) {
//            if (mInterfaceType == IfType.CMD_LINE) { cmd = "2"; }
//            else { cmd = "B"; }
//        } else if (rate == OutputRate.RATE_0_1) {
//            if (mInterfaceType == IfType.CMD_LINE) { cmd = "1"; }
//            else { cmd = "C"; }
//        }
//        DeviceState s = getDeviceState();
//        if (s == DeviceState.DS_OPERATING) {
//            pause();
//            if (mInterfaceType == IfType.CMD_LINE) {
//                changeState("CMD220 "+cmd, DeviceState.DS_CMD_LINE, 5);
//                changeState("CMD100", DeviceState.DS_OPERATING, 5);
//            } else {
//                changeState("R", DeviceState.DS_OUTPUT_RATE, 5);
//                changeState(cmd, DeviceState.DS_MENU_MAIN, 5);
//                changeState("X", DeviceState.DS_OPERATING, 5);
//            }
//            mRate = rate;
//        } else if (s == DeviceState.DS_MENU_MAIN) {
//            changeState("R", DeviceState.DS_OUTPUT_RATE, 5);
//            changeState(cmd, DeviceState.DS_MENU_MAIN, 5);
//            mRate = rate;
//        } else if (s == DeviceState.DS_CMD_LINE) {
//            changeState("CMD220 "+cmd, DeviceState.DS_CMD_LINE, 5);
//            mRate = rate;
//        } else {
//            throw new UnsupportedStateException("setOutputRate: Unsupported "
//                + "intial state: " + getDeviceStateLabel(s));
//        }
    }


    @Override
    public double getOutputRateAsDouble() {
        return 2.0;
    }
    
    
    /**
    Attempt a soft reset of the device.  Wait until the run thread marks the 
    device as operating.
    
    @throws TimeoutException
    @throws UnsupportedStateException
     */
    @Override
    public void reset() throws TimeoutException, UnsupportedStateException {
        int timeoutMillis = 10000;
        int resolutionMillis = 100;
        int sleepMillis = 0;
        boolean done = false;
        DeviceState s;
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }
        
        //Do a $PAMTC,RESET here
        String cmd = "$PAMTC,RESET*";
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");  // wind expects CRLF as line terminator
        mWriter.flush();
        initInstrument();
        
        // Set the device state to unknown and wait for it to be operating again
        mDeviceState = DeviceState.DS_UNKNOWN;        
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
    Attempt a initialize the instrument.  Wait until the run thread marks the 
    device as operating.
    
    @throws TimeoutException
    @throws UnsupportedStateException
     */
    public void initInstrument() throws TimeoutException, UnsupportedStateException {
        int timeoutMillis = 10000;
        int resolutionMillis = 100;
        int sleepMillis = 0;
        boolean done = false;
        DeviceState s;
        
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException("You must call connect()");
        }

        // Set the device state to unknown and wait for it to be operating again
        // On first power up this may fail until we configure the device.  Rather 
        // than just sleep, check if we are operating and if so, go right ahead.
        mDeviceState = DeviceState.DS_UNKNOWN;        
        do {
            s = getDeviceState();
            if (s == DeviceState.DS_OPERATING) {
                break;
            }
            try {
                Thread.sleep(resolutionMillis);
                sleepMillis += resolutionMillis;
            } catch (InterruptedException e) {
            }
        } while (sleepMillis < timeoutMillis);
        
        sendInitStrings();  // Do the actual init

        // Set the device state to unknown and wait for it to be operating again
        mDeviceState = DeviceState.DS_UNKNOWN;  
        sleepMillis = 0;
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
            throw new TimeoutException("Timeout initializing device.  Not receiving data.");
        }
            
    }
    
    private void sendInitStrings() {
        // Send initialization commands here
        // Sentences to turn off
        String cmd = "$PAMTC,EN,ALL,0,0*";                  // turn off all sentences
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");

        // Sentences to turn on
        cmd = "$PAMTC,EN,HDG,1,5*";          // turn on heading once per second (magnetic)
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");

        cmd = "$PAMTC,EN,MDA,1,5*";                  // wind and weather data twice per second
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");

        cmd = "$PAMTC,EN,MWD,1,5*";                  // Calculated wind on moving vessel
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");

        cmd = "$PAMTC,EN,GGA,1,20*";                 // satellite data every two seconds
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");

        cmd = "$PAMTC,EN,GSA,1,20*";                 // satellite data every two seconds
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");
        
        cmd = "$PAMTC,EN,VTG,1,20*";                 // satellite data every two seconds
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");
        
        cmd = "$PAMTC,EN,ZDA,1,20*";                 // satellite data every two seconds
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");

        cmd = "$PAMTC,EN,RMC,1,20*";                 // satellite data every two seconds
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");
//        System.out.print(".........................Wrote:"+cmd+getCheckSum(cmd)+"\r\n");
        
        cmd = "$PAMTC,OPTION,SET,1,1*";              // use gps COG instead of compass course (if SOG > 3 knots)
        mWriter.print(cmd+getCheckSum(cmd)+"\r\n");

        mWriter.flush();                
        
    }
            
    /*
     * Returns a two character string representing the checksum of the  input.
     */
    private static String getCheckSum(String in) {
        int checksum = 0;
        if (in.startsWith("$")) {   // take off the '$' if it is on
            in = in.substring(1, in.length());
        }

        int end = in.indexOf('*');  // point to the end 
        if (end == -1)
            end = in.length();
        
        for (int i = 0; i < end; i++) {
            checksum = checksum ^ in.charAt(i);
        }
        String hex = Integer.toHexString(checksum);
        if (hex.length() == 1)
            hex = "0" + hex;
        return hex.toUpperCase();
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
        
        // to send data to a GPS 
        Socket c = null;
        PrintWriter GPSout = new PrintWriter(System.out); // initializing to satisfy compiler
        
        /*
        Try to devine the current device state and reflect it internally.
        Pull out relevant data if operational and trigger listeners.
         */
        int localState = 0;     // bit field as we collect necessary sentences
        int sentencesWithoutWind = 0;       // if this gets too high, try resetting the instrument
        String[] dataStrings = new String[3];   // place to store each relevant data sentence
        for (;;) {
            checkSocket();
            
            String l = "";
            try {
                if (c==null) {
                    try {
                    // check for a connection to the GPS socket
                    mGPSSocket.setSoTimeout(100);

                    c = mGPSSocket.accept();
                    Logger.getLogger().log("Accepted connection from " + c.toString(), c.toString(), Logger.LogLevel.DEBUG);
                    GPSout = new PrintWriter(c.getOutputStream(), true);
                    } catch (Exception e) {
                        if (e instanceof SocketTimeoutException) {
                            // move out of this try block
                        }
                    }
                } else {
                    if (c.isClosed()) {
                        c = null;
                    }
                }

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
            } catch (Exception e) {
                if (e instanceof SocketTimeoutException) {
                    continue;
                }
                if (e instanceof IOException) {
                    Logger.getLogger().log(e.toString(),this.getClass().getName(), LogLevel.ERROR);
                }
            }
            // Figure out the state.
            if (l.equals("")) {
                // We can safely ignore blank lines
                continue;
            }
  //          System.out.println(l);
            String[] fields = l.split(",");
            /* try block to catch arrayindexoutofbounds exception */
            try {
                String messageString = fields[0];
                if (messageString.contains("$HCHDG")) {
                    dataStrings[0] = l;
                    localState = localState | 0x01;     // indicate that we have an HCHDG sentence
                } else if (messageString.contains("$WIMWD")) {
                    dataStrings[1] = l;
                    localState = localState | 0x02;     // indicate that we have an WIMWD sentence                            
                } else if (messageString.contains("$WIMDA")) {
                    dataStrings[2] = l;
                    localState = localState | 0x04;     // indicate that we have an WIMDA sentence                            
                } else {
                    if (c!=null) {
                        GPSout.print(l+"\r\n");
                        if (GPSout.checkError()==true) {
                            Logger.getLogger().log("GPS data socket has closed.", c.toString(), Logger.LogLevel.DEBUG);
                            c = null;   // indicate that the socket has closed
                        }
                    }
                }
                sentencesWithoutWind++;     // increment
                if (sentencesWithoutWind >= MAX_SENTENCES_WITHOUT_WIND) {
                    Logger.getLogger().log("MAX_SENTENCES_WITHOUT_WIND was exceeded.  Resetting device.",
                            this.getClass().getName(), LogLevel.WARN);
                    sendInitStrings();    // re-initialize the instrument (just send the commands)
                    sentencesWithoutWind = 0;   // reset
                    setDeviceState(DeviceState.DS_UNKNOWN);
                }
                if ( (localState & (0x01 | 0x02 | 0x04)) == (0x01 | 0x02 | 0x04) ) {
                    sentencesWithoutWind = 0;   // reset
                    localState = 0;
                    try {
                        notifyListeners(new WindData(dataStrings));
                    } catch (Exception e) {
                        Logger.getLogger().log(e.toString(),this.getClass().getName(), LogLevel.ERROR);
                        e.printStackTrace();
                    }
                    setDeviceState(DeviceState.DS_OPERATING);  // if we have received HDG and MDA
                    
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
            mGPSSocket.close();
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(),this.getClass().getName(), LogLevel.ERROR);
        }
    }

}
