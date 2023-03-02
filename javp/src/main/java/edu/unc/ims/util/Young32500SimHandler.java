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
public class Young32500SimHandler implements Runnable { // implements Runnable {

    private static final int UPDATE_INTERVAL = 1000;
    private static boolean mRunning;
    private static Socket mSocket;

    public Young32500SimHandler(Socket socket) {
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
                }
                long currentTime = System.currentTimeMillis();
                if ((currentTime - lastTime) >= UPDATE_INTERVAL) {
                    lastTime = currentTime;
                    int n;
                    String ns = "";
                    for(int i = 0; i < 8; i++) {
                        n = (int)(Math.random() * 10000);
                        ns = ns + String.format("%04d", n);
                        if(i != 7) {
                            ns = ns + " ";
                        }
                    }
                    out.print(ns + "\r\n");
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
