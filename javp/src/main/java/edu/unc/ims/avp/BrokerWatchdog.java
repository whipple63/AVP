package edu.unc.ims.avp;

import edu.unc.ims.avp.Logger.LogLevel;

/**
 * Maintains connection to instrument by monitoring state.  If Broker.State.CONNECTING then
 * this thread will try to connect every CONNECT_INTERVAL until the state changes.
 */
public class BrokerWatchdog extends  ShutdownThread implements Runnable {

    private final int CONNECT_INTERVAL = 60000;
    Broker mBroker;
    String mLabel;
    public String getLabel() { return mLabel; }

    /**
     * Initialize broker and a readable label
     * 
     * @param b
     * @param label 
     */
    public BrokerWatchdog(Broker b, String label) {
        mBroker = b;
        mLabel = label;
    }

    
    /**
     * Monitor the state and try to connect if necessary.
     */
    public void run() {
        long sleepTime = CONNECT_INTERVAL;
        int sleepInterval = 1000;   // 1 second

        while(!shouldShutdown()) {
            if ( !mBroker.isSuspended() ) {
                if (sleepTime >= CONNECT_INTERVAL) {
                    sleepTime = 0;

                    // monitor the state of the Broker.
                    Broker.State s = mBroker.getState();

                    // if the brokered device becomes disconnected we should try to connect
                    if (s == Broker.State.CONNECTED && mBroker.isDeviceConnected() == false) {
                        mBroker.setState(Broker.State.CONNECTING);
                    }
                    
                    if(s == Broker.State.CONNECTING) {
                        Logger.getLogger().log("Attempting to connect to " + mLabel + "...", this.getClass().getName(),
                            LogLevel.DEBUG);
                        try {
                            mBroker.connect();
                        } catch(Exception e) {
                            // error was logged within connect()
                        }
                    }
                }
            } else {
                sleepTime = CONNECT_INTERVAL;   // force max sleep time
            }
            // sleep for some period
            try {
                Thread.sleep(sleepInterval);
                sleepTime = sleepTime + sleepInterval;
            } catch(Exception e) {
            }
        }
        Logger.getLogger().log("Shutdown", this.getClass().getName(),
                LogLevel.DEBUG);
    }

}
