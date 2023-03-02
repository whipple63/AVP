package edu.unc.ims.instruments.sounders.NMEA;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.io.PrintStream;
import edu.unc.ims.instruments.sounders.*;

/**
Simple command-line application for testing the Sounder.
Test the Sounder class.  Goes into a command loop and lets user interactively
control the compass.
*/
public class NMEASounderConsole implements SounderListener {
    /**
    NMEASounderConsole.
    @throws Exception all
    */
    protected NMEASounderConsole() throws Exception {
        NMEASounder s = new NMEASounder("avp3.dyndns.org", 55237);
        s.addListener(this);
        BufferedReader br = new BufferedReader(new InputStreamReader(
            System.in));
        printCommands();
        PrintStream ps = new PrintStream(System.out, true);
        for (;;) {
            String l = br.readLine();
            if (l.equals("start")) {
                s.startSampling();
            } else if (l.equals("connect")) {
                ps.println("connecting...");
                s.connect();
                ps.println("connected");
            } else if (l.equals("disconnect")) {
                ps.println("disconnecting...");
                s.disconnect();
                ps.println("disconnected");
            } else if (l.equals("stop")) {
                ps.println("stopping...");
                s.stopSampling();
                ps.println("stopped");
            } else if (l.startsWith("x")) {
                break;
            } else {
                printCommands();
            }
        }
        ps.println("disconnecting...");
        s.disconnect();
        ps.println("disconnected");
    }

    /**
    Called when a measurement is made.
    @param  d   the data.
    */
    public final void onMeasurement(final SounderData d) {
        System.out.println(
            d.getDepthM() + "\t"
            + d.getDepthf() + "\t"
            + d.getDepthF() + "\t"
            + d.getTempC());
    }

    /**
    Main method for testing.

    @param  args    stuff

    @throws Exception   on error
    */
    public static void main(final String [] args) throws Exception {
        new NMEASounderConsole();
    }

    /**
    Prints usage.
    */
    public static void printCommands() {
        System.out.println("Commands:");
        System.out.println("connect                Establish connection");
        System.out.println("disconnect             Close connection");
        System.out.println("start                  Start data collection");
        System.out.println("stop                   Stop data collection");
        System.out.flush();
    }
}
