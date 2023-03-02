package edu.unc.ims.instruments.wind;

/**
Interface for classes to receive messages from the Young 32500.
*/
public interface WindListener {
    /**
    Called when a measurement has been read.
    @param  m   The data.
    */
    void onMeasurement(WindData m);
}
