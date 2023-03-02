package edu.unc.ims.avp.dashboard;

import org.json.*;
import javax.swing.*;
import javax.swing.table.*;

public class ParamTableModel extends AbstractTableModel {
    private JSONObject mData = null;

    public void setData(JSONObject a) {
        mData = a;
        fireTableStructureChanged();
    }

    public JSONObject getData() {
        return mData;
    }

    public String getColumnName(int columnIndex) {
        if(columnIndex == 0) {
            return "Name";
        } else if(columnIndex == 1) {
            return "Value";
        } else {
            return "Units";
        }
    }

    public int getRowCount() {
        if(mData == null) {
            return 0;
        }
        try {
            // parameters has a list of JSONObjects, each a param
            if(!mData.has("result")) {
                return 0;
            }
            JSONObject result = mData.getJSONObject("result");
            if(result == null) {
                return 0;
            }
            String [] paramNames = JSONObject.getNames(result);
            return paramNames.length;
        } catch(Exception e) {
            e.printStackTrace();
        }
        return 0;
    }

    public int getColumnCount() {
        if(mData == null) {
            return 0;
        }
        return 3;
    }

    public Object getValueAt(int row, int column) {
        if(mData == null) {
            return null;
        }
        try {
            if(!mData.has("result")) {
                return null;
            }
            JSONObject result = mData.getJSONObject("result");
            if(result == null) {
                return null;
            }
            String [] paramNames = JSONObject.getNames(result);
            JSONObject o = mData.getJSONObject("result").getJSONObject(
                paramNames[row]);
            if(column==0) {
                return paramNames[row];
            } else if(column == 1) {
                if(o.has("value"))
                    return o.get("value");
                else return "";
            } else if(column == 2) {
                return o.get("units");
            }
        } catch(Exception e) {
            e.printStackTrace();
        }
        return null;
    }
}
