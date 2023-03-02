package edu.unc.ims.instruments.lisst;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;

/**
 * a tiny version of Ward Christensen's MODEM program for UNIX.
 * Written ~ 1980 by Andrew Scott Beals. Last revised 1982.
 * A.D. 2000 - dragged from the archives for use in Java Cookbook.
 * 2011 - modified to do single file ymodem receives
 *
 * @author C version by Andrew Scott Beals, sjobrg.andy%mit-oz@mit-mc.arpa.
 * @author Java version by Ian F. Darwin, http://www.darwinsys.com/
 * @author YModem mods by Tony Whipple whipple@email.unc.edu
 */
public class YModem {
    private boolean mDebugThis = true;

    protected final int  MAXERRORS = 10;    /* max times to retry one block */
    protected final int  SECSIZE   = 128;   /* cpm sector, transmission block */
    protected final int  SENTIMOUT = 30;    /* timeout time in send */
    protected final int  SLEEP     = 30;    /* timeout time in recv */

    /* Protocol characters used */
    protected final byte  SOH    = 1;   /* Start Of Header */
    protected final byte  STX    = 2;   /* Begins 1k sector */
    protected final byte  EOT    = 4;   /* End Of Transmission */
    protected final byte  ACK    = 6;   /* ACKnowlege */
    protected final byte  NAK    = 0x15;/* Negative AcKnowlege */
    protected final byte  CPMEOF = 26;  /* control/z */

    protected InputStream  inStream;
    protected OutputStream outStream;
    protected PrintWriter  errStream;

    protected boolean standalone = false;
//    protected boolean gotChar;   // A flag used to communicate with inner class IOTimer

  /** Construct */
    public YModem(InputStream is, OutputStream os, PrintWriter errs) {
        inStream  = is;
        outStream = os;
        errStream = errs;
        if (mDebugThis==true) {
            System.out.println("YModem inStream: " + inStream.toString() + " outStream: " +
                    outStream.toString() + " errStream: " + errStream.toString());
        }
    }

    /** Construct with default files (stdin and stdout). */
    public YModem() {
        inStream  = System.in;
        outStream = System.out;
        errStream = new PrintWriter(System.err);
        if (mDebugThis==true) {
            System.out.println("YModem inStream: " + inStream.toString() + " outStream: " +
                    outStream.toString() + " errStream: " + errStream.toString());
        }
    }

    /**
     * A main program, for direct invocation.
     *
     * Exit code 0 for success 1 for failure
     * 
     * @param argv
     * @throws IOException
     * @throws InterruptedException
     */
    public static void main(String[] argv) throws IOException, InterruptedException, FileTransferException {
        // argc must == 1 or 2, i.e., `java YModem -s filename'.
        // -r can be used with no filename
        if (argv.length < 1)          { usage(); }
        if (argv[0].charAt(0) != '-') { usage(); }

        YModem ym = new YModem();
        ym.setStandalone(true);

        // ymodem batch file handling is not set up.  I don't intend to use it that way.
        switch (argv[0].charAt(1)) {
            case 'r':
                if (argv.length == 1) {
                    ym.receive("");        // receive using filename in header
                } else {
                    ym.receive(argv[1]);   // receive using specified filename
                }
                break;
            case 's':   // YModem send is not yet implemented
                ym.sendXModem(argv[1]);    // send specified filename
                break;
            default:
                usage();
        }
        System.out.print("Done OK");
        System.exit(0);
    }

    /* give user minimal usage message */
    protected static void usage() {
        System.err.println("usage: YModem -r/-s file");
        System.exit(1);     // not errStream, not die(), since this is static.
    }

    /** If we're in a standalone application it is OK to System.exit() */
    public void setStandalone(boolean is) {
        standalone = is;
    }
    public boolean isStandalone() {
        return standalone;
    }

    protected byte getchar() throws IOException, FileTransferException {
        // getchar needs to do the input stream timing so reads won't block
        // forever.
        long startTime = System.currentTimeMillis();
        byte b = 0;
        while (System.currentTimeMillis()-startTime < SLEEP * 1000) {
            if (inStream.available() > 0) {
                break;
            }
            try { Thread.sleep(1);
            }  catch (InterruptedException e) { e.printStackTrace(); }
        }
        // did we time out or get a char?
        if (inStream.available() > 0) {
            b = (byte) inStream.read();
            if (mDebugThis==true) { 
                if (b > 31 && b < 127) {
                    System.out.print(String.valueOf((char)b));
                } else {
                    System.out.print(" "+b+" ");
                }
            }
        } else {
            errStream.println("Timed out waiting for character.");
            if (mDebugThis==true) { System.out.println("getchar: Timed out waiting for character."); }
            die(1);
        }
        return b;
    }
    protected void putchar(int c) throws IOException {
        outStream.write(c);
        if (mDebugThis==true) { System.out.println("\nputchar: " + String.valueOf((char)c)); }
    }

    protected void xerror() throws FileTransferException {
        errStream.println("too many errors...aborting");
        if (mDebugThis==true) { System.out.println("xerror: Too many errors...aborting"); }
        die(1);     // either exits or throws exception
    }

    protected void die(int how) throws FileTransferException {
        if (standalone) {
            System.exit(how);
        } else {
            throw new FileTransferException("Error code " + Integer.toString(how));
        }
    }

  /**
   * receive ymodem data
   * @param tfile
   * @throws IOException
   * @throws InterruptedException
   */
  public void receive(String tfile) throws IOException, InterruptedException, FileTransferException
  {
    char index, blocknumber, errorcount;
    int crc, read_crc, hb, lb;
    byte character;
    byte[] sector = new byte[SECSIZE];
    String headerFileName;
    String file_length = null;

    /* get the filename from the data */
//    System.out.println("you have " + SLEEP + " seconds...");

    while (true) {
        errStream.println("Starting receive...");
        if (mDebugThis == true) { System.out.println("Starting receive..."); }
        putchar('C');           // C to start CRC transmission
        errorcount = 0;
        blocknumber = 0;        // block 0 for the header
        rxLoop:
        do {
          character = getchar();
    //      gotChar = true;
          if (character != EOT) {
            try {
              byte not_ch;
              if (character != SOH) {
                errStream.println( "Not SOH");
                if (mDebugThis == true) { System.out.println("Not SOH"); }
                if (++errorcount < MAXERRORS)
                  continue rxLoop;
                else
                  xerror();
              }
              character = getchar();        // should be block number
              not_ch = (byte)(~getchar());  // ones complement of block number (flipped again to equal char)
              errStream.println( "\n[" +  character + "] ");
              if (mDebugThis == true) { System.out.println("[" +  character + "] "); }
              if (character != not_ch) {
                errStream.println( "Blockcount and its ones complement don't match.");
                if (mDebugThis == true) { System.out.println("Blockcount and its ones complement don't match."); }
                ++errorcount;
                continue rxLoop;
              }
              if (character != blocknumber) {
                errStream.println( "Wrong blocknumber");
                if (mDebugThis == true) { System.out.println("Wrong blocknumber"); }
                ++errorcount;
                continue rxLoop;
              }
              // Start reading the header data here.
              crc = 0;
              for (index = 0; index < SECSIZE; index++) {
                sector[index] = getchar();          // read in the sector
                crc = crc ^ sector[index] << 8;     // and calculate the crc
                byte i = 8;
                do {
                    if ((crc & 0x8000) != 0) {
                        crc = crc << 1 ^ 0x1021;
                    } else {
                        crc = crc << 1;
                    }
                } while (--i > 0);
              }
              crc &= 0xffff;

              hb = getchar() & 0xff;   // hi byte
              lb = getchar() & 0xff;   // lo byte
              read_crc = ((hb<<8) | lb) & 0xffff;
              if (crc != read_crc) {
                errStream.println( "Bad crc checksum");
                if (mDebugThis == true) { System.out.println("Bad crc checksum"); }
                errorcount++;
                continue rxLoop;
              }
              putchar(ACK);     // we have the header.  acknowledge
              errorcount = 0;   // if we made it here we must be in sync...
              break rxLoop;

            } finally {
            if (errorcount != 0)
              putchar(NAK);
          }
        }
        } while (true);   // dummy loop - quickest mod given break and continue statements

        // extract info from the header
        String[] t = new String(sector).replaceAll("\000", " ").split(" ");
        headerFileName = "";
        if (t.length > 0) { headerFileName = t[0]; }
        if (mDebugThis == true) { System.out.println("File Name from header: '"+headerFileName+"'"); }
        if (t.length > 1) { file_length = t[1]; }
        if (mDebugThis == true) { System.out.println("File Length: '"+file_length+"'"); }

        // WAY OUT: null file name in header
        if (headerFileName.equals("")) {
            break;  // out of the while true loop
        }

        // Use the header file name if the file name wasn't specified
        if (tfile.equals("")) {
            tfile = headerFileName;
        }

        if (file_length != null) {
            receiveXModemCRC(tfile, Long.valueOf(file_length));
        } else {
            // ready to read the blocks of data with the correct filename
            receiveXModemCRC(tfile, Long.MAX_VALUE);
        }

        // reset the file name and loop to see if the sender has more files
        tfile = "";
      } // end of while true loop
  }

    /*
     * receive a file from the remote XModem Style with regular checksums
     * This routine is untested.  I modified it in parallel to the CRC version
     * which is tested, so it should work.
     */
    public void receiveXModem(String tfile) throws IOException, InterruptedException, FileTransferException {
        char checksum, index, blocknumber, errorcount;
        byte character;
        int thisSectorSize;
        DataOutputStream foo;

        foo = new DataOutputStream(new FileOutputStream(tfile));

        System.out.println("you have " + SLEEP + " seconds...");

        errStream.println("Starting receive...");
        putchar(NAK);
        errorcount = 0;
        blocknumber = 1;
        character = getchar();
        rxLoop:
        do {
            character = getchar();
            if (character != EOT) {
                try {
                    byte not_ch;
                    if (character != SOH) {
                        errStream.println("Not SOH");
                        if (++errorcount < MAXERRORS) {
                            continue rxLoop;
                        } else {
                            xerror();
                        }
                    }
                    if (character == STX) {
                        thisSectorSize = 1024;
                    } else {
                        thisSectorSize = SECSIZE;
                    }
                    byte[] sector = new byte[thisSectorSize];    // support 1k sectors
                    character = getchar();
                    not_ch = (byte) (~getchar());
                    errStream.println("[" + character + "] ");
                    if (character != not_ch) {
                        errStream.println("Blockcounts not ~");
                        ++errorcount;
                        continue rxLoop;
                    }
                    if (character != blocknumber) {
                        errStream.println("Wrong blocknumber");
                        ++errorcount;
                        continue rxLoop;
                    }
                    checksum = 0;
                    for (index = 0; index < thisSectorSize; index++) {
                        sector[index] = getchar();
                        checksum += sector[index];
                    }
                    if (checksum != getchar()) {
                        errStream.println("Bad checksum");
                        errorcount++;
                        continue rxLoop;
                    }
                    putchar(ACK);
                    blocknumber++;
                    try {
                        foo.write(sector);
                    } catch (IOException e) {
                        errStream.println("write failed, blocknumber " + blocknumber);
                    }
                } finally {
                    if (errorcount != 0) {
                        putchar(NAK);
                    }
                }
            }
            character = getchar();
        } while (character != EOT);

        foo.close();

        putchar(ACK);  /* tell the other end we accepted his EOT   */
        putchar(ACK);
        putchar(ACK);

        errStream.println("Receive Completed.");
    }

    /*
     * receive a file from the remote XModem Style with CRC checksums
     */
    public void receiveXModemCRC(String tfile, long file_length)
            throws IOException, InterruptedException, FileTransferException {
        char index, blocknumber, errorcount;
        int crc, read_crc, hb, lb;
        byte character;
        DataOutputStream foo;
        int thisSectorSize;
        int writeLength = 0;

        foo = new DataOutputStream(new FileOutputStream(tfile));

        errStream.println("Starting XModemCRC receive...");
        if (mDebugThis == true) { System.out.println("Starting XModemCRC receive..."); }
        putchar('C');
        errorcount = 0;
        blocknumber = 1;
        character = getchar();
        rxLoop:
        do {
            if (character != EOT) {
                try {
                    byte not_ch;
                    if ((character != SOH) && (character != STX)) {
                        errStream.println("Not SOH");
                        if (mDebugThis == true) { System.out.println("Not SOH"); }
                        if (++errorcount < MAXERRORS) {
                            continue rxLoop;
                        } else {
                            xerror();
                        }
                    }
                    if (character == STX) {
                        thisSectorSize = 1024;
                    } else {
                        thisSectorSize = SECSIZE;
                    }
                    byte[] sector = new byte[thisSectorSize];    // support 1k sectors
                    character = getchar();
                    not_ch = (byte) (~getchar());
                    errStream.println("\n[" + character + "] ");
                    if (mDebugThis == true) { System.out.println("[" + character + "] "); }
                    if (character != not_ch) {
                        errStream.println("Blockcounts not ~");
                        if (mDebugThis == true) { System.out.println("Blockcounts not ~"); }
                        ++errorcount;
                        continue rxLoop;
                    }
                    if (character != blocknumber) {
                        errStream.println("Wrong blocknumber");
                        if (mDebugThis == true) { System.out.println("Wrong blocknumber"); }
                        ++errorcount;
                        continue rxLoop;
                    }
                    crc = 0;
                    for (index = 0; index < thisSectorSize; index++) {
                        sector[index] = getchar();
                        crc = crc ^ sector[index] << 8;     // and calculate the crc
                        byte i = 8;
                        do {
                            if ((crc & 0x8000) != 0) {
                                crc = crc << 1 ^ 0x1021;
                            } else {
                                crc = crc << 1;
                            }
                        } while (--i > 0);
                    }
                    crc &= 0xffff;

                    hb = getchar() & 0xff;   // hi byte
//                    System.out.println("hb:" + Integer.toHexString(hb));
                    lb = getchar() & 0xff;   // lo byte
//                    System.out.println("lb:" + Integer.toHexString(lb));
                    read_crc = ((hb << 8) | lb) & 0xffff;
//                    System.out.println("read_crc:" + Integer.toHexString(read_crc));
                    if (crc != read_crc) {
                        errStream.println("Bad checksum");
                        if (mDebugThis == true) { System.out.println("Bad checksum"); }
                        errorcount++;
                        continue rxLoop;
                    }
                    putchar(ACK);
                    blocknumber++;
                    try {
                        if (writeLength+sector.length > file_length) {
                            foo.write(sector, 0, (int)(file_length-writeLength) );
                            writeLength = writeLength + (int) (file_length-writeLength);
                        } else {
                            foo.write(sector);
                            writeLength = writeLength + sector.length;
                        }
                    } catch (IOException e) {
                        errStream.println("write failed, blocknumber " + blocknumber);
                        if (mDebugThis == true) { System.out.println("write failed, blocknumber " + blocknumber); }
                    }
                } finally {
                    if (errorcount != 0) {
                        putchar(NAK);
                    }
                }
            }
            character = getchar();  // get the first char of the next block
        } while (character != EOT);

        foo.close();

        putchar(ACK);  /* tell the other end we accepted his EOT   */
        putchar(ACK);
        putchar(ACK);

        errStream.println("Receive Completed.");
        if (mDebugThis == true) { System.out.println("Receive Completed."); }
    }

    /*
     * sendXModem a file to the remote
     * NOTE this is still xmodem.  Modifying receive first since that is what I need.
     */
    public void sendXModem(String tfile) throws IOException, InterruptedException, FileTransferException {
        char checksum, index, blocknumber, errorcount;
        byte character;
        byte[] sector = new byte[SECSIZE];
        int nbytes;
        DataInputStream foo;

        foo = new DataInputStream(new FileInputStream(tfile));
        errStream.println("file open, ready to send");
        errorcount = 0;
        blocknumber = 1;

        do {
            character = getchar();
//            gotChar = true;
            if (character != NAK && errorcount < MAXERRORS) {
                ++errorcount;
            }
        } while (character != NAK && errorcount < MAXERRORS);

        errStream.println("transmission beginning");
        if (errorcount == MAXERRORS) {
            xerror();
        }

        while ((nbytes = inStream.read(sector)) != 0) {
            if (nbytes < SECSIZE) {
                sector[nbytes] = CPMEOF;
            }
            errorcount = 0;
            while (errorcount < MAXERRORS) {
                errStream.println("{" + blocknumber + "} ");
                putchar(SOH);  /* here is our header */
                putchar(blocknumber);  /* the block number */
                putchar(~blocknumber);  /* & its complement */
                checksum = 0;
                for (index = 0; index < SECSIZE; index++) {
                    putchar(sector[index]);
                    checksum += sector[index];
                }
                putchar(checksum);  /* tell our checksum */
                if (getchar() != ACK) {
                    ++errorcount;
                } else {
                    break;
                }
            }
            if (errorcount == MAXERRORS) {
                xerror();
            }
            ++blocknumber;
        }
        boolean isAck = false;
        while (!isAck) {
            putchar(EOT);
            isAck = getchar() == ACK;
        }
        errStream.println("Transmission complete.");
    }

}


