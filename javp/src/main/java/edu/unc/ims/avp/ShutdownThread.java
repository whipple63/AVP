package edu.unc.ims.avp;

/**
Convenience base class for a thread with graceful shutdown utility.
*/
public abstract class ShutdownThread implements Runnable {
    /**
    Gracefully shut down.
    */
    public final synchronized void shutdown() {
        synchronized (mLock) {
            mShutdown = true;
        }
    }

    /**
    Has user requested a shutdown?
    @return true if user has requested a shutdown.
    */
    protected final synchronized boolean shouldShutdown() {
        synchronized (mLock) {
            if (mShutdown) {
                return true;
            }
        }
        return false;
    }

    /**
    Internal mutex.
    */
    private String mLock = new String("lock");

    /**
    Shutdown flag.
    */
    private boolean mShutdown = false;
}
