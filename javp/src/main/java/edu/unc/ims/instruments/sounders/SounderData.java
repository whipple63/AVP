package edu.unc.ims.instruments.sounders;

/**
Data received from a depth Sounder.
* 
* Note that depth in ft and Fathoms has been removed and will be zero.
*/
public class SounderData { // will probably extend a generic someday

    private double mDepthM;     // Depth in meters.
    private double mDepthf;     // Depth in feet.
    private double mDepthF;     // Depth in Fathoms.
    private double mTempC;      // Temperature in degrees C.

    /**
    New data instance.

    @param  lDepthM     Water depth in meters
    @param  lDepthf     Water depth in feet
    @param  lDepthF     Water depth in Fathoms
    @param  lTempC      Water temperature in C
    */
    public SounderData(final double lDepthM, final double lDepthf, final double lDepthF, final double lTempC) {
        mDepthM = lDepthM;
        mDepthf = lDepthf;
        mDepthF = lDepthF;
        mTempC = lTempC;
    } // SounderData

    /**
    Get depth in meters.
    Depth (in meters).
    @return depth in meters.
    */
    public final double getDepthM() {
        return mDepthM;
    }

    /**
    Get depth in feet.
    Depth (in feet).
    @return depth in feet.
    */
    public final double getDepthf() {
        return mDepthf;
    }

    /**
    Get depth in Fathoms.
    Depth (in Fathoms).
    @return depth in Fathoms.
    */
    public final double getDepthF() {
        return mDepthF;
    }

    /**
    Get temperature in degrees C.
    Temperature (in degrees C).
    @return temperature in degrees C.
    */
    public final double getTempC() {
        return mTempC;
    }

    /**
    Get string representation.
    @return string
    */
    public final String toString() {
        StringBuffer sb = new StringBuffer();
        sb.append("Depth in meters:\t" + mDepthM + "\n");
        sb.append("Depth in feet:\t" + mDepthf + "\n");
        sb.append("Depth in Fathoms:\t" + mDepthF + "\n");
        sb.append("Temperature in degrees C:\t" + mTempC + "\n");
        return sb.toString();
    }
}
