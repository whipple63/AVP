package edu.unc.ims.instruments.aio;

/**
Controls access to the AccessIO 104-AI12-8 Analog Input/Digital IO board.
*/
public final class JAccessIO {
    /**
    Private.
    */
    private JAccessIO() { }

    /**
    Get the direction of I/O ports.
    @param  base    Base address (0x100-0x3FF)
    @throws Exception on out-of-range value
    @return int with lower nyble set to hi-C, lo-C, B and A direction bits.  1 is intput, 0 is output.
    */
    public static native int getDir(final int base) throws Exception;

    /**
    Get the direction of a given port.
    @param  base    Base address (0x100-0x3FF)
    @param portNum 0-4 (a,b,c_lo,c_hi, respectively)
    @throws Exception on out-of-range value
    @return true if port is set as an input port.
    */
    public static boolean isPortInput(final int base, int portNum) throws Exception {

        return ((getDir(base) >> portNum) & 1) == 1;
    }

    /**
    Get the direction of a given port.
    @param  base    Base address (0x100-0x3FF)
    @param portNum 0-4 (a,b,c_lo,c_hi, respectively)
    @throws Exception on out-of-range value
    @return 0 or 1 (output or input)
    */
    public static int getPortDirection(final int base, int portNum) throws Exception {

        return ((getDir(base) >> portNum) & 1);
    }

    /**
    Get the direction of the A port.
    @param  base    Base address (0x100-0x3FF)
    @throws Exception on out-of-range value
    @return true if A is set as an input port.
    */
    public static boolean isPortAInput(final int base) throws Exception {
        return (getDir(base) & 1) == 1;
    }

    /**
    Get the direction of the B port.
    @param  base    Base address (0x100-0x3FF)
    @throws Exception on out-of-range value
    @return true if B is set as an input port.
    */
    public static boolean isPortBInput(final int base) throws Exception {
        return ((getDir(base) >> 1) & 1) == 1;
    }

    /**
    Get the direction of the C-lo port.
    @param  base    Base address (0x100-0x3FF)
    @throws Exception on out-of-range value
    @return true if C-lo is set as an input port.
    */
    public static boolean isPortCLoInput(final int base) throws Exception {
        return ((getDir(base) >> 2) & 1) == 1;
    }

    /**
    Get the direction of the C-hi port.
    @param  base    Base address (0x100-0x3FF)
    @throws Exception on out-of-range value
    @return true if C-hi is set as an input port.
    */
    public static boolean isPortCHiInput(final int base) throws Exception {
        return ((getDir(base) >> 3) & 1) == 1;
    }

    /**
    Set the direction of the IO ports.
    @param  base    Base address (0x100-0x3FF)
    @param  aDir   Direction (1 for input, 0 for output)
    @param  bDir   Direction (1 for input, 0 for output)
    @param  cLoDir   Direction for C pins 3:0 (1 for input, 0 for output)
    @param  cHiDir   Direction for C pins 7:4 (1 for input, 0 for output)
    @throws Exception on out-of-range value
    */
    public static native void setDirection(final int base, final int aDir,
        final int bDir, final int cLoDir, final int cHiDir) throws
        Exception;

    /**
    Set the value of a dio pin.
    @param  base    Base address (0x100-0x3FF)
    @param  port    The port (0=A, 1=B, 2=C)
    @param  pin     The pin (0-7)
    @param  value   Value to write to the port (0x00-0xFF)
    @throws Exception on out-of-range value
    */
    public static native void putPin(final int base, final int port, final
        int pin, final int value) throws Exception;

    /**
    Set the value of an entire dio port.
    @param  base    Base address (0x100-0x3FF)
    @param  port    The port (0=A, 1=B, 2=C)
    @param  value   Value to write to the port (0x00-0xFF)
    @throws Exception on out-of-range value
    */
    public static native void putPort(final int base, final int port, final
        int value) throws Exception;

    /**
    Get the value at a pin.
    @param  base    Base address (0x100-0x3FF)
    @param  port    The port (0=A, 1=B, 2=C)
    @param  pin     The pin (0-7)
    @throws Exception on out-of-range value
    @return value at pin
    */
    public static native int getPin(final int base, final int port,
        final int pin) throws Exception;

    /**
    Get the value at a port.
    @param  base    Base address (0x100-0x3FF)
    @param  port    The port (0=A, 1=B, 2=C)
    @throws Exception on out-of-range value
    @return value at port
    */
    public static native int getPort(final int base, final int port) throws
        Exception;

    /**
    Get the ADC value.
    @param  base    Base address (0x100-0x3FF)
    @param  channel Channel (0-7)
    @param  polarity (0=unipolar, 1=bipolar)
    @param  range (0=5V, 1=10V)
    @throws Exception on out-of-range value
    @return value
    */
    public static native int getAdc(final int base, final int channel,
        final int polarity, final int range) throws Exception;

    /**
    Get the voltage.
    @param  base    Base address (0x100-0x3FF)
    @param  channel Channel (0-7)
    @param  polarity (0=unipolar, 1=bipolar)
    @param  range (0=5V, 1=10V)
    @throws Exception on out-of-range value
    @return value
    */
    public static native double getVoltage(final int base, final int channel,
        final int polarity, final int range) throws Exception;
}
