package edu.unc.ims.util;

/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
import java.net.*;
import java.io.*;
import java.util.Formatter;
import java.util.Locale;

/**
 *
 * @author danb
 */
public class SounderSimHandler implements Runnable { // implements Runnable {

    private static final int UPDATE_INTERVAL = 1000;
    private static boolean mRunning;
    private static final int PORT = 5440;
    private static final double DEFAULT_DEPTH = 4.3;
    private static double mDepth;
    private static double mTemp;
    private static Socket mSocket;

    public SounderSimHandler(Socket socket) {
        mSocket = socket;
    }

    public static synchronized void kill() {
        mRunning = false;
    }

    private static synchronized boolean isRunning() {
        return mRunning;
    }

    private static synchronized void startRunning() {
        mRunning = true;
    }

    private static int checksum(String is) {
        int rv = 0;
        for (int i = 0; i < is.length(); i++) {
            int val = is.charAt(i);
            rv ^= val;
        }
        return rv;
    }

    public void run() {
        BufferedReader in = null;
        PrintWriter out = null;
        long lastTime = 0;
        startRunning();

        try {
            mSocket.setSoTimeout(100);
            out = new PrintWriter(mSocket.getOutputStream(), true);
            in = new BufferedReader(new InputStreamReader(
                    mSocket.getInputStream()));
            int input;
            while (mSocket.isConnected() && isRunning()) {
                if (in.ready()) {
                    input = in.read();
                    switch (input) {
                        case '+':
                            mDepth += Math.random();
                            break;
                        case '-':
                            mDepth -= Math.random();
                            break;
                        case ')':
                            mTemp += Math.random() * 10;
                            break;
                        case '(':
                            mTemp -= Math.random() * 10;
                            break;
                        case 'n':
                            mDepth = Double.NaN;
                            break;
                        case '0':
                            mDepth = 0;
                            break;
                        case 'r':
                            mDepth = DEFAULT_DEPTH;
                            break;
                        case 'x':
                            kill();
                            break;
                        default:
                            mDepth = mDepth;
                    }
                }
                long currentTime = System.currentTimeMillis();
                if ((currentTime - lastTime) >= UPDATE_INTERVAL) {

                    lastTime = currentTime;
                    String dsf, dsm, dsF;
                    if (Double.isNaN(mDepth)) {
                        dsf = "";
                        dsm = "";
                        dsF = "";
                    } else {
                        dsf = String.format("%03.1f", mDepth * 3.2808399);
                        dsm = String.format("%03.1f", mDepth);
                        dsF = String.format("%03.1f", mDepth * 0.546806649);
                    }
                    String os;
                    String cs;
                    os = ("SDDPT," + dsm + ",");
                    cs = String.format("%02X", checksum(os));
                    out.print("$" + os + "*" + cs + "\r\n");
                    os = ("SDDBT," + dsf + ",f," + dsm + ",M," + dsF + ",F");
                    cs = String.format("%02X", checksum(os));
                    out.print("$" + os + "*" + cs + "\r\n");
                    os = ("YXMTW," + String.format("%03.1f", mTemp) + ",C");
                    cs = String.format("%02X", checksum(os));
                    out.print("$" + os + "*" + cs + "\r\n");
                    out.flush();
                } else {
                    try {
                        Thread.sleep(100);
                    } catch (Exception e) {
                        e.printStackTrace();
                    }
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
        try {
            mSocket.close();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
