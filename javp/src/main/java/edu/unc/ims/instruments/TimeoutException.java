package edu.unc.ims.instruments;

/**
Timeout.
A timeout error, see message for details.
*/
public class TimeoutException extends Exception {
    /**
    Constructor.
    */
    public TimeoutException() {
        super();
    }

    /**
    Constructor.
    @param  msg Message
    */
    public TimeoutException(final String msg) {
        super(msg);
    }
}
