package edu.unc.ims.instruments.wind;

import java.util.ArrayList;
import java.util.Arrays;

/**
Data received from the wind instrument.
*/
public class WindData {
    private double mWindSpeed;      // Wind speed (m/s)
    private double mWindDir;        // Wind direction (degrees), corrected if compass present
    private int mVin1;              // VIN1 voltage input (0 to 1000mV input = 0 to 4000), if available
    private int mVin2;              // VIN2 voltage input (0 to 1000mV input = 0 to 4000), if available
    private int mVin3;              // VIN3 voltage input (0 to 5000mV input = 0 to 4000), if available
    private int mVin4;              // VIN4 voltage input (0 to 1000mV input = 0 to 4000) or Tipping Bucket TIP COUNT (0-9999).
    private double mCompassDir;     // Compass direction measurement (degrees)
    private double mWindDirUncorrected; // Wind direction (degrees), uncorrected by compass, if available
    private double mAirTemp;        // air temperature, if available
    private double mAirPressure;    // barometric pressure, if available
    private long mTimestamp;

    
    /**
     * New data instance given a line as read from the instrument.
     * 
     * @param    rawLine 8 space-separated fields
     * @throws Exception on error
     */
    public WindData(final String rawLine) throws NumberFormatException, InvalidInputException {
        
        // We will decide if the data come from an young32500, or an airmar NMEA stream
        // based on the first character.
        if (rawLine.startsWith("$")) {  // NMEA string is MDA string with heading appended on end
                                        // The code in this 'if' section is being replaced and can be removed
                                        // once the string[] constructor is working.
            String[] fields = rawLine.split(",");
            
            // Check for empty fields and set them to NaN
            for(int i = 0; i < fields.length; i++) {
                if (fields[i].isEmpty()) { fields[i] = "NaN"; }
            }
            
            mTimestamp = System.currentTimeMillis();
            mWindSpeed = Double.valueOf(fields[19]);
            mWindDir = Double.valueOf(fields[15]);
            mVin1 = -99;
            mVin2 = -99;
            mVin3 = -99;
            mVin4 = -99;
            mCompassDir = Double.valueOf(fields[21]);
            mWindDirUncorrected = Double.NaN;
            mAirTemp = Double.valueOf(fields[5]);
            mAirPressure = Double.valueOf(fields[3]);
            
//            System.out.println(toString());
        } else {

            String [] xfields = rawLine.split(" "); // separate the raw data into fields

            if (xfields.length != 8) {
                throw new InvalidInputException("We expect 8 fields, only got " + xfields.length);
            }

            String [] fields = new String[xfields.length];
            for(int i = 0; i < xfields.length; i++) {
                fields[i] = removeLeadingZeros(xfields[i]);
            }

            // assumes 05106 wind sensor.  Calculate the wind speed from counts.
            mTimestamp = System.currentTimeMillis();
            mWindSpeed = Double.parseDouble(fields[0]) * 0.04903;
            mWindDir = Double.parseDouble(fields[1]) / 10.0;
            mVin1 = Integer.parseInt(fields[2]);
            mVin2 = Integer.parseInt(fields[3]);
            mVin3 = Integer.parseInt(fields[4]);
            mVin4 = Integer.parseInt(fields[5]);
            mCompassDir = Double.parseDouble(fields[6]) / 10.0;
            mWindDirUncorrected = Double.parseDouble(fields[7]) / 10.0;
            mAirTemp = Double.NaN;         // mark as non-existent
            mAirPressure = Double.NaN;
        }
    }

    /**
     * New data instance given a line as read from the instrument.
     * 
     * @param    rawLine 8 space-separated fields
     * @throws Exception on error
     */
    public WindData(final String[] rawLines) throws NumberFormatException, InvalidInputException {  
            ArrayList<String> fields = new ArrayList<String>();
            fields.addAll( Arrays.asList(rawLines[0].split(",")) );
            fields.addAll( Arrays.asList(rawLines[1].split(",")) );
            fields.addAll( Arrays.asList(rawLines[2].split(",")) );
            
            // Check for empty fields and set them to NaN
            for(int i = 0; i < fields.size(); i++) {
                if (fields.get(i).isEmpty()) { fields.set(i,"NaN"); }
            }
            
            mTimestamp = System.currentTimeMillis();
            mWindSpeed = Double.valueOf(fields.get(13));
            mWindDir = Double.valueOf(fields.get(7));
            mVin1 = -99;
            mVin2 = -99;
            mVin3 = -99;
            mVin4 = -99;
            mCompassDir = Double.valueOf(fields.get(1));
            mWindDirUncorrected = Double.NaN;
            mAirTemp = Double.valueOf(fields.get(20));
            mAirPressure = Double.valueOf(fields.get(18));
            
            System.out.println(toString());
    }
    
   
    public static String removeLeadingZeros(String s) {
        StringBuilder sb = new StringBuilder(s.length());
        char lastC = 'x';
        for(int i = 0;i < s.length();i++) {
            sb.append(s.charAt(i));
            if((i+1) == s.length()) {
                break;
            }
            if((s.charAt(i) == '0') && (lastC == '0')) {
                continue;
            }
            lastC = s.charAt(i);
        }
        return sb.toString();
    }
    
    
    /**
    Get wind speed.
    Wind speed (m/s)
    @return wind speed.
    */
    public final double getWindSpeed() {
        return mWindSpeed;
    }

    /**
    Get wind direction.
    Wind direction (degrees), corrected if compass present.
    @return wind direction (corrected).
    */
    public final double getWindDirection() {
        return mWindDir;
    }

    /**
    Get VIN1.
    VIN1 voltage input (0 to 1000mV input = 0 to 4000).
    @return VIN1;
    */
    public final int getVin1() {
        return mVin1;
    }

    /**
    Get VIN2.
    VIN1 voltage input (0 to 1000mV input = 0 to 4000).
    @return VIN2;
    */
    public final int getVin2() {
        return mVin2;
    }

    /**
    Get VIN3.
    VIN3 voltage input (0 to 5000mV input = 0 to 4000).
    @return VIN3;
    */
    public final int getVin3() {
        return mVin3;
    }

    /**
    Get VIN4.
    VIN3 voltage input (0 to 5000mV input = 0 to 4000).
    @return VIN4;
    */
    public final int getVin4() {
        return mVin4;
    }

    /**
     * Get timestamp.
     * @return time sample was acquired
     */
    public final long getTimestamp() {
        return mTimestamp;
    }

    /**
    Get compass direction.
    Compass direction measurement (degrees).
    @return compass direction.
    */
    public final double getCompassDirection() {
        return mCompassDir;
    }

    /**
    Get uncorrected compass direction.
    Wind direction (degrees), uncorrected by compass.
    @return uncorrected compass direction.
    */
    public final double getUncorrectedWindDirection() {
        return mWindDirUncorrected;
    }

    /**
    Get air temperature.
    Air temperature in degrees C.
    @return air temp.
    */
    public final double getAirTemp() {
        return mAirTemp;
    }

    /**
    Get pressure.
    Barometric pressure in Bar.
    @return barometric pressure.
    */
    public final double getAirPressure() {
        return mAirPressure;
    }

    /**
    Get string representation.
    @return string.
    */
    @Override
    public final String toString() {
        StringBuilder sb = new StringBuilder();
        sb.append("Timestamp:\t\t\t").append(mTimestamp).append("\n");
        sb.append("Wind Speed:\t\t\t").append(mWindSpeed).append("\n");
        sb.append("Wind Direction (corrected):\t").append(mWindDir).append("\n");
        sb.append("Wind Direction (uncorrected):\t").append(mWindDirUncorrected).append("\n");
        sb.append("Compass Direction:\t\t").append(mCompassDir).append("\n");
        sb.append("VIN1:\t\t\t\t").append(mVin1).append("\n");
        sb.append("VIN2:\t\t\t\t").append(mVin2).append("\n");
        sb.append("VIN3:\t\t\t\t").append(mVin3).append("\n");
        sb.append("VIN4:\t\t\t\t").append(mVin4).append("\n");
        sb.append("Air Temperature:\t\t").append(mAirTemp).append("\n");
        sb.append("Air Pressure:\t\t\t").append(mAirPressure);
        return sb.toString();
    }
}
