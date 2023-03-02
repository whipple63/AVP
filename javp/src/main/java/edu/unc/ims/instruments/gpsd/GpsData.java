/*
 * To change this template, choose Tools | Templates
 * and open the template in the editor.
 */

package edu.unc.ims.instruments.gpsd;

/**
 *
 * @author Tony Whipple
 */
public class GpsData {
    /** The most recent string from gpsd */
    private String mJsonStr;

    public void update(String s) {
        mJsonStr = s;
    }

    public String get() {
        return mJsonStr;
    }

}

//
//TPV
//A TPV object is a time-position-velocity report. The "class" and "mode" fields will reliably be present. Others may be reported or not depending on the fix quality.
//
//Table 1. TPV object
//
//Name Always? Type Description
//class Yes string Fixed: "TPV"
//tag No string Type tag associated with this GPS sentence; from an NMEA device this is just the NMEA sentence type..
//device No string Name of originating device
//time No numeric Seconds since the Unix epoch, UTC. May have a fractional part of up to .01sec precision.
//ept No numeric Estimated timestamp error (%f, seconds, 95% confidence).
//lat No numeric Latitude in degrees: +/- signifies West/East
//lon No numeric Longitude in degrees: +/- signifies North/South.
//alt No numeric Altitude in meters.
//epx No numeric Longitude error estimate in meters, 95% confidence.
//epy No numeric Latitude error estimate in meters, 95% confidence.
//epv No numeric Estimated vertical error in meters, 95% confidence.
//track No numeric Course over ground, degrees from true north.
//speed No numeric Speed over ground, meters per second.
//climb No numeric Climb (positive) or sink (negative) rate, meters per second.
//epd No numeric Direction error estimate in degrees, 95% confifdence.
//eps No numeric Speed error estinmate in meters/sec, 95% confifdence.
//epc No numeric Climb/sink error estinmate in meters/sec, 95% confifdence.
//mode Yes numeric NMEA mode: %d, 0=no mode value yet seen, 1=no fix, 2=2D, 3=3D.
//
//
//
//When the C client library parses a response of this kind, it will assert validity bits in the top-level set member for each field actually received; see gps.h for bitmask names and values.
//
//Here's an example:
//
//{"class":"TPV","tag":"MID2","device":"/dev/pts/1",
//    "time":1118327688.280,"ept":0.005,
//    "lat":46.498293369,"lon":7.567411672,"alt":1343.127,
//    "eph":36.000,"epv":32.321,
//    "track":10.3788,"speed":0.091,"climb":-0.085,"mode":3}
//
//SKY
//A SKY object reports a sky view of the GPS satellite positions. If there is no GPS device available, or no skyview has been reported yet, only the "class" field will reliably be present.
//
//Table 2. SKY object
//
//Name Always? Type Description
//class Yes string Fixed: "SKY"
//tag No string Type tag associated with this GPS sentence; from an NMEA device this is just the NMEA sentence type..
//device No string Name of originating device
//time No numeric Seconds since the Unix epoch, UTC. May have a fractional part of up to .01sec precision.
//xdop No numeric Longitudinal dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get an error estimate.
//ydop No numeric Latitudinal dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get an error estimate.
//vdop No numeric Altitude dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get an error estimate.
//tdop No numeric Time dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get an error estimate.
//hdop No numeric Horizontal dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get a circular error estimate.
//pdop No numeric Spherical dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get an error estimate.
//gdop No numeric Hyperspherical dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get an error estimate.
//xdop No numeric Longitudinal dilution of precision, a dimensionsless factor which should be multiplied by a base UERE to get an error estimate.
//satellites Yes list List of satellite objects in skyview
//
//
//
//Many devices compute dilution of precision factors but do nit include them in their reports. Many that do report DOPs report only HDOP, two-dimensial circular error. gpsd always passes through whatever the device actually reports, then attempts to fill in other DOPs by calculating the appropriate determinants in a covariance matrix based on the satellite view. DOPs may be missing if some of these determinants are singular. It can even happen that the device reports an error estimate in meters when the correspoding DOP is unavailable; some devices use more sophisticated error modeling than the covariance calculation.
//
//The satellite list objects have the following elements:
//
//Table 3. Satellite object
//
//Name Always? Type Description
//PRN Yes numeric PRN ID of the satellite
//az Yes numeric Azimuth, degrees from true north.
//el Yes numeric Elevation in degrees.
//ss Yes numeric Signal strength in dB.
//used Yes boolean Used in current solution?
//
//
//
//Note that satellite objects do not have a "class" field.., as they are never shipped outside of a SKY object.
//
//When the C client library parses a SKY response, it will assert the SATELLITE_SET bit in the top-level set member.
//
//Here's an example:
//
//{"class":"SKY","tag":"MID2","device":"/dev/pts/1","time":1118327688.280
//    "xdop":1.55,"hdop":1.24,"pdop":1.99,
//    "satellites":[
//        {"PRN":23,"el":6,"az":84,"ss":0,"used":false},
//        {"PRN":28,"el":7,"az":160,"ss":0,"used":false},
//        {"PRN":8,"el":66,"az":189,"ss":44,"used":true},
//        {"PRN":29,"el":13,"az":273,"ss":0,"used":false},
//        {"PRN":10,"el":51,"az":304,"ss":29,"used":true},
//        {"PRN":4,"el":15,"az":199,"ss":36,"used":true},
//        {"PRN":2,"el":34,"az":241,"ss":43,"used":true},
//        {"PRN":27,"el":71,"az":76,"ss":43,"used":true}]}
//
