package edu.unc.ims.avp;

import org.json.JSONObject;
import org.json.JSONArray;
import org.json.JSONException;

/**
 * IoClient implements a broker client object to interact with the mIo broker.
 */
public class IoClient implements BrokerClientListener {

    BrokerClient mIo;
    private int mID;
    JSONObject mResponse;
    private static final int TIMEOUT = 2000;

//    /**
//     * example main routine
//     * 
//     * @param args
//     * @throws Exception 
//     */
//    public static void main(String args[]) throws Exception {
//        IoClient a = new IoClient("avp3.dyndns.org", 8880);
//        for(;;) {
//            a.turnOn('pin_a_7');
//            System.out.println(a.isOn('pin_a_7'));
//            Thread.sleep(2000);
//            a.turnOff('pin_a_7');
//            System.out.println(a.isOn('pin_a_7'));
//            Thread.sleep(2000);
//        }
//       // a.shutdown();
//    }

    
    /**
     * Constructor sets up communication via BrokerClient adds this as a listener
     * and starts the BrokerClient run thread.
     * 
     * @param host
     * @param port
     * @throws Exception 
     */
    public IoClient(final String host, final int port) throws Exception {
        mIo = new BrokerClient(host, port);
        
        Thread t;
        t = new Thread(mIo, "io-client");
        
        mIo.addListener(this);
        
        t.start();  // This is the broker client run thread.
        mID = (int)(Math.random() * 9999);  // pick a random number
    }

    /**
     *
     * @return
     */
    @Override
    public boolean isActive() {
        return !mIo.shouldShutdown();
    }

    
    public void shutdown() {
        if(mIo != null) {
            mIo.shutdown();
        }
    }

    
    /**
     * acquire the io control token from the broker
     * 
     * @return  boolean success/fail
     * @throws Exception 
     */
    protected synchronized boolean acquire() throws Exception {
        return sendRequest("tokenAcquire");
    }

    /**
     * release the io control token back to the broker
     * 
     * @return  boolean success/fail
     * @throws Exception 
     */
    protected synchronized boolean release() throws Exception {
        return sendRequest("tokenRelease");
    }

    /**
     * Send a JSONRequest and wait for the response
     * 
     * @param name
     * @return boolean success/fail
     * @throws Exception 
     */
    protected synchronized boolean sendRequest(String name) throws Exception {
        BrokerMessage request = new BrokerMessage();
        request.setMethod(name);
        mID = mID + 1;  // increment before sending
        request.setId(mID);
        
        mIo.send(request.toJSONRequest());
        
        try {
            // wait() until someone calls notify() which happens in onData()
            // This means we wait here for a response on the port.
            wait();
        } catch(IllegalMonitorStateException e) {
            e.printStackTrace();
            return false;
        }
        return true;
    }


    /**
     * Turn on a particular pin
     * 
     * @see #switchPin(char, int, boolean) 
     * @param port
     * @param pin
     * @return boolean success/fail
     */
    public boolean turnOn(String port) {
        return switchPin(port, true);
    }

    /**
     * Turn off a particular pin
     * 
     * @see #switchPin(char, int, boolean) 
     * @param port
     * @param pin
     * @return boolean success/fail
     */
    public boolean turnOff(String port) {
        return switchPin(port, false);
    }
    
    /**
     * set the value of an io pin
     * 
     * @param port  values are any valid names
     * @param switchOn  boolean
     * @return boolean success/fail
     */
    public synchronized final boolean switchPin(String port, boolean switchOn) {
        boolean result = false;
        BrokerMessage request = new BrokerMessage();
 
        // get the control token
        try {
            if(!acquire()) {
                return result;
            }
        } catch(Exception e) {
            e.printStackTrace();
            Logger.getLogger().log("Exception trying to acquire control token: " + e.toString(),
                    this.getClass().getName(), Logger.LogLevel.ERROR);
            return result;
        }
        
        int pinValue = switchOn ? 1 : 0;
        try {
            request.setMethod("set");
            mID = mID + 1;  // increment before sending
            request.setId(mID);
            request.addParam(port, pinValue);
            mIo.send(request.toJSONRequest());
        } catch (Exception e) {
            e.printStackTrace();
            Logger.getLogger().log("Exception trying to create JSON Request: " + e.toString(),
                    this.getClass().getName(), Logger.LogLevel.ERROR);
            return result;  // fail
        }

        try {
            wait(TIMEOUT);  // wait for a response
        } catch (InterruptedException ie) {
            Logger.getLogger().log("Interrupted waiting for response from io broker: " + ie.toString(),
                    this.getClass().getName(), Logger.LogLevel.WARN);
            return result;
        }
        
        // If we got here there was some sort of broker message or a timeout
        // Check to see if the mResponse has the correct mID and the result is "ok"
        try {
            if  (mResponse.getInt("id") == mID) {
                if ( mResponse.getJSONObject("result").getJSONObject(port).getString("status").equalsIgnoreCase("ok") )
                result = true;
            }
        } catch (JSONException je) {
            Logger.getLogger().log("Exception trying to get id from JSON Response: " + je.toString(),
                    this.getClass().getName(), Logger.LogLevel.WARN);          
        }
        
        // release the token
        try {
            if(!release()) {
                return result;
            }
        } catch(Exception e) {
            e.printStackTrace();
            Logger.getLogger().log("Exception trying to release control token: " + e.toString(),
                    this.getClass().getName(), Logger.LogLevel.ERROR);
            return result;
        }
        
        return result;
    }


    /**
     * Check the value of a pin
     * 
     * @param port
     * @param pin
     * @return  true if on (set) 
     */
    public synchronized boolean isOn(String port)  {
        BrokerMessage request = new BrokerMessage();
        JSONArray data = new JSONArray();
        boolean retval = false;
        
        request.setMethod("status");
        mID = mID + 1;  // increment before sending
        request.setId(mID);
        data.put(port);
        request.addParam("data", data);
        try {
            mIo.send(request.toJSONRequest());
            Logger.getLogger().log("IoClient sending: " + request.toJSONRequest().toString(),
                    this.getClass().getName(), Logger.LogLevel.DEBUG);            
        } catch (Exception e) {
            e.printStackTrace();
            Logger.getLogger().log("Exception trying to create JSONRequest: " + e.toString(),
                    this.getClass().getName(), Logger.LogLevel.ERROR);
        }
        
        try {
            wait(TIMEOUT);  // wait for a response
        } catch (InterruptedException ie) {
            Logger.getLogger().log("Interrupted waiting for response from io broker: " + ie.toString(),
                    this.getClass().getName(), Logger.LogLevel.WARN);
        }
        
        // here either we have a response or a timeout
        try {
            Logger.getLogger().log("IoClient received: " + mResponse.toString(),
                    this.getClass().getName(), Logger.LogLevel.DEBUG);            
        } catch (Exception e) {
            e.printStackTrace();
            Logger.getLogger().log("Exception trying to create JSONRequest debug log: " + e.toString(),
                    this.getClass().getName(), Logger.LogLevel.ERROR);
        }
        
        try {
            if (mResponse.getInt("id") == mID) {
                if (mResponse.getJSONObject("result").getJSONObject(port).getInt("value") == 1) {
                    retval = true;
                } 
            }
        } catch (JSONException je) {
            Logger.getLogger().log("JSONException trying to get result from io: " + je.toString(),
                    this.getClass().getName(), Logger.LogLevel.ERROR);
        }
        
        return retval;
    }

    
    /**
     * Called from within BrokerClient run thread.  Set response and notify() the 
     * object that we no longer have to wait.
     * 
     * @param d 
     */
    @Override
    public synchronized void onData(JSONObject d) {
        if(d!= null) {
            mResponse = d;
        }
        notify();
    }

}
