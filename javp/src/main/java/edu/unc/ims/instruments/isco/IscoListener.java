package edu.unc.ims.instruments.isco;

/**
Interface for classes to receive messages.
*/
public interface IscoListener {
    /**
    Called when a measurement has been read.
    @param  m   The data.
    */
    void onMeasurement(IscoData m);
}
