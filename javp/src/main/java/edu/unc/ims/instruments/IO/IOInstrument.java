package edu.unc.ims.instruments.IO;

import com.nahuellofeudo.piplates.InvalidParameterException;
import java.util.Iterator;
import java.util.List;
import java.util.Vector;

/**
 * Abstract class IO Instrument defines the required classes
 * 
 * @author Tony
 */
public abstract class IOInstrument {
    
    private List<IOListener> mListeners = new Vector<IOListener>();   // List of Listeners.
    
    protected int mState = S_DISCONNECTED;     // internal (broker) state
    protected static final int S_DISCONNECTED = 0;    // Disconnected state.
    protected static final int S_CONNECTED = 1;       // Cconnected state.
    protected void setState(int state) { mState = state; }
    
    public abstract void connect() throws Exception;
    public abstract void disconnect();
    public boolean isConnected() { return (mState == S_CONNECTED); }
    public abstract void reset() throws Exception;
    
    public abstract boolean startSampling();    // return success/fail
    public abstract boolean stopSampling();     // return success/fail
    
    public abstract long getIOTimeStamp();
    public abstract void setAllRelays(int v) throws InvalidParameterException;
    public abstract void setAllDOut(int v);
    public abstract void setRelay(int p, int v) throws InvalidParameterException;
    public abstract void setDOut(int p, int v) throws InvalidParameterException;
    public abstract void setPWM(int p, int v) throws InvalidParameterException;
    public abstract void setAOut(int p, double v) throws InvalidParameterException;
    public abstract int getRelay(int p);
    public abstract int getDOut(int p);
    public abstract int getDIn(int p) throws InvalidParameterException;
    public abstract double getAIn(int p) throws InvalidParameterException;
    public abstract int getPWM(int p);
    public abstract double getAOut(int p);
    
    
    /**
    Add a class to the list of listeners.  Classes must implement Listener,
    thereby having an onMeasurement method.
    
    @param  l   The listener
     */
    public void addListener(final IOListener l) {
        mListeners.add(l);
    }

    
    /**
    Calls each of the onMeasurement methods in the list of listeners.
    
    @param  data    Data to send.
     */
    protected void notifyListeners(IOData data) {
        Iterator<IOListener> i = mListeners.iterator();
        while (i.hasNext()) {
            IOListener l = i.next();
            l.onMeasurement(data);
        }
    }
    
}
