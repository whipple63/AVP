package edu.unc.ims.instruments.motionmind3;

import java.net.Socket;
import java.io.BufferedInputStream;
import java.io.OutputStream;
import java.io.IOException;
import java.net.UnknownHostException;
import java.util.HashMap;
import java.util.Vector;
import java.util.Iterator;
import java.math.BigInteger;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;
import edu.unc.ims.instruments.UnknownStateException;
import edu.unc.ims.instruments.UnsupportedStateException;
import edu.unc.ims.instruments.TimeoutException;


/**
MotionMind3 Motor Controller.
 */
public final class MM3 {

    /* it's possible to have more than one device on a bus, but we will assume
    this is the only one, for now */
    private static final byte DEVICE_ADDRESS = 1;
    /* binary command mappings */
    public static final HashMap<String, Byte> bCommandMap =
            new HashMap<String, Byte>();

    /* ascii command mappings */
    public static final HashMap<String, String> aCommandMap =
            new HashMap<String, String>();
    /* register location mappings */
    public static final HashMap<String, Integer> registerMap =
            new HashMap<String, Integer>();
    /* register byte widths */
    public static final HashMap<String, Integer> widthMap =
            new HashMap<String, Integer>();

    // saved register information to reduce polling frequency
    public HashMap<String, Integer> mSavedRegisterValues =
            new HashMap<String, Integer>();
//    public HashMap<String, Long> mSavedRegisterTimes =
//            new HashMap<String, Long>();
    public HashMap<String, Long> mSavedRegisterAccessTimes =
            new HashMap<String, Long>();
    public Long mLastReadTime = 0L;
    public static final int POLL_PERIOD = 200;

    private static final int DEFAULT_RETRIES = 3;
    /* according to the manual, operations can take up to 2.5ms to process */
    private static final int DEFAULT_PROC_TIME = 250;
    /* according to the manual, write_store can take up to 40ms to process */
    private static final int DEFAULT_WS_PROC_TIME = 400;
    private static final int DEFAULT_LATENCY_PER_CHARACTER = 30;
    private static final byte BINARY_OK = (byte) 0x06;
    /* use binary mode? */
    /**
    Internal state.
     */
    private int mState = S_DISCONNECTED;
    /**
    Hostname.
     */
    private String mHost;
    /**
    Port number.
     */
    private int mPort;
    /**
    Socket.
     */
    private Socket mSocket;
    private BufferedInputStream mInStream;
    private OutputStream mOutStream;

    private String mPortName;

    private long mSendBytesExitTime = 0;
    private static long SEND_BYTES_DELAY = 20;  // ms.

    /**
    Create a compass communication channel.
    Creates the channel, but does not open it.

    @param  host    Hostname
    @param  port    Port number

    @see #connect
     */
    public MM3(final String host, final int port) {
        mHost = host;
        mPort = port;
    }
    
    public MM3(final String portName) {
        mPortName = portName;
    }

    /**
    Connect to the MotionMind3.
    Attempts to open a connection to the motor controller, makes a best-effort
    attempt to determine current state of the device and puts it into a known
    state.
    <p>
    If successful, the state will be as described in the reset() method.
    <p>
    <b>You must call disconnect() to free up resources!</b>

    @see #reset
    @throws UnknownHostException    Unknown host or bad IP.
    @throws IOException IO error.
    @throws UnknownStateException    If state cannot be determined, a power
    cycle is probably required.
    @throws UnsupportedStateException   Check message for details.
     */
    public void connect() throws UnknownStateException, UnknownHostException,
            IOException, UnsupportedStateException {
        if (mState != S_DISCONNECTED) {
            throw new UnsupportedStateException("You must call disconnect()");
        }
        mSocket = new Socket(mHost, mPort);
        mInStream = new BufferedInputStream(mSocket.getInputStream());
        mOutStream = mSocket.getOutputStream();
        try {
            setState(S_CONNECTED);
            readRegister("function");   // try to do something - anything to see if we are connected
//            reset();
            Logger.getLogger().log("MM3 connected.",
                    this.getClass().getName(), LogLevel.INFO);
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(),
                    this.getClass().getName(), LogLevel.ERROR);
            setState(S_DISCONNECTED);
            try {
                disconnect();
            } catch (Exception ee) {
            }
            throw new UnknownStateException();
        }
    }

    private static final int PORT_OPEN_TIMEOUT = 2000;

 
    /**
    Sets instrument socket state to S_CONNECTED or S_DISCONNECTED
    @param state
     */
    private void setState(final int state) {
        mState = state;
    }

    /**
    Disconnect.
     */
    public void disconnect() {
        /* attempt to set velocity to zero */
        try {
                moveAt(0);
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(),
                    this.getClass().getName(), LogLevel.ERROR);
        }
        
        // the close needs a separate try statemenmt so that if the above fails we still clean
        // up the socket
        try {
            mInStream.close();
            mOutStream.close();
            mSocket.close();
            setState(S_DISCONNECTED);
        } catch (Exception e) {
            Logger.getLogger().log(e.toString(),
                    this.getClass().getName(), LogLevel.ERROR);
        }
    }

    /**
    Sets PID terms.

    @param  p P term
    @param  i I term
    @param  d D term

    @throws Exception on error
     */
    public void setPIDTerms(int p, int i, int d) throws TimeoutException,
            IOException, UnsupportedStateException {
            if (write("p_term", p)) {
                if (write("i_term", i)) {
                    write("d_term", d);
                }
            }
    }

    public boolean changeSpeed(int value) throws UnsupportedStateException,
            TimeoutException, IOException {
        byte[] command = new byte[5];
        command[0] = bCommandMap.get("CH_SPD");
        command[1] = DEVICE_ADDRESS;
        command[2] = (byte) (value & 0xFF);
        command[3] = (byte) ((value >> 8) & 0xFF);
        command[4] = computeChecksum(command);
        byte[] result =
                sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);
        return result[0] == BINARY_OK;
    }

    public boolean moveAbs(int value) throws UnsupportedStateException,
            TimeoutException, IOException {
        byte[] command = new byte[7];
        command[0] = bCommandMap.get("MOVE_ABS");
        command[1] = DEVICE_ADDRESS;
        command[2] = (byte) (value & 0xFF);
        command[3] = (byte) ((value >> 8) & 0xFF);
        command[4] = (byte) ((value >> 16) & 0xFF);
        command[5] = (byte) ((value >> 24) & 0xFF);
        command[6] = computeChecksum(command);
        byte[] result =
                sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);
        return result[0] == BINARY_OK;
    }

    public boolean moveRel(int value) throws UnsupportedStateException,
            TimeoutException, IOException {
        byte[] command = new byte[7];
        command[0] = bCommandMap.get("MOVE_REL");
        command[1] = DEVICE_ADDRESS;
        command[2] = (byte) (value & 0xFF);
        command[3] = (byte) ((value >> 8) & 0xFF);
        command[4] = (byte) ((value >> 16) & 0xFF);
        command[5] = (byte) ((value >> 24) & 0xFF);
        command[6] = computeChecksum(command);
        byte[] result =
                sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);
        return result[0] == BINARY_OK;
    }

    public boolean moveAt(int value) throws UnsupportedStateException,
            TimeoutException, IOException {
        byte[] command = new byte[5];
        command[0] = bCommandMap.get("MOVE_AT");
        command[1] = DEVICE_ADDRESS;
        command[2] = (byte) (value & 0xFF);
        command[3] = (byte) ((value >> 8) & 0xFF);
        command[4] = computeChecksum(command);
        byte[] result =
                sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);
        return result[0] == BINARY_OK;
    }

    public boolean write(String register, int value) throws
            UnsupportedStateException, TimeoutException, IOException {
        int position;
        int width = widthMap.get(register);
        byte[] command = new byte[4 + width];
        position = registerMap.get(register);
        command[0] = bCommandMap.get("WRITE");
        command[1] = DEVICE_ADDRESS;
        command[2] = (byte) position;
        for (int i = 0; i < width; i++) {
            command[i + 3] = (byte) ((value >> (8 * i)) & 0xFF);
        }
        command[command.length - 1] = computeChecksum(command);
        byte[] result =
                sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);
        return result[0] == BINARY_OK;
    }

    public boolean writeStore(String register, int value) throws
            UnsupportedStateException, TimeoutException, IOException {
        int position;
        int width = widthMap.get(register);
        byte[] command = new byte[4 + width];
        position = registerMap.get(register);
        command[0] = bCommandMap.get("WRITE_ST");
        command[1] = DEVICE_ADDRESS;
        command[2] = (byte) position;
        for (int i = 0; i < width; i++) {
            command[i + 3] = (byte) ((value >> (8 * i)) & 0xFF);
        }
        command[command.length - 1] = computeChecksum(command);
        byte[] result =
                sendBytes(command, DEFAULT_RETRIES, DEFAULT_WS_PROC_TIME);
        return result[0] == BINARY_OK;
    }

    //TODO: throw ArrayIndexOutOfBoundsException, catch and report as invalid response
    public int readRegister(String register) throws UnsupportedStateException,
            TimeoutException, IOException {
        int regWord = 0;
        Vector<String> registerVector = new Vector<String>();
        int position, mask, vectorIndex;
        byte[] command = new byte[4];
        position = registerMap.get(register);
        command[0] = bCommandMap.get("READ_REG");
        command[1] = DEVICE_ADDRESS;
        command[2] = (byte) position;
        command[3] = computeChecksum(command);
        byte[] result = sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);
        int index = 1;
        int width;
        int value;
        width = widthMap.get(register);
        byte[] bigByte = new byte[width];
        for (int i = 1; i <= width; i++) {
            bigByte[width - i] = result[i];
        }
        value = (new BigInteger(bigByte)).intValue();
        return value;
    }

    public boolean reset() throws UnsupportedStateException, TimeoutException,
            IOException {
        byte[] command = new byte[3];
        command[0] = bCommandMap.get("RESET");
        command[1] = DEVICE_ADDRESS;
        command[2] = computeChecksum(command);
        byte[] result = sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);
        return (result[0] == BINARY_OK);
    }

    public boolean restore() throws UnsupportedStateException, TimeoutException,
            IOException {
        
        int stateWas = mState;
        if (mState == S_DISCONNECTED) {
            try { connect(); }
            catch (Exception e) {
                Logger.getLogger().log(e.toString(), this.getClass().getName(), LogLevel.ERROR);
                }
            }

        byte[] command = new byte[3];
        command[0] = bCommandMap.get("RESTORE");
        command[1] = DEVICE_ADDRESS;
        command[2] = computeChecksum(command);
        byte[] result = sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);

        if (stateWas == S_DISCONNECTED && mState != S_DISCONNECTED) {
            disconnect();
        }

        return (result[0] == BINARY_OK);
    }

    public void read(HashMap<String, Integer> registers) throws
            UnsupportedStateException, TimeoutException, IOException {
        int regWord = 0;
        Iterator<String> iter1 = registers.keySet().iterator();
        /* registerVector required to identify the positions at which the results
        will occur in the reply from the instrument */
        Vector<String> registerVector = new Vector<String>();
        String register;
        int position, mask, vectorIndex;
        byte[] command = new byte[7];
        boolean needToRead = false;

        // First check saved values to see if they are less than POLL_PERIOD old.
        // If we don't have a value, or the value we have is too old, do a read
        // of all values in the list.
        // Otherwise just return what we have along with it's timestamp.  Also maintain
        // last access time.  At some point, check the list to see if the last access
        // time is more than 10 times the poll period, and if so, drop it from the list.

        // check to see what values are old and should be dropped from the list
        // if we have no saved values, initialize
        if (mSavedRegisterValues.isEmpty() == false) {
            Iterator<String> iter2 = mSavedRegisterValues.keySet().iterator();
            while (iter2.hasNext()) {
                register = iter2.next();
                if ( (System.currentTimeMillis() - mSavedRegisterAccessTimes.get(register)) >
                        POLL_PERIOD * 10) {
                    iter2.remove(); // should remove mSavedRegisterValues(register) from the hashmap
                    mSavedRegisterAccessTimes.remove(register);
//                    Logger.getLogger().log("Removing " + register + " from saved list.",
//                            this.getClass().getName(), LogLevel.DEBUG);
                }
            }
        }

        // Check to see if requested values are in the saved list, if not add them.
        while (iter1.hasNext()) {
            register = iter1.next();
            if (mSavedRegisterValues.isEmpty() == false && mSavedRegisterValues.containsKey(register)) {
                if ( (mLastReadTime  + POLL_PERIOD) > System.currentTimeMillis() ) {    // not yet time to read
                    registers.put(register, mSavedRegisterValues.get(register));
                    mSavedRegisterAccessTimes.put(register, System.currentTimeMillis());
                } else {
                    needToRead = true;
                }
            } else {
                needToRead = true;
                mSavedRegisterValues.put(register, 0);
                mSavedRegisterAccessTimes.put(register, 0L);
            }
        }

        Iterator<String> iter2 = mSavedRegisterValues.keySet().iterator();
        if (needToRead == true) {
            while (iter2.hasNext()) {
                register = iter2.next();
                position = registerMap.get(register);
                mask = 1 << position;
                regWord = regWord | mask;
                /* vectorIndex = number of parameters in registerVector with lower
                positions than current register = index of current register in
                registerVector */
                vectorIndex = Integer.bitCount(regWord & (mask - 1));
                registerVector.add(vectorIndex, register);
//                Logger.getLogger().log(
//                        "Adding \'" + vectorIndex + " : " + register
//                        + "\' to registerVector.",
//                        this.getClass().getName(), LogLevel.DEBUG);
            }
//            Logger.getLogger().log(
//                    "registerVector is " + registerVector.size() + " elements long.",
//                    this.getClass().getName(), LogLevel.DEBUG);

            command[0] = bCommandMap.get("READ");
            command[1] = DEVICE_ADDRESS;
            command[2] = (byte) (regWord & 0xFF);
            command[3] = (byte) ((regWord >> 8) & 0xFF);
            command[4] = (byte) ((regWord >> 16) & 0xFF);
            command[5] = (byte) ((regWord >> 24) & 0xFF);
            command[6] = computeChecksum(command);
            byte[] result = sendBytes(command, DEFAULT_RETRIES, DEFAULT_PROC_TIME);

            int index = 1;
            int width;
            int value;
            /* is openJDK's vector iterator broken? */
            for (int j = 0; j < registerVector.size(); j++) {
                register = registerVector.get(j);
                width = widthMap.get(register);
                byte[] bigByte = new byte[width];
                for (int i = 1; i <= width; i++) {
                    bigByte[width - i] = result[index++];
                }
                value = (new BigInteger(bigByte)).intValue();
//                Logger.getLogger().log(
//                        "Adding \'" + register + " : " + value + "\' to saved result.",
//                        this.getClass().getName(), LogLevel.DEBUG);
                if (registers.containsKey(register)) {  // only return the ones asked for
                    registers.put(register, value);
                    mSavedRegisterAccessTimes.put(register, System.currentTimeMillis());
                }

                // save values and times from this read
                mSavedRegisterValues.put(register, value);
            }
            mLastReadTime = System.currentTimeMillis();
        }   // end of if need to read
    }

    public byte computeChecksum(byte[] input) {
        byte retval = input[0];
        for (int i = 1; i < (input.length - 1); i++) {
            retval += input[i];
        }
        return retval;
    }

    public static String getHexString(byte[] b) {
        String result = "";
        int lastPos = b.length - 1;
        for (int i = 0; i < b.length; i++) {
            result += Integer.toString((b[i] & 0xff) + 0x100, 16).substring(1);
            if (i < lastPos) {
                result += " ";
            }
        }
        return result;
    }

    public boolean verifyChecksum(byte[] input) {
        byte checksum = input[input.length - 1];
        return (computeChecksum(input) == checksum);
    }

    /* returns results */
    public synchronized byte[] sendBytes(byte[] bytes, int maxRetries, long processing_time)
            throws TimeoutException, IOException, UnsupportedStateException {
        int retryNum = 0;
        boolean done = false;
        byte[] reply = new byte[256];
        byte[] flushedChars = new byte[256];
        byte[] trimmedReply = null;
        int readLength;
        String sentString = "", recvString = "";
        int sleepTime;
        if (mState != S_CONNECTED) {
            throw new UnsupportedStateException(
                    "Must be connected to call sendBytes");
        }
        // Don't allow sending too quickly after having just done it
        while (System.currentTimeMillis() < mSendBytesExitTime + SEND_BYTES_DELAY) {
            try { Thread.sleep(SEND_BYTES_DELAY / 10); }
            catch(InterruptedException e) { e.printStackTrace(); }
        }
        do {
            // Log info about retries
            if (retryNum > 0) {
                Logger.getLogger().log(
                        "Retrying sendBytes.  Sent: "+sentString+" Received: "+recvString,
                        this.getClass().getName(), LogLevel.INFO);
            }
            
            // flush the input buffer
            int flen=0;
            while (mInStream.available() > 0) {
                flushedChars[flen++] = (byte) mInStream.read(); // flush input stream
            }
            if (flen>0) {
                trimmedReply = new byte[flen];
                System.arraycopy(flushedChars, 0, trimmedReply, 0, flen);
                Logger.getLogger().log("Flushing: " + getHexString( trimmedReply ),
                        this.getClass().getName(), LogLevel.DEBUG);
            }

            sentString = getHexString(bytes);
//            Logger.getLogger().log(
//                    "Sending \"" + byteString + "\" to MM3.",
//                    this.getClass().getName(), LogLevel.DEBUG);
            mOutStream.write(bytes);
            mOutStream.flush();
            sleepTime = 0;
            readLength = 0;
            // while: we haven't waited processing_time for first char
            //    or: we have chars available
            //    or: we haven't waited DEFAULT_LATENCY_PER_CHARACTER since we got a char
            while (((sleepTime < processing_time) && (readLength == 0)) || (mInStream.
                    available() > 0) || sleepTime < DEFAULT_LATENCY_PER_CHARACTER) {
                if (mInStream.available() > 0) {
                    reply[readLength] = (byte) mInStream.read();
                    readLength++;
                    sleepTime = 0;
                    if (readLength > reply.length) {
                        Logger.getLogger().log(
                                "sendBytes reply buffer overflow!",
                                this.getClass().getName(), LogLevel.ERROR);
                        break; // shouldn't happen!
                    }
                } else {
                    try {
                        Thread.sleep(DEFAULT_LATENCY_PER_CHARACTER);
                        sleepTime += DEFAULT_LATENCY_PER_CHARACTER;
                    } catch (InterruptedException ie) {
                        Logger.getLogger().log(
                                "Unexpected interrupted exception in sendBytes.",
                                this.getClass().getName(), LogLevel.ERROR);
                    }
                }
            }
            if (readLength > 0) {
                trimmedReply = new byte[readLength];
                System.arraycopy(reply, 0, trimmedReply, 0, readLength);
                recvString = getHexString(trimmedReply);
//                Logger.getLogger().log(
//                        "Received \"" + byteString + "\" from MM3.",
//                        this.getClass().getName(), LogLevel.DEBUG);
                if (verifyChecksum(trimmedReply)) {
                    if ((trimmedReply[0] == BINARY_OK) || (trimmedReply[0]
                            == bytes[1])) {
                        done = true;
                    } else {
                        Logger.getLogger().log(
                                "MM3 reply had unexpected first byte.",
                                this.getClass().getName(), LogLevel.ERROR);
                    }
                } else {
                    Logger.getLogger().log(
                            "MM3 reply had bad checksum.  Sent: "+sentString+" Received: "+recvString,
                            this.getClass().getName(), LogLevel.INFO);
                }
            }
            retryNum++;
        } while (!done && (retryNum < maxRetries));
        if (!done) {
            throw new TimeoutException();
        }
        mSendBytesExitTime = System.currentTimeMillis();
        return trimmedReply;
    }

    public boolean isConnected() {
        return (mState == S_CONNECTED);
    }

    /**
    Device states.
     */
    /**
    Disconnected state.
     */
    private static final int S_DISCONNECTED = 0;
    /**
    Connected state.
     */
    private static final int S_CONNECTED = 1;
    /**
    Collection mode.
    True if user has requested collection mode, false if not.
     */
    private boolean mCollecting = false;
    /**
    List of Listeners.
     */
    private String mLock = "lock";

    public enum MM3Parameter {

        POSITION, VELOCITYLIMIT,
        VELOCITYFF, FUNCTION, PTERM, ITERM, DTERM, ADDRESS, PIDSCALAR,
        TIMER, RCMAX, RCMIN, RCBAND, RCCOUNT, VELOCITY, TIME, STATUS, REVISION,
        MODE, ANALOGCON, ANALOGFBCK, PWMOUT, INDEXPOS, VNLIMIT, VPLIMIT,
        PWMLIMIT, DEADBAND, DESIREDPOSITION, AMPSLIMIT, AMPS, FUNCTION2,
        THERMISTOR, S0, S1, S2, S3, S4, S5, S6, S7, S8, S9, F0, F1, F2, F3, F4,
        F5, F6, F7, F8, F9, F10, F11, F12, F13, F14, F15, OK, BAD_COMMAND,
        NOVALUE,
        MOVEAT_VELOCITY, MOVETO_RELATIVE, MOVETO_ABSOLUTE, WRITE, WRITE_STORE,
        READ
    }

    public enum MM3Function {

        POSPWRUP, RETPOS, RETVEL, RETTIME, SATPROT, SAVEPOS, VELLIMIT,
        ACTIVESTOP, LASTRC, ADSTEP, ADSERIAL, ENABLEDB, RCPOSENCFDBCK, VIRTLIMIT,
        DISABLEPID, DISABLEBLINK
    }

    public enum MM3Status {

        NEGLIMIT, POSLIMIT, BRAKE, INDEX,
        BADRC, VNLIMIT, VPLIMIT, CURRENTLIMIT,
        PWMLIMIT, INPOSITION, TEMPFAULT, S11,
        S12, S13, S14, S15
    }

    static {
        bCommandMap.put("CH_SPD", (byte) 0x14);
        bCommandMap.put("MOVE_ABS", (byte) 0x15);
        bCommandMap.put("MOVE_REL", (byte) 0x16);
        bCommandMap.put("MOVE_AT", (byte) 0x17);
        bCommandMap.put("WRITE", (byte) 0x18);
        bCommandMap.put("WRITE_ST", (byte) 0x19);
        bCommandMap.put("READ", (byte) 0x1A);
        bCommandMap.put("RESTORE", (byte) 0x1B);
        bCommandMap.put("RESET", (byte) 0x1C);
        bCommandMap.put("READ_REG", (byte) 0x1D);
    }

    static {
        aCommandMap.put("CH_SPD", "C01");
        aCommandMap.put("MOVE_ABS", "P01");
        aCommandMap.put("MOVE_REL", "M01");
        aCommandMap.put("MOVE_AT", "V01");
        aCommandMap.put("WRITE", "W01");
        aCommandMap.put("WRITE_ST", "S01");
        aCommandMap.put("READ", "R01");
        aCommandMap.put("RESTORE", "X01");
        aCommandMap.put("RESET", "Y01");
    }

    static {
        registerMap.put("position", 0);
        registerMap.put("velocity_limit", 1);
        registerMap.put("velocity_ff", 2);
        registerMap.put("function", 3);
        registerMap.put("p_term", 4);
        registerMap.put("i_term", 5);
        registerMap.put("d_term", 6);
        registerMap.put("address", 7);
        registerMap.put("pid_scalar", 8);
        registerMap.put("timer", 9);
        registerMap.put("rcmax", 10);
        registerMap.put("rcmin", 11);
        registerMap.put("rcband", 12);
        registerMap.put("rccount", 13);
        registerMap.put("velocity", 14);
        registerMap.put("time", 15);
        registerMap.put("status", 16);
        registerMap.put("revision", 17);
        registerMap.put("mode", 18);
        registerMap.put("analog_con", 19);
        registerMap.put("analog_fbck", 20);
        registerMap.put("pwm_out", 21);
        registerMap.put("index_pos", 22);
        registerMap.put("vir_neg_limit", 23);
        registerMap.put("vir_pos_limit", 24);
        registerMap.put("PWM_limit", 25);
        registerMap.put("deadband", 26);
        registerMap.put("desired_position", 27);
        registerMap.put("amps_limit", 28);
        registerMap.put("amps", 29);
        registerMap.put("function2", 30);
        registerMap.put("temperature", 31);
    }

    static {
        widthMap.put("position", 4);
        widthMap.put("velocity_limit", 2);
        widthMap.put("velocity_ff", 1);
        widthMap.put("function", 2);
        widthMap.put("p_term", 2);
        widthMap.put("i_term", 2);
        widthMap.put("d_term", 2);
        widthMap.put("address", 1);
        widthMap.put("pid_scalar", 1);
        widthMap.put("timer", 1);
        widthMap.put("rcmax", 2);
        widthMap.put("rcmin", 2);
        widthMap.put("rcband", 2);
        widthMap.put("rccount", 2);
        widthMap.put("velocity", 2);
        widthMap.put("time", 4);
        widthMap.put("status", 2);
        widthMap.put("revision", 1);
        widthMap.put("mode", 1);
        widthMap.put("analog_con", 2);
        widthMap.put("analog_fbck", 2);
        widthMap.put("pwm_out", 2);
        widthMap.put("index_pos", 4);
        widthMap.put("vir_neg_limit", 4);
        widthMap.put("vir_pos_limit", 4);
        widthMap.put("PWM_limit", 2);
        widthMap.put("deadband", 2);
        widthMap.put("desired_position", 4);
        widthMap.put("amps_limit", 2);
        widthMap.put("amps", 2);
        widthMap.put("function2", 2);
        widthMap.put("temperature", 2);
    }
}
