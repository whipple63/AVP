package edu.unc.ims.instruments.ysi_exo;

/**
Interface for classes to receive messages from the YSI Sonde 6.
*/
public interface EXO2Listener {
    /**
    Called when a measurement has been read.
    @param  m   The data.
    */
    void onMeasurement(EXO2Data m);
}
