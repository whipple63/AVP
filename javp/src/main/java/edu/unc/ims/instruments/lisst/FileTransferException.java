package edu.unc.ims.instruments.lisst;

/** A file transfer error, see message for details. */
public class FileTransferException extends Exception {

    /**
     * Constructor
     */
    public FileTransferException() {
        super();
    }

    /**
     * Constructor.
     * @param msg
     */
    public FileTransferException(final String msg) {
        super(msg);
    }
}
