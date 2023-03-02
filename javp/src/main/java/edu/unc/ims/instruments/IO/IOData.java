package edu.unc.ims.instruments.IO;

import java.sql.Timestamp;

/**
 * Keep a copy of all of the IO data as well as the timestamp for when it was collected.
 * For our copy of the digital data, a 1 is a non-zero voltage output and a 0 is a 0V output.
 * @author Tony
 */
public class IOData {    
    private long mTimeStamp;    // if we get one value we get them all
    private final int[] mRelayData;
    private final int[] mDOutData;
    private final int[] mDInData;
    private final double[] mAInData;
    private final int[] mPWMData;
    private final double[] mAOutData;

    // constructor accepts relay and daqc plates for access
    public IOData(int nRelays, int nDOut, int nDIn, int nAIn, int nPWM, int nAOut) {
        mRelayData = new int[nRelays];
        mDOutData  = new int[nDOut];
        mDInData   = new int[nDIn];
        mAInData   = new double[nAIn];
        mPWMData   = new int[nPWM];
        mAOutData  = new double[nAOut];        
    }

    // update the timestamp
    private void ts() { mTimeStamp = System.currentTimeMillis(); }
    
    // Public access methods
    public long getTimeStamp()   { return mTimeStamp;      }
    public int getRelay(int num) { return mRelayData[num]; }
    public int getDIn(int num)   { return mDInData[num];   }
    public int getDOut(int num)  { return mDOutData[num];  }
    public double getAIn(int num)   { return mAInData[num];   }
    public int getPWM(int num)   { return mPWMData[num];   }
    public double getAOut(int num)  { return mAOutData[num];  }

    public int getAllRelays() { 
        int rval = 0;
        for (int i=0; i<mRelayData.length; i++) {
            rval |= (mRelayData[i]!=0?1:0) << i;
        }
        return rval;
    }

    public int getAllDOut() { 
        int rval = 0;
        for (int i=0; i<mDOutData.length; i++) {
            rval |= (mDOutData[i]!=0?1:0) << i;
        }
        return rval;
    }

    
    // These methods are used to update the recorded state of output variables
    public void setRelay(int num, int val)  { ts(); mRelayData[num] = val; }
    public void setDOut(int num, int val)   { ts(); mDOutData[num] = val; }
    public void setDIn(int num, int val)    { ts(); mDInData[num] = val; }
    public void setAIn(int num, double val) { ts(); mAInData[num] = val; }
    public void setPWM(int num, int val)    { ts(); mPWMData[num] = val; };
    public void setAOut(int num, double val){ ts(); mAOutData[num] = val; }
    
    public void setAllRelays(int v) {
        for (int i=0; i<mRelayData.length; i++) {
            mRelayData[i] = (v&(1<<i))>0?1:0;
        }
    }
    
    public void setAllDOut(int v) {
        for (int i=0; i<mDOutData.length; i++) {
            mDOutData[i] = (v&(1<<i))>0?1:0;
        }
    }

    @Override
    public String toString() {
        StringBuilder sb = new StringBuilder(1024);
        
        sb.append("Timestamp: ").append(new Timestamp(mTimeStamp)).append("\n");

        sb.append("Relays").append("\n");
        for(int i=0; i< mRelayData.length; i++) {
            sb.append(i).append(": ").append(mRelayData[i]).append("\n");
        }

        sb.append("Digital Inputs ").append("\n");
        for(int i=0; i< mDInData.length; i++) {
            sb.append(i).append(": ").append(mDInData[i]).append("\n");
        }

        sb.append("Digital Outputs").append("\n");
        for(int i=0; i< mDOutData.length; i++) {
            sb.append(i).append(": ").append(mDOutData[i]).append("\n");
        }

        sb.append("Analog Inputs").append("\n");
        for(int i=0; i< mAInData.length; i++) {
            sb.append(i).append(": ").append(mAInData[i]).append("\n");
        }

        sb.append("PWM Outputs").append("\n");
        for(int i=0; i< mPWMData.length; i++) {
            sb.append(i).append(": ").append(mPWMData[i]).append("\n");
        }
        
        sb.append("Analog Outputs").append("\n");
        for(int i=0; i< mAOutData.length; i++) {
            sb.append(i).append(": ").append(mAOutData).append(" volts\n");
        }

        return sb.toString();
    }    
}
