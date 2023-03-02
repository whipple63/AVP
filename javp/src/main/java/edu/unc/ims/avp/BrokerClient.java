package edu.unc.ims.avp;

import java.net.Socket;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import edu.unc.ims.avp.Logger.LogLevel;
import java.util.List;
import java.util.Queue;
import java.util.LinkedList;
import java.util.ArrayList;
import java.util.Iterator;
import org.json.JSONObject;

/**
 * BrokerClient allows code to connect to a broker port, issue requests, and
 * listen for responses and notifications.
*/
public class BrokerClient extends ShutdownThread {

    private Socket mSocket;
    private String mHost;
    private int mPort;

    private final List<BrokerClientListener> mListeners = new ArrayList<BrokerClientListener>();
    private final Queue<JSONObject> mOutQueue = new LinkedList<JSONObject>();

    private BufferedReader mReader;
    private PrintWriter mWriter;


    /**
     * Constructor.  Set up the socket and its reader and writer.
     * 
     * @param  host    host
     * @param  port    port
     * @throws Exception   On error
     */
    public BrokerClient(final String host, final int port) throws Exception {
        mHost = host;
        mPort = port;
        mSocket = new Socket(mHost, mPort);
        mReader = new BufferedReader(new InputStreamReader(mSocket.getInputStream()));
        mWriter = new PrintWriter(mSocket.getOutputStream());
    }
    
    
    /**
     * Add a listener.
     * @param  l   listener.
     */
    public final void addListener(final BrokerClientListener l) {
        synchronized (mListeners) {
            mListeners.add(l);
        }
    }

    
    /**
     * Add a JSONObject to the queue to be sent.
     * 
     * @param o 
     */
    public void send(JSONObject o) {
        synchronized(mOutQueue) {
            mOutQueue.add(o);
        }
    }

    
    /**
     * Run sends anything that appears in the output queue, and accepts input and
     * passes it along to any interested listeners.
     */
    @Override
    public final void run() {
        while(!shouldShutdown()) {
            try {
                
                // anything to send?
                synchronized(mOutQueue) {
                    JSONObject o;
                    while((o = mOutQueue.poll())!= null) {
                        o.write(mWriter);
                        mWriter.flush();
                    }
                }
                
                if (mReader.ready()) {
                    // we should have data ready to read
                    String line = mReader.readLine();

                    JSONObject ja = new JSONObject(line);
                    sendToListeners(ja);
                    
                } else {
                    /*
                    No data ready to read, sleep a bit and see if we need
                    to gracefully shutdown.
                    */
                    try {
                        Thread.sleep(100);
                    } catch (InterruptedException e) {
                        Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                    }
                    
                    if (shouldShutdown()) {
                        mSocket.close();
                        break;
                    }
                }
            } catch (Exception e) {
                e.printStackTrace();
                String msg = e.getMessage();
                BrokerError err = new BrokerError(BrokerError.E_EXCEPTION, msg);
                try {
                    sendToListeners(err.toJSONObject());
                } catch (Exception f) {
                    f.printStackTrace(); // we really should never arrive here
                }
            }
        }
//        Logger.getLogger().log("Shutdown", this.getClass().getName(), LogLevel.DEBUG);
    }

    
    /**
     * Send what was read from the port to all listeners.
     * @param  d   The data
     */
    public final void sendToListeners(final JSONObject d) {
        synchronized (mListeners) {
            Iterator<BrokerClientListener> i = mListeners.iterator();
            while (i.hasNext()) {
                BrokerClientListener l = i.next();
                l.onData(d);
            }
        }
    }

    
}
