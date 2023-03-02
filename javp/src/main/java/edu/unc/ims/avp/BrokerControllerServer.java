package edu.unc.ims.avp;

import java.net.ServerSocket;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.io.PrintWriter;
import java.io.InputStreamReader;
import edu.unc.ims.avp.Logger.LogLevel;
import org.json.JSONObject;
import org.json.JSONTokener;

/**
 Server for broker clients.
 Waits for connection from a control client for a broker. Upon connection,
 creates and runs a ControllerClientHandler thread. Continues to wait for ad-
 ditional connections.
*/
public class BrokerControllerServer extends ShutdownThread {
    /**
    Socket.
    */
    private ServerSocket mSocket;

    /**
    Broker.
    */
    private Broker mBroker;

    /**
    Constructor.
    @param  broker  Broker.
    @throws Exception   On error
    */
    public BrokerControllerServer(final Broker broker) throws Exception {
        mBroker = broker;
        String port = broker.getProperties().getProperty(mBroker.getAdapterName()
                + "_ctrl_port", "8888");
        Logger.getLogger().log("Starting BrokerControllerServer for "
                + mBroker.getAdapterName()
                + " on port " + port + "."
                , this.getClass().getName(), LogLevel.INFO);
        mSocket = new ServerSocket(Integer.parseInt(
            broker.getProperties().getProperty(mBroker.getAdapterName()
                + "_ctrl_port", "8888")));
    }

    /**
    Run.
    */
    public final void run() {
        for (;;) {
            // We allow multiple listeners
            // wait for a connection, check shutdown flag frequently
            for (;;) {
                try {
                    mSocket.setSoTimeout(100);
                    Socket c = mSocket.accept();
                    Logger.getLogger().log("Accepted connection from "
                        + c.toString(), c.toString(), Logger.LogLevel.DEBUG);
                    ControllerClientHandler h = new ControllerClientHandler(mBroker, c);
                    Thread ccht = new Thread(h, this.getClass().getName()+"-ControllerClientHandler-"+c.toString());
                    ccht.start();
                    Logger.getLogger().log("Thread started",
                        this.getClass().getName(), Logger.LogLevel.DEBUG);
                    if (shouldShutdown()) {
                        break;
                    }
                } catch (Exception e) {
                    if (shouldShutdown()) {
                            break;
                    }
                    if (e instanceof SocketTimeoutException) {
                        continue;
                    }
                    e.printStackTrace();
                }
            }
            try {
                mSocket.close();
            } catch (Exception e) {
                break;
            }
            if (shouldShutdown()) {
                break;
            }
        }
        Logger.getLogger().log("Shutdown", this.getClass().getName(),
            Logger.LogLevel.INFO);
    }
}
