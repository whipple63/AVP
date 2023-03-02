package edu.unc.ims.instruments.ysi;

import java.util.ArrayList;
import java.util.Map;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Arrays;
import edu.unc.ims.avp.Logger;
import edu.unc.ims.avp.Logger.LogLevel;

/**
Data received from the YSI Sonde.
*/
public class Sonde6Data {
    private final static Map<String, ElementDesc> mParaIdToDesc = initializeMap();
    private static List<ElementDesc> mAvailableDataElements = null;

    private Map<String, DataElement> mPrettyIdToValue = null;

    public static class ElementDesc {
        public String mId;
        public String mUnits;
        public String mShortName;
        public ElementDesc() {
        }
        public ElementDesc(String id, String shortName, String units) {
            mId = id;
            mUnits = units;
            mShortName = shortName;
        }
        public String toString() {
            return "ElementDesc:\nid="+mId+", name="+mShortName+", units="+mUnits;
        }
    }

    public class DataElement extends ElementDesc {
        String mValue;
        DataElement(String id, String shortName, String units, String value) {
            super(id, shortName, units);
            mValue = value;
        }
        public String toString() {
            return super.toString() + ", value=" + mValue;
        }
    }


    public boolean mConstructorSuccess = false; // flag if we finish the constructor
    /**
    New data instance.
    This constructor stores the data values along with a mapped id, description
    and units taken from an internal mapping.
    @param    identifiers   List of integers retrieved via the 'para' command,
        used to parse the fields correctly.
    @param    rawLine space-separated fields of data values.
    */
    public Sonde6Data(final List<String> identifiers, final String rawLine) {
        // Parse the data values into an array
        List<String> fields = Arrays.asList(rawLine.split("[\\s]+"));
        
        // Make sure that all fields except the first two (Date and time)
        // can be parsed as double (in case of bad data transmission)
        for (int i=2; i<fields.size();i++) {
            try {
                Double.parseDouble(fields.get(i));
            } catch (java.lang.NumberFormatException fe) {
                Logger.getLogger().log("NumberFormatException: "+fields.get(i)+
                        " within line: " + rawLine,
                        "Sonde6Data", LogLevel.WARN);
                return;
            }
        }

        // Make sure that there are the same number of fields in the rawLine as there are identifiers
        if ( identifiers.size() != fields.size() ) {
            Logger.getLogger().log("Raw sonde data not expected size: "+rawLine, "Sonde6Data", LogLevel.DEBUG);
        } else {
            // Step through each identifier received from the Sonde and map 
            mPrettyIdToValue = new HashMap<String, DataElement>();
            for(int i=0;i<identifiers.size();i++) {
                String paraId = identifiers.get(i);
                ElementDesc e = mParaIdToDesc.get(paraId);
                String prettyId = e.mShortName;
                String value = fields.get(i);
                DataElement de = new DataElement(e.mId, e.mShortName, e.mUnits, value);
                mPrettyIdToValue.put(prettyId, de);
            }
            mConstructorSuccess = true;
        }
    }

    public static List<String> mapParaIdsToPrettyIds(final List<String> paraIds)
        throws Exception {
        if(mAvailableDataElements == null) {
            // This is the first time we've been called.  Setup the table
            // of data elements available from the connected sonde.
            mAvailableDataElements = new ArrayList<ElementDesc>();
        }
        List<String> result = new ArrayList<String>();
        Iterator<String> i = paraIds.iterator();
        while (i.hasNext()) {
            String paraId = i.next();

            if(mParaIdToDesc.containsKey(paraId)) {
                ElementDesc e = mParaIdToDesc.get(paraId);
                result.add(e.mShortName);
                mAvailableDataElements.add(e);
            } else {
                Logger.getLogger().log("Requested field id (" + paraId + ") not in internal map!",
                    "Sonde6Data",  LogLevel.DEBUG);
            }
        }
        return result;
    }

    /**
     * This will return null until mapParaIdsToPrettyIds() has been called,
     * typically by the Sonde after a para command
     * @return available data elements
     */
    public static List<ElementDesc> getAvailableDataElements() {
        return mAvailableDataElements;
    }

    /*
     * is is the mapped id, not the raw integer id
     */
    public final String getDescription(String id) {
        return mPrettyIdToValue.get(id).mUnits;
    }

    public String get(String id) {
        if(mPrettyIdToValue.containsKey(id)) {
            return mPrettyIdToValue.get(id).mValue;
        } else {
            return null;
        }
    }

    public double getDouble(String id) {
        if(mPrettyIdToValue.containsKey(id)) {
            return Double.parseDouble(mPrettyIdToValue.get(id).mValue);
        } else {
            return Double.NaN;
        }
    }

    public String toString() {
        StringBuffer sb = new StringBuffer(128);
        Iterator<String> i = mPrettyIdToValue.keySet().iterator();
        while(i.hasNext()) {
            String key = i.next();
            DataElement d = mPrettyIdToValue.get(key);
            sb.append(d.toString());
            if(i.hasNext()) {
                sb.append(", ");
            }
        }
        return sb.toString();
    }
    /**
    Initializes the static map.
    These values are in Appendix N of the YSI 6 series user  manual
    @return initialized map.
    */
    private final static Map<String, ElementDesc> initializeMap() {
        Map<String, ElementDesc> m = new HashMap<String, ElementDesc>();
        m.put("51" , new ElementDesc("51",  "date_dmy", "d/m/y"));
        m.put("52" , new ElementDesc("52",  "date_mdy", "m/d/y"));
        m.put("53" , new ElementDesc("53",  "date_ymd", "y/m/d"));
        m.put("153", new ElementDesc("153", "date_", "n/a"));
        m.put("54" , new ElementDesc("54",  "time_hms", "hh:mm:ss"));
        m.put("1"  , new ElementDesc("1",   "temp_C", "C"));
        m.put("2"  , new ElementDesc("2",   "temp_F", "F"));
        m.put("3"  , new ElementDesc("3",   "temp_K", "K"));
        m.put("4"  , new ElementDesc("4",   "cond_mScm", "mS/cm"));
        m.put("5"  , new ElementDesc("5",   "cond_uScm", "uS/cm"));
        m.put("6"  , new ElementDesc("6",   "spcond_mScm", "mS/cm"));
        m.put("7"  , new ElementDesc("7",   "spcond_uScm", "uS/cm"));
        m.put("8"  , new ElementDesc("8",   "resist_KOhmcm", "KOhm*cm"));
        m.put("9"  , new ElementDesc("9",   "resist_MOhmcm", "MOhm*cm"));
        m.put("94" , new ElementDesc("94",  "resist_Ohmcm", "Ohm*cm"));
        m.put("10" , new ElementDesc("10",  "tds_gL", "g/L"));
        m.put("95" , new ElementDesc("95",  "tds_KgL", "Kg/L"));
        m.put("12" , new ElementDesc("12",  "sal_ppt", "ppt"));
        m.put("14" , new ElementDesc("14",  "dosat_pct", "%"));
        m.put("200", new ElementDesc("200", "dosat_pctlocal", "%Local"));
        m.put("15" , new ElementDesc("15",  "do_mgL", "mg/L"));
        m.put("96" , new ElementDesc("96",  "dochrg", "n/a"));
        m.put("211", new ElementDesc("211", "odosat_pct", "%"));
        m.put("214", new ElementDesc("214", "odosat_pctlocal", "%Local"));
        m.put("212", new ElementDesc("212", "odo_mgL", "mg/L"));
        m.put("209", new ElementDesc("209", "c12_mgL", "mg/L"));
        m.put("210", new ElementDesc("210", "cl2chrg", "n/a"));
        m.put("20" , new ElementDesc("20",  "press_psia", "psia"));
        m.put("104", new ElementDesc("104", "press_psir", "psir"));
        m.put("21" , new ElementDesc("21",  "press_psig", "psig"));
        m.put("111", new ElementDesc("111", "press_psi", "psi"));
        m.put("22" , new ElementDesc("22",  "depth_m", "meters"));
        m.put("23" , new ElementDesc("23",  "depth_f", "feet"));
        m.put("118", new ElementDesc("118", "flow_ft3sec", "ft3/sec"));
        m.put("166", new ElementDesc("166", "flow_ft3min", "ft3/min"));
        m.put("167", new ElementDesc("167", "flow_ft3hour", "ft3/hour"));
        m.put("168", new ElementDesc("168", "flow_ft3day", "ft3/day"));
        m.put("164", new ElementDesc("164", "flow_galsec", "gal/sec"));
        m.put("119", new ElementDesc("119", "flow_galmin", "gal/min"));
        m.put("165", new ElementDesc("165", "flow_galhour", "gal/hour"));
        m.put("120", new ElementDesc("120", "flow_Mgalday", "Mgal/day"));
        m.put("121", new ElementDesc("121", "flow_m3sec", "m3/sec"));
        m.put("169", new ElementDesc("169", "flow_m3min", "m3/min"));
        m.put("170", new ElementDesc("170", "flow_m3hour", "m3/hour"));
        m.put("171", new ElementDesc("171", "flow_m3day", "m3/day"));
        m.put("122", new ElementDesc("122", "flow_Ls", "L/s"));
        m.put("172", new ElementDesc("172", "flow_AFday", "AF/day"));
        m.put("123", new ElementDesc("123", "volume_ft3", "ft3"));
        m.put("124", new ElementDesc("124", "volume_gal", "gal"));
        m.put("173", new ElementDesc("173", "volume_Mgal", "Mgal"));
        m.put("125", new ElementDesc("125", "volume_m3", "m3"));
        m.put("126", new ElementDesc("126", "volume_L", "L"));
        m.put("174", new ElementDesc("174", "volume_acreft", "acre*ft"));
        m.put("18" , new ElementDesc("18",  "ph", "n/a"));
        m.put("17" , new ElementDesc("17",  "ph_mV", "mV"));
        m.put("19" , new ElementDesc("19",  "orp_mV", "mV"));
        m.put("48" , new ElementDesc("48",  "nh4_NmgL", "N mg/L"));
        m.put("108", new ElementDesc("108", "nh4_NmV", "N mV"));
        m.put("47" , new ElementDesc("47",  "nh3_NmgL", "N mg/L"));
        m.put("106", new ElementDesc("106", "no3_NmgL", "N mg/L"));
        m.put("101", new ElementDesc("101", "no3_NmV", "N mV"));
        m.put("112", new ElementDesc("112", "cl_mgL", "mg/L"));
        m.put("145", new ElementDesc("145", "cl_mV", "mV"));
        m.put("201", new ElementDesc("201", "par1", "n/a"));
        m.put("202", new ElementDesc("202", "par2", "n/a"));
        m.put("37" , new ElementDesc("37",  "turbid_NTU", "NTU"));
        m.put("203", new ElementDesc("203", "turbidPl_NTU", "NTU"));
        m.put("193", new ElementDesc("193", "chl_ugL", "ug/L"));
        m.put("194", new ElementDesc("194", "chl_RFU", "RFU"));
        m.put("204", new ElementDesc("204", "rhodamine_ugL", "ug/L"));
        m.put("215", new ElementDesc("215", "bga_pc_cellsmL", "cells/mL"));
        m.put("216", new ElementDesc("216", "bga_pc_RFU", "RFU"));
        m.put("217", new ElementDesc("217", "bga_pe_cellsmL", "cells/mL"));
        m.put("218", new ElementDesc("218", "bga_pe_RFU", "RFU"));
        m.put("98" , new ElementDesc("98",  "gnd_Hz", "Hz"));
        m.put("99" , new ElementDesc("99",  "scale_Hz", "Hz"));
        m.put("100", new ElementDesc("100", "prescmp", "n/a"));
        m.put("32" , new ElementDesc("32",  "density_kgm3", "kg/m3"));
        m.put("28" , new ElementDesc("28",  "battery_V", "volts"));
        return m;
    }
}
