package edu.unc.ims.avp;

import org.json.JSONException;
import edu.unc.ims.avp.Logger.LogLevel;
import java.util.HashMap;
import java.util.ArrayList;
import java.util.Iterator;
import edu.unc.ims.avp.adapters.BrokerAdapter;

/**
 * BrokerSubscription implements the runnable thread that pushes subscribed data
 * to the listener.
 * <p>
 * Several parameters determine the timing and style of the data updates.  The minimum
 * interval is the granularity at which data are checked for new values.
 * If max interval passes without a reply being sent, data will be checked.
 * OnNew=t will send a reply every time the data are checked,
 * otherwise replies will be send when data change.  Verbose style includes units.
 * 
 */
public class BrokerSubscription implements Runnable {

    private ArrayList<String> mParameters;
    public ArrayList<String> getParameters() { return mParameters; }
    public boolean hasParameter(String param) { return mParameters.contains(param); }

    private long mMinInterval;
    private long mMaxInterval;
    private boolean mOnNew;
    private boolean mVerbose;
    private BrokerAdapter mAdapter;
    private BrokeredDeviceListener mListener;
    
    private boolean mActive;
    private synchronized void setActive(boolean state) { mActive = state; }
    private synchronized boolean getActive() {
        // A disconnect need not end subscription.  It will happen on suspend
        if (/*!mAdapter.isConnected() ||*/ !mListener.isActive()) {
            mActive = false;
        }
        return mActive;
    }

    /**
     * Constructor initializes object values
     * @param params        list of parameters in this subscription
     * @param minInterval   min interval to push updates
     * @param maxInterval   max interval to push updates
     * @param onNew         boolean push updates on new data regardless of interval
     * @param verbose       boolean verbose update messages
     * @param adapter       to whom this subscription belongs
     * @param listener      to which the data are flowing
     */
    BrokerSubscription( ArrayList<String> params, long minInterval, long maxInterval, boolean onNew,
            boolean verbose, BrokerAdapter adapter, BrokeredDeviceListener listener) {
        mParameters =  params;
        mMinInterval = minInterval;
        mMaxInterval = maxInterval;
        mOnNew =       onNew;
        mVerbose =     verbose;
        mAdapter =     adapter;
        mListener =    listener;
        mActive =      false;
    }


    /**
     * Thread runs until all parameters have been unsubscribed or thread has been
     * otherwise told to stop.
     */
    public void run() {
        String param;
        String params = "";
        long nextIssueTime = 0;
        long lastNotifyTime = 0;
        long maxTime = 0;
        HashMap<String, Object> pm = new HashMap<String, Object>();
        setActive(true);

        Iterator<String> iter = mParameters.iterator();
        while (iter.hasNext()) {
            param = iter.next();
            mAdapter.addSubscription(param, mListener, this);   // put the parameter in the adapter's subscription list
            pm.put(param, null);    // make a hash map for the call to get
            params = params + param;    // generate a comma separated string for the log message
            if(iter.hasNext()) {
                params = params + ", ";
            }
        }
        Logger.getLogger().log("Starting subscription for " + mAdapter.getClass().getName() + ", parameters: "
                    + params + ", minInterval: " + mMinInterval + ", maxInterval: " + mMaxInterval,
                    this.getClass().getName(), LogLevel.DEBUG);

        // until the subscription has ended
        do {
            if (mAdapter.isSuspended() == false) {  // Do nothing if the broker is suspended
                
                if (System.currentTimeMillis() > nextIssueTime) {
                    BrokerMessage reply = new BrokerMessage("subscription", mVerbose);
                    try {
                        mAdapter.get(pm, reply);    // get the data for this parameter
                    } catch(Exception e) {
                        Logger.getLogger().log("Exception during subscription: " + e.getMessage(),
                                this.getClass().getName(), LogLevel.ERROR);
                        e.printStackTrace();
                    }
                    
                    // Issue the response if the subscription hasn't ended and
                    // ( this is the first time or 
                    //   there is something new to reply - changed data or an error or
                    //   mOnNew==ture meaning every time we read the value )
                    // therefore 'on change' happens by default via reply.hasNew() and mOnNew overrides
                    if (getActive() && ((lastNotifyTime == 0) || (reply.hasNew() || mOnNew))) {
                        notifyListener(reply);
                        lastNotifyTime = System.currentTimeMillis();
                        nextIssueTime = lastNotifyTime + mMinInterval;  // set to the min interval
                        maxTime = lastNotifyTime + mMaxInterval;
                    } else {    // it is past next issue time but we did not reply (i.e. no new data)
                        long minTime = System.currentTimeMillis() + mMinInterval;   // add another min interval
                        nextIssueTime = (minTime < maxTime) ? minTime : maxTime;    // unless is is more than maxTime
                    }
                }
            }   // end of if not suspended
            
            try {
                Thread.sleep(50);   // this sets minimum granularity of subscriptions (50ms == 20Hz)
            } catch (InterruptedException ie) { }
            } while (getActive());

        // ending subscription thread
        iter = mParameters.iterator();
        while (iter.hasNext()) {
            param = iter.next();
            Logger.getLogger().log("Ending subscription for " + mAdapter.getClass().getName() + " parameter "
                    + param, this.getClass().getName(), LogLevel.DEBUG);
        }
        Logger.getLogger().log("Ending subscription thread.", this.getClass().getName(), LogLevel.DEBUG);
    }

    
    /**
     * Unsubscribe from a parameter.  If all parameters are unsubscribed this ends
     * the subscription thread.
     * @param param 
     */
    public void unSubscribe(String param) {
        mParameters.remove(param);
        Logger.getLogger().log("Ending subscription for " + mAdapter.getClass().getName() + " parameter "
                + param, this.getClass().getName(), LogLevel.DEBUG);
        if (mParameters.isEmpty()) {
            mActive = false;
        }
    }

    
    /**
     * Send the data to the listener
     * @param reply 
     */
    private void notifyListener(BrokerMessage reply) {
        try {
            mListener.onData(reply.toJSONNotification());
        } catch (JSONException j) {
            Logger.getLogger().log("JSONException in subscription.notifyListener: " + j.getMessage(),
                    this.getClass().getName(), LogLevel.WARN);
        } catch (Exception e) {
            Logger.getLogger().log("Exception in subscription.notifyListener: " + e.getMessage(),
                    this.getClass().getName(), LogLevel.ERROR);
            e.printStackTrace();
        }
    }

}
