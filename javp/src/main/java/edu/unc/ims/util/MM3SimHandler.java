/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */
package edu.unc.ims.util;

import java.net.*;
import java.io.*;
import edu.unc.ims.instruments.motionmind3.*;

/**
 *
 * @author danb
 */
public class MM3SimHandler implements Runnable {

    private static boolean mRunning;
    private static final int PORT = 5440;
    private static Socket mSocket;

    public MM3SimHandler(Socket socket) {
        mSocket = socket;
    }

    public void setCommand(MM3Command cmd) {
    }

    /**
     *
     */
    public String getCommand() {
        return "hello world";
    }

    /*
     *
     */
    public long getInterval() {
        return 3;
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

    public void run() {
        BufferedReader in = null;
        PrintWriter out = null;
        long lastTime = 0;
        startRunning();

        try {
//            mSocket.setSoTimeout(100);
            out = new PrintWriter(mSocket.getOutputStream(), true);
            in = new BufferedReader(new InputStreamReader(
                    mSocket.getInputStream()));
            String input;
            while (mSocket.isConnected() && isRunning()) {
                if (in.ready()) {
                    input = in.readLine();
                    if (input != null) {
                        input = input.toUpperCase();
                        String output = "";
                        System.out.println("RX: " + input); //debug
                        String[] fields = input.split(" ");
                        if (fields[0].equals("R01")) {
                            int requestInt = Integer.parseInt(fields[1]);
                            if (requestInt == 99) {
                                for (int i = 0; i < 32; i++) {
                                    output = output + (int) (Math.random()
                                            * 16384) + ",";
                                }
                            }
                        } else {
                            output = "OK";
                        }
                        out.println(output);
                        out.flush();
                        System.out.println("TX: " + output); //debug
                    } else {
                        break;
                    }
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
