/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package edu.unc.ims.util;

import java.net.*;
import java.io.*;

/**
 *
 * @author danb
 */
public class MM3Sim { // implements Runnable {

    private static boolean mRunning;
    private static final int PORT = 5440;

    public MM3Sim() {
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

    public static void main(String[] args) {
        ServerSocket serverSocket = null;
        Socket clientSocket = null;
        startRunning();
        try {
            serverSocket = new ServerSocket(PORT);
        } catch (IOException e) {
            System.err.println("Could not listen on port " + PORT + ".");
            System.exit(1);
        }

        while (isRunning()) {
            try {
//                serverSocket.setSoTimeout(100);
                clientSocket = serverSocket.accept();
//                clientSocket.setSoTimeout(100);
                new Thread(new MM3SimHandler(clientSocket)).start();
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
