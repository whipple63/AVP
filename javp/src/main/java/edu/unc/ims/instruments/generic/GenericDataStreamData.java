package edu.unc.ims.instruments.generic;

import java.util.*;

/**
 *
 * @author Tony
 */
public class GenericDataStreamData {
    Map<String, Object> mData = new HashMap<String, Object>();
    public Map getData() { return mData; }
    
    Map<String, String> mType = new HashMap<String, String>();
    public Map getType() { return mType; }
    

    /**
     * Constructor populates a hashmap with given names as keys.  Given types
     * and values will be assigned in the same order as the names.
     * 
     * @param col_names
     * @param col_types 
     * @param col_values
     */
    public GenericDataStreamData(String[] col_names, String[] col_types, String[] col_values)
            throws NumberFormatException {
       for (int i=0; i<col_names.length; i++) {
          if (col_types[i].toLowerCase().equals("string")) {
             mType.put(col_names[i], "string");
             mData.put(col_names[i], col_values[i]);
          }
          else if (col_types[i].toLowerCase().equals("int")) {
             mType.put(col_names[i], "int");
             mData.put(col_names[i], Integer.valueOf(col_values[i]));
          }
          else if (col_types[i].toLowerCase().equals("double")) {
             mType.put(col_names[i], "double");
             mData.put(col_names[i], Double.valueOf(col_values[i]));
          }
       }
    }

}
