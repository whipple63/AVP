package edu.unc.ims.instruments.IO;

/**
Interface for classes to receive messages from the instrument.
*/
public interface IOListener {
    /**
    Called when a measurement has been read.
    @param  m   The data.
    */
    void onMeasurement(IOData m);
}
