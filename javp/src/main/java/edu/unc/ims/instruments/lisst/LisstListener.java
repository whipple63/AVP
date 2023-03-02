package edu.unc.ims.instruments.lisst;

/**
Interface for classes to receive messages.
*/
public interface LisstListener {
    /**
    Called when a measurement has been read.
    @param  m   The data.
    */
    void onMeasurement(LisstData m);
}
