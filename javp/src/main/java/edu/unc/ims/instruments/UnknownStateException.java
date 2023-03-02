package edu.unc.ims.instruments;

/**
Unknown state.
*/
public class UnknownStateException extends Exception {
    /**
    Constructor.
    */
    public UnknownStateException() {
        super();
    }

    /**
    Constructor.
    @param  msg Message
    */
    public UnknownStateException(final String msg) {
        super(msg);
    }
}
