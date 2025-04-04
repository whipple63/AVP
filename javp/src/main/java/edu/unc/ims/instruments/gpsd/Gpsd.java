/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

package edu.unc.ims.instruments.gpsd;

import java.net.*;
import java.io.*;
import java.util.List;
import java.util.Vector;
import java.util.Iterator;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;


/**
 * Communicates with the gpsd daemon
 * @author Tony Whipple
 */
public class Gpsd implements Runnable,GpsdListener {

    /** Socket attached to the gpsd port */
    private Socket mSocket;

    /** host on which gpsd is running */
    private String mHost;

    /** internet address associated with gpsd host */
    private InetAddress mInetAddress;

    /* port to use to connect to gpsd */
    private int mPort;

    /** buffered reader for gpsd data */
    private BufferedReader mBR;

    /** buffered writer for gpsd data */
    private BufferedWriter mBW;

    /** List of Listeners. */
    private List<GpsdListener> mListeners = new Vector<GpsdListener>();

    /** Runnable thread in gpsd */
    private Thread mGpsdThread;

    /** set to false to end the run() thread */
    private boolean mKeepRunning = true;

    /** The most recent gps data */
    private GpsData mGpsData;
    private long mDataTime;
    private long mDataDelayMax = 300000; // max time is ms between obs from gpsd


    /**
     * main routine for testing only
     * @param args the command line arguments (are ignored)
     */
    public static void main(String[] args) throws UnknownHostException, InterruptedException, IOException  {
        Gpsd myGPS = new Gpsd("avp3.dyndns.org", 2947);

        System.out.println("Tony's gpsd monitor");
        myGPS.connectGpsdSocket();
        myGPS.startSampling();
        myGPS.addListener(myGPS);
        Thread.sleep(600000);
        myGPS.stopSampling();
        myGPS.disconnectGpsdSocket();
    }

    public void run() {
        while (mKeepRunning == true) {
            if (mSocket.isConnected()) {
                this.readGPS();
                try {
                    Thread.sleep(100);
                } catch (InterruptedException e) {
                    System.out.println(e.getMessage());
                    mKeepRunning = false;
                }
            } else {
                try {
                    Logger.getLogger().log("GPSD Socket is disconnected.  Attempting reset. ",
                            this.getClass().getName(), LogLevel.ERROR);
                    softReset();
                } catch (Exception e) {
                    Logger.getLogger().log("GPSD Socket reset failed: "+e.getMessage(),
                            this.getClass().getName(), LogLevel.ERROR);
                    System.out.println(e.getMessage());
                }
            }
        }
    }
    
    /**
     * Constructor
     * @param host name of host running gpsd
     * @param port port number to connect to gpsd
     * @throws UnknownHostException
     */
    public Gpsd(String host, int port) throws UnknownHostException {
        mHost = host;
        mPort = port;

        mSocket = null;
        mInetAddress = InetAddress.getByName(mHost);
        mBR = null;
        mGpsData = new GpsData();   // create a storage spot for the data
        mDataTime = System.currentTimeMillis();
    }

    /**
     * Connect socket to the host and port
     */
    public void connectGpsdSocket() {
          if (mSocket == null) {
            try {
                mSocket = new Socket( mInetAddress, mPort);
                mBR = new BufferedReader( new InputStreamReader( mSocket.getInputStream()) );
                mBW = new BufferedWriter( new OutputStreamWriter( mSocket.getOutputStream() ) );
            } catch(Exception e ) {
                System.out.println(e.getMessage());
                e.printStackTrace(System.out);
                System.exit(-1);
            }
            // start the thread that will gather the data and pass it along
            mKeepRunning = true;
            mGpsdThread = new Thread(this, this.getClass().getName());
            mGpsdThread.start();
          }
        }

    /**
     * Disconnect socket
     */
    public void disconnectGpsdSocket() throws InterruptedException {
        mKeepRunning = false;   // stop the run thread
        mGpsdThread.join(300);     // wait until run actually finishes
                                   // NOTE for some reason this just times out, but works

        mBW = null;     // drop the buffered writer
        mBR = null;     // drop the buffered reader
        try { mSocket.close(); } catch (IOException ee) { /* so the close failed, move on */ }
        mSocket = null; // destroy the socket
        }

    
    public boolean startSampling() {
        try {
            mBW.write( "?WATCH={\"enable\":true,\"json\":true}\n" );
            mBW.flush();
        } catch (IOException e) {
            Logger.getLogger().log("IOException writing to gpsd: "+e.getMessage(),
                    this.getClass().getName(), LogLevel.ERROR);            
        }
        return true;
    }

    public boolean stopSampling() {
        try {
            mBW.write( "?WATCH={\"enable\":false}\n" );
            mBW.flush();
        } catch (IOException e) {
            Logger.getLogger().log("IOException writing to gpsd: "+e.getMessage(),
                    this.getClass().getName(), LogLevel.ERROR);            
        }
        return true;
    }

    /**
    Let the device attempt to reset to a known state.
    @throws Exception   on error
    */
    public void softReset() throws Exception {
        stopSampling();
        disconnectGpsdSocket();
        connectGpsdSocket();
        startSampling();
    }

    protected void readGPS() {
        if (mBR == null) return;

        try {
            if (System.currentTimeMillis() > mDataTime+mDataDelayMax) {
                mDataTime = System.currentTimeMillis(); // reset the timer
                Logger.getLogger().log("Data delay exceeded.  Attempting reset. ", this.getClass().getName(), LogLevel.WARN);                
                softReset();    //try resetting
            }
            while (mBR.ready()) {
                mGpsData.update(mBR.readLine());
                mDataTime = System.currentTimeMillis();
//                System.out.println(mGpsData.get());     // Debugging print statement
                notifyListeners(mGpsData);
            }
        } catch (Exception e) {
              System.out.println(e.getMessage());
            }
        }

    /**
    Send data to listeners.
    @param  data    data to send.
    */
    private void notifyListeners(GpsData data) {
        Iterator <GpsdListener>i = mListeners.iterator();
        while(i.hasNext()) {
            GpsdListener l = i.next();
            l.onMeasurement(data);
        }
    }

    /**
    * Who to notify when measurements are available
    * @param  l   The listener
    */
    public void addListener(final GpsdListener l) {
        mListeners.add(l);
    }

    public void onMeasurement(GpsData d) {
        System.out.println("readGPS: " + d.get());
    }
}
