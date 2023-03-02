package edu.unc.ims.instruments.wind;

import java.util.Iterator;
import java.util.List;
import java.util.Vector;

/**
 * Abstract class SounderInstrument defines the required classes for a depth
 * sounder and implements the list of listeners.
 * 
 * @author Tony
 */
public abstract class WindInstrument {
    
    private List<WindListener> mListeners = new Vector<WindListener>();   // List of Listeners.
    
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
    
    public List<Double> OUTPUT_RATES;     // possible output rates must be defined in real class
    public abstract void setOutputRate(double rate) throws Exception;
    public abstract double getOutputRateAsDouble();
    
    /**
    Add a class to the list of listeners.  Classes must implement sounderListener,
    thereby having an onMeasurement method.
    
    @param  l   The listener
     */
    public void addListener(final WindListener l) {
        mListeners.add(l);
    }

    
    /**
    Calls each of the onMeasurement methods in the list of listeners.
    
    @param  data    SounderData to send.
     */
    protected void notifyListeners(WindData data) {
        Iterator<WindListener> i = mListeners.iterator();
        while (i.hasNext()) {
            WindListener l = i.next();
            l.onMeasurement(data);
        }
    }
    
}
