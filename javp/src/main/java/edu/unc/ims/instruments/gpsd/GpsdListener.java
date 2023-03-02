
package edu.unc.ims.instruments.gpsd;

/**
 * Interface for classes to receive messages from gpsd.
 * @author Tony Whipple
 */
public interface GpsdListener {
    /**
    Called when a measurement has been read.
    @param  m   The data.
    */
    void onMeasurement(GpsData m);
}
