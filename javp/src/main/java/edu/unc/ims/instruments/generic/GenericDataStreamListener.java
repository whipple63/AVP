package edu.unc.ims.instruments.generic;

/**
Interface for classes to receive messages from the depth sounder.
Classes are required to implement an onMeasurement method.
*/
public interface GenericDataStreamListener {
    /**
    Called when a measurement has been read.
    @param  m   The data
    */
    void onMeasurement(GenericDataStreamData m);
}
