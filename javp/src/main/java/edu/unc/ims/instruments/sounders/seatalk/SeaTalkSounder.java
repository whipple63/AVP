package edu.unc.ims.instruments.sounders.seatalk;

import java.net.Socket;
import java.io.DataInputStream;
import java.io.BufferedInputStream;
import java.io.IOException;
import java.net.UnknownHostException;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.*;
import edu.unc.ims.instruments.sounders.*;

/**
<p>
SeaTalk Depth Sounder Instrument code
</p><p>
This code was tested with a Raymarine ST40 sounder.  Reads only the depth data packet.
Temperature is not being transmitted by this device.
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
public final class SeaTalkSounder extends SounderInstrument implements Runnable {

    private DeviceState mDeviceState = DeviceState.DS_UNKNOWN;
    private boolean mShutdown = false;      // shutdown requested flag
    private String mHost;                   // hostname
    private int mPort;                      // port number
    private Socket mSocket;
    private DataInputStream mDataStream;
    private Thread mReaderThread;
    private long mLastCharTime = 0;
    private static long SOCKET_TEST_TIMEOUT = 3000;
    private static long PACKET_INTERVAL = 100;
    enum DeviceState { DS_UNKNOWN, DS_OPERATING  };
    private final String mLock = "lock";

    
    /**
    Initialize host and port which came from the broker config file.
    @param  host    Hostname
    @param  port    Port number
    @see #connect
     */
    public SeaTalkSounder(final String host, final int port) {
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
        mDataStream = new DataInputStream(new BufferedInputStream(mSocket.getInputStream()));
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
                    mDataStream = new DataInputStream(new BufferedInputStream(mSocket.getInputStream()));
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
        /* 
            Notes from working txbasic code 
            
            Data are in binary, in bursts.  If there is a 0.1s delay that should
            be the end of a burst.
            
            Sea-Talk Data Format (in hexadecimal notation):
                            00  02  IJ  XX YY
                                  Depth below transducer: (XX + 256* YY)/10 feet
                                  Display units: I=0 => feet, I=4 => meter
                                  Flags: J&1 Shallow Depth Alarm   (J=1)
                                  J&4 Transducer defective (J=4) (i.e. bad pings)
         */

        // reset the shutdown flag
        synchronized (mLock) {
            mShutdown = false;
        }
        
        /*
        Try to devine the current device state and reflect it internally.
        Pull out relevant data if operational and trigger listeners.
         */
        int packetType;
        int dataLength; // useful if more messages are supported
        int flags;
        double localDepthM;
        double localDepthf;
        double localDepthF;
        double localTempC;
        mLastCharTime = System.currentTimeMillis();
        for (;;) {
            checkSocket();

            try {
                if (mDataStream.available() > 0) {
                    if (System.currentTimeMillis() > mLastCharTime+PACKET_INTERVAL) {
                        mLastCharTime = System.currentTimeMillis();
                        
                        localDepthM = 0;
                        localDepthf = 0;
                        localDepthF = 0;
                        localTempC = Double.NaN;

                        //Read the packet
                        packetType = mDataStream.readUnsignedByte();
                        //System.out.format("packetType: %d ", packetType);
                        dataLength = mDataStream.readUnsignedByte();    // there will be dataLength+1 more bytes
                        //System.out.format("dataLength: %d ", dataLength);
                        switch (packetType) {
                            case 0:     // depth
                                // it looks like we are operating - good data or not
                                setDeviceState(DeviceState.DS_OPERATING);           
                                
                                flags = mDataStream.readUnsignedByte();
                                System.out.print("flags: " + Integer.toBinaryString(flags));
                                // From experimenting, it looks like if either bit 2 or 3 is set
                                // it's a bad ping.
                                if ( (flags & 0x0C) != 0) { // bad ping
                                    mDataStream.skipBytes(2);
                                } else {
                                    // I *think* that the readings are always in feet even
                                    // if the display is in meters or fathoms.
                                    localDepthf = mDataStream.readUnsignedByte();
                                    localDepthf += mDataStream.readUnsignedByte() << 8;
                                    localDepthf = localDepthf / 1000.0 * 3.280839895013123; // appears to be in meters
//                                    localDepthf /= 10.0;
                                    System.out.format(" depthf: %.2f%n", localDepthf);
                                    localDepthM = localDepthf * 0.3048;
                                    localDepthF = localDepthf * 0.1666666666666667;
                                }
                                break;
                            default:    // could be out of sync
                                // skip bytes until there is a delay in the stream
                                while (mDataStream.available() > 0) {
                                    mLastCharTime = System.currentTimeMillis();
                                    mDataStream.skipBytes(mDataStream.available());
                                    try {
                                        Thread.sleep(10);
                                    } catch (InterruptedException e) {
                                        Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                                    }
                                }
                                break;
                        }
                        if (localDepthf != 0) { // we got data
                            try {
                                notifyListeners(new SounderData(localDepthM, localDepthf, localDepthF, localTempC));
                            } catch (Exception e) {
                                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                            }
                        }
                    }
                } else {
                    // No data ready to read, sleep a bit and see if we need to gracefully shutdown.
                    try {
                        Thread.sleep(10);
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
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            }
            
        } // for(;;)
        
        // We're gracefully exiting, try to close the socket on the way out
        try {
            mSocket.close();
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
        }
    }

    
}

