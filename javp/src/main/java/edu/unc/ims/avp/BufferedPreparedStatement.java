package edu.unc.ims.avp;

import java.util.HashMap;
import java.util.Map;
import java.util.Iterator;
import java.sql.Timestamp;
import java.sql.PreparedStatement;
import java.sql.Connection;
import java.sql.SQLException;
import java.io.InputStream;

/**
 * Use to prepare for a prepared statement.
 * This will rely on a connection that is externally provided and create
 * a prepared statement based on the values contained within.
 *
 * @author Tony Whipple
 */
public class BufferedPreparedStatement {

    private String mCommand;
    private HashMap<Integer, Object> mArguments = new HashMap<Integer, Object>();
    private class binStream {
        public InputStream mInStr;
        public int len;
    }

    /**
     * Constructor
     */
    public BufferedPreparedStatement(String cmd) {
        mCommand = cmd;
    }

    public void setTimestamp(int argNum, Timestamp val) {
        mArguments.put((Integer) argNum, val);
    }

    public void setInt(int argNum, int val) {
        mArguments.put((Integer) argNum, val);
    }

    public void setString(int argNum, String val) {
        mArguments.put((Integer) argNum, val);
    }

    public void setLong(int argNum, long val) {
        mArguments.put((Integer) argNum, val);
    }

    public void setDouble(int argNum, double val) {
        mArguments.put((Integer) argNum, val);
    }

    public void setBoolean(int argNum, boolean val) {
        mArguments.put((Integer) argNum, val);
    }

    public void setBinaryStream(int argNum, InputStream ins, int len) {
        binStream bs = new binStream();
        bs.mInStr = ins;
        bs.len = len;

        mArguments.put((Integer) argNum, bs);
    }

    public PreparedStatement createPreparedStatement(Connection con) throws SQLException {

        PreparedStatement ps = con.prepareStatement(mCommand);

        Iterator<Map.Entry<Integer, Object>> iter = mArguments.entrySet().iterator();
        while (iter.hasNext()) {
            Map.Entry<Integer, Object> entry = iter.next();
            Integer argNum = entry.getKey();
            Object val = entry.getValue();

            if (val instanceof Double) {
                ps.setDouble(argNum, (Double) val);
            } else if (val instanceof Integer) {
                ps.setInt(argNum, (Integer) val);
            } else if (val instanceof String) {
                ps.setString(argNum, (String) val);
            } else if (val instanceof Long) {
                ps.setLong(argNum, (Long) val);
            } else if (val instanceof Timestamp) {
                ps.setTimestamp(argNum, (Timestamp) val);
            } else if (val instanceof Boolean) {
                ps.setBoolean(argNum, (Boolean) val);
            } else if (val instanceof binStream) {
                ps.setBinaryStream(argNum, ((binStream) val).mInStr, ((binStream) val).len );

            } else {
                System.out.println("INTERNAL ERROR: type not handled in buffered prepared statement.");
            }
        }

        return ps;
    }

    @Override
    public String toString() {

        StringBuilder messageString = new StringBuilder(mCommand + ", ");

        Iterator<Map.Entry<Integer, Object>> iter = mArguments.entrySet().iterator();
        while (iter.hasNext()) {
            Map.Entry<Integer, Object> entry = iter.next();
            Integer argNum = entry.getKey();
            Object val = entry.getValue();

            if (val instanceof Double) {
                messageString.append(argNum).append(" ").append(val).append(", ");
            } else if (val instanceof Integer) {
                messageString.append(argNum).append(" ").append(val).append(", ");
            } else if (val instanceof String) {
                messageString.append(argNum).append(" ").append(val).append(", ");
            } else if (val instanceof Long) {
                messageString.append(argNum).append(" ").append(val).append(", ");
            } else if (val instanceof Timestamp) {
                messageString.append(argNum).append(" ").append(val.toString()).append(", ");
            } else if (val instanceof Boolean) {
                messageString.append(argNum).append(" ").append(val).append(", ");
            } else if (val instanceof binStream) {
                messageString.append(argNum).append(" ").append("Binary Stream of length ").append(
                        String.valueOf( ((binStream) val).len) ).append(val).append(", ");

            } else {
                System.out.println("INTERNAL ERROR: type not handled in buffered prepared statement.");
            }
        }

        return messageString.toString();
    }
}
