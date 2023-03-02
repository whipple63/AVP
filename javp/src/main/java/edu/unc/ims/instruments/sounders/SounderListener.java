package edu.unc.ims.instruments.sounders;

/**
Interface for classes to receive messages from the depth sounder.
Classes are required to implement an onMeasurement method.
*/
public interface SounderListener {
    /**
    Called when a measurement has been read.
    @param  m   The data
    */
    void onMeasurement(SounderData m);
}
