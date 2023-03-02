package edu.unc.ims.instruments.ysi;

/**
Interface for classes to receive messages from the YSI Sonde 6.
*/
public interface Sonde6Listener {
    /**
    Called when a measurement has been read.
    @param  m   The data.
    */
    void onMeasurement(Sonde6Data m);
}
