package edu.unc.ims.instruments.IO.piplate;

import com.nahuellofeudo.piplates.relayplate.RELAYPlate;
import com.nahuellofeudo.piplates.daqcplate.DAQCPlate;
import com.nahuellofeudo.piplates.InvalidParameterException;
import com.nahuellofeudo.piplates.InvalidAddressException;
import edu.unc.ims.avp.Broker;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.instruments.IO.*;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;


/**
 *
 * @author Tony
 */
public class PiPlateStack extends IOInstrument {
    private final Broker mBroker;
    String mHost;   // host and port for future instruments
    int mPort;
    IOData mIOD;
    
    RELAYPlate [] mRelayPlate;     // the relay plate(s)
    DAQCPlate [] mDaqcPlate;
    
    public PiPlateStack(String host, int port, Broker b) {
        mHost = host;   // host and port for future io instruments
        mPort = port;
        mBroker = b;
    }
   
    @Override
    public void connect() throws InvalidAddressException, UnsupportedStateException, UnknownStateException {
        if (mState != S_DISCONNECTED) {
            throw new UnsupportedStateException("Already connected");
        }

        String adapterName = mBroker.getAdapterName();

        // PiPlate board addresses will always start at 0 and increment
        
        // Relays come in multiples of 7 on pi-plate relay boards, the new relay plate2 has 8
		// will assume 8 and most significant bit may or may not be useful
        int nRelays = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_relays"));
        int nb = (int) Math.ceil(nRelays/8.0);
        mRelayPlate = new RELAYPlate[nb];
        for (int i=0; i<nb; i++) { mRelayPlate[i] = new RELAYPlate(i); }
        
        // DOuts come in multiples of 7 on pi-plate daqc boards
        int nDOut = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_dout"));
        nb = (int) Math.ceil(nDOut/7.0);
        mDaqcPlate = new DAQCPlate[nb];
        for (int i=0; i<nb; i++) { mDaqcPlate[i] = new DAQCPlate(i); }

        // get the rest of the arguments from config
        int nDIn = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_din"));
        int nAIn = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_ain"));
        int nPWM = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_pwm"));
        int nAOut = Integer.parseInt(mBroker.getProperties().getProperty(adapterName + "_aout"));
        mIOD = new IOData(nRelays, nDOut, nDIn, nAIn, nPWM, nAOut);        
        
        try {
            initInstrument();    // inits instrument and tries to wait for data to start flowing
            initData();          // init the data class
            setState(S_CONNECTED);
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(), this.getClass().getName(), Logger.LogLevel.ERROR);
            setState(S_DISCONNECTED);
            try {
                disconnect();
            } catch (Exception ee) {
            }
            throw new UnknownStateException();
        }

    }
    
    private void initInstrument() throws UnknownStateException {
        // check that all the boards reply
        for (int i=0; i<mRelayPlate.length; i++) {
            if (mRelayPlate[i].getAddr() < 0) {
                throw new UnknownStateException("PiPlate Stack can't find relay board at address"+i);
            }
        }
        for (int i=0; i<mDaqcPlate.length; i++) {
            if (mDaqcPlate[i].getAddr() < 0) {
                throw new UnknownStateException("PiPlate Stack can't find daqc board at address "+i);
            }
        }               
    }
    
    @Override
    public void disconnect() {
        // nothing to disconnect
        setState(S_DISCONNECTED);
    }

    @Override
    public void reset() throws Exception {
        // does nothing
    }

    // could use these to start/stop interrupt driven digital inputs
    @Override
    public boolean startSampling() {    // return success/fail
        return true;
    }
    
    @Override
    public boolean stopSampling() {     // return success/fail
        return true;
    }
    
    /**
     * setRelay sets a relay to on (non-zero) or off (0)
     * Also maintains the internal copy of the data and notifies
     * listeners of any change.
     * 
     * NOTE: relay library code numbers relays from 1 to 7, but I am keeping consistent
     * numbering with the digital outputs as 0 to 6.  Therefore, I add 1 to the call
     * before sending it off to the library.
     * 
     * @param p
     * @param v
     * @throws InvalidParameterException 
     */
    @Override
    public void setRelay(int p, int v) throws InvalidParameterException {
        int board = (int) Math.floor(p/7.0);   // which board
        int pin = p%7 + 1;  // which pin on this board
        if (v!=0) v=1;  // v can only be zero or one
        if (mIOD.getRelay(p)!=v) {  // if the value needs changing
            mRelayPlate[board].relayToggle(pin);
            mIOD.setRelay(p, v);    // update the data
            notifyListeners(mIOD);  // let listeners know that data has changed
        }
    }
    
    @Override
    public void setDOut(int p, int v) throws InvalidParameterException {
        int board = (int) Math.floor(p/7.0);   // which board
        int pin = p%7;  // which pin on this board
        if (v!=0) v=1;  // v can only be zero or one
        if (mIOD.getDOut(p)!=v) {  // if the value needs changing
            mDaqcPlate[board].toggleDOUTbit(pin);
            mIOD.setDOut(p, v);    // update the data
            notifyListeners(mIOD);  // let listeners know that data has changed
        }
    }
    
    @Override
    public void setPWM(int p, int v) throws InvalidParameterException {
        int board = (int) Math.floor(p/2.0);   // which board
        int pin = p%2;  // which pin on this board
        if (v<0) v=0;   // v cannot be negative
        if (v>=1024) v=1023;  // v can only go to 1024
        if (mIOD.getPWM(p)!=v) {  // if the value needs changing
            mDaqcPlate[board].setPWM(pin, v);
            mIOD.setPWM(p, v);    // update the data
            notifyListeners(mIOD);  // let listeners know that data has changed
        }
    }
    
    @Override
    public void setAOut(int p, double v) throws InvalidParameterException {
        int board = (int) Math.floor(p/2.0);   // which board
        int pin = p%2;  // which pin on this board
        if (v<0.0) v=0.0;   // v cannot be negative
        if (v>4.095) v=4.095;  // v can only go to 4.095 volts
        if (mIOD.getAOut(p)!=v) {  // if the value needs changing
            mDaqcPlate[board].setDAC(pin, v);
            mIOD.setAOut(p, v);    // update the data
            notifyListeners(mIOD);  // let listeners know that data has changed
        }
    }
    
    @Override
    public void setAllRelays(int v) throws InvalidParameterException {
        if (mIOD.getAllRelays() != v) {  // if the value needs changing
            for (int i=0; i<mRelayPlate.length; i++) {
                int d = (v>>(7*i))&0x7F;    // 1st 7 bits for board 0, 2nd 7 for board 1, etc.
                mRelayPlate[i].relayAll(d);
            }
            mIOD.setAllRelays(v);    // update the data
            notifyListeners(mIOD);  // let listeners know that data has changed
        }
    }
    
    @Override
    public void setAllDOut(int v) {
        if (mIOD.getAllDOut()!=v) {  // if the value needs changing
            for (int i=0; i<mDaqcPlate.length; i++) {
                int d = (v>>(7*i)); // take 1st 7 bits for board 0, 2nd 7 for board 1, etc.
                d = (~d)&0x7F;    // invert d (daqc plate is reverse logic) and mask off the bits we want
                mDaqcPlate[i].setDOUTall(d);
            }
            mIOD.setAllDOut(v);    // update the data
            notifyListeners(mIOD);  // let listeners know that data has changed
        }
    }

    @Override public long getIOTimeStamp() { return mIOD.getTimeStamp(); }
    @Override public int getRelay(int p) { return mIOD.getRelay(p); }
    @Override public int getDOut(int p) { return mIOD.getDOut(p); }
    @Override public int getDIn(int p) throws InvalidParameterException { updateDin(); return mIOD.getDIn(p); }
    @Override public int getPWM(int p) { return mIOD.getPWM(p); }
    @Override public double getAOut(int p) { return mIOD.getAOut(p); }
    
    @Override public double getAIn(int p) throws InvalidParameterException {
        int board = (int) Math.floor(p/8.0);   // which board
        int pin = p%8;  // which pin on this board
        double tmp=mDaqcPlate[board].getADC(pin);
        //System.out.println("   adc("+p+"): "+tmp);
        mIOD.setAIn(p, tmp);
        return mIOD.getAIn(p);
    }
    
    private void initData() throws InvalidParameterException {
        int rv; // a value
        int dv; // a value
        int mask;
        for (int i=0; i<mRelayPlate.length; i++) {
            rv = mRelayPlate[i].relayState();
            for (int j=0; j<7; j++) {
                mask = 1<<j;
                mIOD.setRelay(i*7+j, (rv&mask)!=0?1:0 ); // set to 0 or 1
            }
        }
        for (int i=0; i<mDaqcPlate.length; i++) {
            dv = ~(mDaqcPlate[i].getDOUTall()) & 0x7F;  // inverted logic for daqcplate
            for (int j=0; j<7; j++) {             
                mask = 1<<j;
                mIOD.setDOut(i*7+j, (dv&mask)!=0?1:0 ); // set to 0 or 1
            }            
            for (int j=0; j<2; j++) {
                mIOD.setPWM(i*2+j, mDaqcPlate[i].getPWM(j) );
                mIOD.setAOut(i*2+j, mDaqcPlate[i].getDAC(j) );
            }
            for (int j=0; j<8; j++) {
                getAIn(i*8+j);
            }
        }        
        updateDin();   // update the input values
        
        // test routine for some other code...
//        try {
//            for (int i=0; i<7; i++) {
//                setRelay(i,1);
//                Thread.sleep(3000);
//                setRelay(i,0);
//                Thread.sleep(1000);
//            }
//            
//            for (int i=0; i<7; i++) {
//                setDOut(i,1);
//                Thread.sleep(3000);
//                setDOut(i,0);
//                Thread.sleep(1000);
//            }
//
//            for (int i=0; i<2; i++) {
//                setPWM(i,512);
//                Thread.sleep(10000);
//                setPWM(i,0);
//                Thread.sleep(5000);
//            }
            
////            for (int i=0; i<2; i++) {
////                setAOut(i,3.0);
////                Thread.sleep(10000);
////                setAOut(i,0);
////                Thread.sleep(5000);
////            }
//
//        } catch (Exception e) { }
//        
    }

    // update all data values
    private void updateDin() throws InvalidParameterException {
        for (int i=0; i<mDaqcPlate.length; i++) {
            int dval=mDaqcPlate[i].getDINAll() & 0xFF;
            for (int j=0; j<8; j++) {
                mIOD.setDIn(i*8+j, (dval&(1<<j)) > 0 ? 1:0 );
//                try { Thread.sleep(10); } catch (Exception e) {}
            }
        }
    }
    
}
    
    

