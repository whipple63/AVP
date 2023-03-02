package edu.unc.ims.instruments;

/**
Unsupported state.
*/
public class UnsupportedStateException extends Exception {
    /**
    Constructor.
    */
    public UnsupportedStateException() {
        super();
    }

    /**
    Constructor.
    @param  msg Message
    */
    public UnsupportedStateException(final String msg) {
        super(msg);
    }
}
