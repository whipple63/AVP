/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package edu.unc.ims.util;

import java.net.*;
import java.io.*;
import java.util.Formatter;
import java.util.Locale;

/**
 *
 * @author danb
 */
public class SounderSim { // implements Runnable {

    private static final int UPDATE_INTERVAL = 1000;
    private static boolean mRunning;
    private static final int PORT = 5440;
    private static final double DEFAULT_DEPTH = 4.3;
    private static double mDepth;
    private static double mTemp;

    public SounderSim() {
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

    public static void main(String[] args) {
        ServerSocket serverSocket = null;
        Socket clientSocket = null;
        BufferedReader in = null;
        PrintWriter out = null;
        boolean connected = false;
        long lastTime = 0;
        startRunning();
        try {
            serverSocket = new ServerSocket(PORT);
        } catch (IOException e) {
            System.err.println("Could not listen on port " + PORT + ".");
            System.exit(1);
        }

        while (isRunning()) {
            try {
                serverSocket.setSoTimeout(100);
                clientSocket = serverSocket.accept();
                clientSocket.setSoTimeout(100);
                new Thread(new SounderSimHandler(clientSocket)).start();
            } catch (Exception e) {
            }
        }
        try {
            serverSocket.close();
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
}
