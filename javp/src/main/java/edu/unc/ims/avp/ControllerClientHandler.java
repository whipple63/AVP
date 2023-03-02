package edu.unc.ims.avp;

import java.net.Socket;
import java.net.InetSocketAddress;
import java.io.PrintWriter;
import edu.unc.ims.avp.Logger.LogLevel;
import java.io.InputStreamReader;
import org.json.JSONObject;
import org.json.JSONTokener;
import java.io.BufferedReader;
import java.net.SocketException;
import org.json.JSONException;
import java.net.SocketTimeoutException;

/**
 Client handler.
 Spawned by BrokerControllerServer. Accepts client connection, accepts and
 passes command from the client to the broker, and passes replies from the broker
 to the client.
 */
public class ControllerClientHandler extends ShutdownThread implements BrokeredDeviceListener, Runnable {

    private Socket mSocket;
    private PrintWriter mWriter;
    private BufferedReader mReader;
    private Broker mBroker;
    private String mWho = "?";  // String representing client. Typically the IP address, useful in logging.
    private boolean mActive = false;
    private boolean mToken = false;

    
    /**
    Constructor.
    @param  broker  Broker.
    @param  s   Client socket
    @throws Exception   On error
     */
    public ControllerClientHandler(final Broker broker, final Socket s) throws Exception {
        mSocket = s;
        mBroker = broker;
        mWriter = new PrintWriter(mSocket.getOutputStream());
        mReader = new BufferedReader(new InputStreamReader(mSocket.getInputStream()));
        broker.register(this);
        mWho = ((InetSocketAddress) mSocket.getRemoteSocketAddress()).getAddress().getHostAddress();
        Logger.getLogger().log("Accepted listener: "+mWho, this.getClass().getName(), LogLevel.DEBUG);
    }
    

    /**
    Send JSON replies (data) back to client.
    @param  d   the data.
     */
    public final void onData(final JSONObject d) {
        try {
            String s = d.toString();
            mWriter.println(s);
            mWriter.flush();
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            shutdown();
        }
    }
    
    
    /**
    Is the thread still running?
    @return True if the thread is still running, False if it is not.
    */
    public final boolean isActive() {
        return mActive;
    }

    /**
    Does this ControllerClientHandler currently own the control token?
    @return True if the ControllerClientHandler has the control token, False
     if not.
    */
    public synchronized final boolean hasToken() {
        return mToken;
    }

    /**
    Acquire the control token.
    */
    public synchronized final void acquireToken() {
        mToken = true;
    }

    /**
    Release the control token.
    */
    public synchronized final void releaseToken() {
        mToken = false;
    }

    
    /**
    Run.
     */
    public final void run() {
        // we could read init request from data client here
        mActive = true;
        String b = "";
        BrokerMessage reply = new BrokerMessage();
        JSONObject request = new JSONObject();
        
        try {
            mSocket.setSoTimeout(100);
        } catch (Exception e) {
            shutdown();
        }
        
        while (mSocket.isConnected() && !shouldShutdown()) {
            try {
                mSocket.setSoTimeout(100);  // time in ms a read will block before generating a timeout exception
                mReader.mark(10);           // bookmark the reader stream
                if (mReader.read() == -1) { // if the read fails, we lost the socket
                    Logger.getLogger().log("Client "+mWho+" disconnected. Socket closing.",
                            this.getClass().getName(), LogLevel.DEBUG);
                    shutdown();
                }                
                mReader.reset();            // socket is ok, go back to the bookmark
                mSocket.setSoTimeout(0);    // infinite timeout
                if (mReader.ready()) {
                    mReader.mark(255);      // if next line throws ex. use mark to show input
                    request = new JSONObject(new JSONTokener(mReader)); // read a JSON request
//                    System.out.println(request);
                    
                    if (!request.has("id")) {   // no id is an error
                        reply.addError(BrokerError.E_ID_PARSE);
                        onData(reply.toJSONResponse());
                        
                    } else if (!request.has("method")) {    // no method is an error
                        reply.addError(BrokerError.E_METHOD_PARSE);
                        reply.setId(request.getInt("id"));
                        onData(reply.toJSONResponse());
                        
                    } else {    // pass request along to broker
                        reply.setId(request.getInt("id"));
                        mBroker.processRequest(request, this);
                    }
                }
                
            } catch (JSONException joe) {
                reply.addError(BrokerError.E_PARSE);
                try {
                    mReader.reset();
                    while (mReader.ready()) {
                        b = b + mReader.readLine();
                    }
                    reply.setId(request.getInt("id"));
                    onData(reply.toJSONResponse());
                } catch (Exception e) {     //shouldn't happen
                    Logger.getLogger().log("Got exception sending parse error."
                        + b, this.getClass().getName(), LogLevel.ERROR);
                }
                Logger.getLogger().log("Error parsing JSONObject:" + b + joe.toString(),
                        this.getClass().getName(), LogLevel.ERROR);
                
            } catch (SocketTimeoutException ste) {
                // ignore
                
            } catch (NullPointerException npe) {
                Logger.getLogger().log("Client "+mWho+" disconnected. Socket closing.",
                        this.getClass().getName(), LogLevel.DEBUG);
                shutdown();
                
            } catch (SocketException e) {
                Logger.getLogger().log("SocketException: Client "+mWho+" disconnected. Socket closing.",
                        this.getClass().getName(), LogLevel.DEBUG);
                shutdown();
                
            } catch (Exception e) {
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                e.printStackTrace();
            }
            
            try {
                Thread.sleep(100);
            } catch (Exception e) {
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
            }
            
            if (mWriter.checkError()) {
                Logger.getLogger().log("Closing "+mWho, this.getClass().getName(), LogLevel.DEBUG);
                break;
            }
            
        }
        
        
        // close connection to the controller
        try {
            mSocket.close();
        } catch (Exception e) {
        }
        Logger.getLogger().log("Shutdown", this.getClass().getName(), LogLevel.DEBUG);
        mBroker.unregister(this);
        mActive = false;
    }
}
