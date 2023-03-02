package edu.unc.ims.instruments.wind;

/**
Invalid input.
See message for details.
*/
public class InvalidInputException extends Exception {
    /**
    Constructor.
    */
    public InvalidInputException() {
        super();
    }

    /**
    Constructor.
    @param  msg Message
    */
    public InvalidInputException(final String msg) {
        super(msg);
    }
}
