package edu.unc.ims.avp;

import java.io.PrintWriter;
import java.io.File;
import java.util.Calendar;
import java.util.List;
import java.util.ArrayList;
import java.text.SimpleDateFormat;
import java.sql.Timestamp;
import java.sql.Statement;
import java.sql.ResultSet;

/**
Logger.
*/
public class Logger {

    private Db mDb = null;  // Database connection object
    private String mPrefix; // Database table prefix
    private PrintWriter mWriter;
    private static String mFilename = "-";
    private static Logger mLogger = null;

    private LogLevel mLevel = LogLevel.FATAL;   // The current level
    public final LogLevel getLevel() { return mLevel; }
    public enum LogLevel { DEBUG, INFO, WARN, ERROR, FATAL };   // Possible error levels

    private static final String LOG_DATE_FORMAT = "yyyy-MM-dd HH:mm:ss";    // Format string for log messages

    
    /**
     * Constructor.
     * @throws Exception on error
     */
    protected Logger() throws Exception {
        setLogFile("-");
    }

    
    /**
     * Set the database connection information.
     * 
     * @param db   Database connection information.
     * @param prefix   Our scheme requires a site-specific table prefix, e.g.
     *                 'avp5'.
     */
    public final void setDatabase(final Db db, final String prefix) {
        mDb = db;
        mPrefix = prefix;
    }

    
    /**
     * Set the name of a log file.
     * @param  filename    Name of file or "-" for stderr.
     */
    public final void setLogFile(final String filename) {
        mFilename = filename;
        if (!mFilename.equals("-")) {
            try {
                mWriter = new PrintWriter(new File(filename));
                return;
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
        // if the user wants or we failed to open given file, use stderr
        try {
            mWriter = new PrintWriter(System.err);
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    
    /**
     * Get logger instance.
     * @return logger instance.
     */
    public static Logger getLogger() {
        if (mLogger == null) {
            try {
                mLogger = new Logger();
                mLogger.setLogFile("-");
            } catch (Exception e) {
                e.printStackTrace();
            }
        }
        return mLogger;
    }

    
    /**
     * Sets the level of log messages.
     * 
     * <table border="1">
     * <tr><th>Level<th>Description
     * <tr><td>debug<td>Debug-level messages
     * <tr><td>info<td>Informational.
     * <tr><td>warn<td>Warning conditions.
     * <tr><td>error<td>Error conditions.
     * <tr><td>fatal<td>Fatal error, system unusable.
     * </table>
     * When a particular level is specified, messages from all other levels of
     * higher significance will be reported as well. E.g., when LogLevel info is
     * specified, then messages with log levels of info and debug will be logged.
     * posted.
     * 
     * @param  level   The new level.
     */
    public final void setLevel(final LogLevel level) {
        mLevel = level;
    }

    
    /**
     * Set the log level.
     * See setLevel(LogLevel) for details.
     * 
     * @param  level One of DEBUG, INFO, WARN, ERROR, FATAL.
     */
    public final void setLevel(final String level) {
        if (level.equalsIgnoreCase("DEBUG")) {
            setLevel(LogLevel.DEBUG);
        } else if (level.equalsIgnoreCase("INFO")) {
            setLevel(LogLevel.INFO);
        } else if (level.equalsIgnoreCase("WARN")) {
            setLevel(LogLevel.WARN);
        } else if (level.equalsIgnoreCase("ERROR")) {
            setLevel(LogLevel.ERROR);
        } else if (level.equalsIgnoreCase("FATAL")) {
            setLevel(LogLevel.FATAL);
        }
    }

    
    /**
     * Log a message.
     * If a database has been given with setDatabase(), all messages are logged to
     * it.
     * 
     * @param  s   msg.
     * @param  src Source of the message.
     * @param  level   the importance of the message.
     */
    public final void log(final String s, final String src, final LogLevel level) {
//System.out.println("message: "+s+" src: "+src+" LogLevel: "+level.toString());
        if((s == null) || (s.equals(""))) {
            return;
        }
        // We've had cases where the incoming s contains " characters, we must
        // escape those or jdbc is unhappy
        String msg = s.replace("\"", "'");
        /* also, UTF8-encoded databases don't like 0x00... */
        msg = msg.replace("\u0000", "(null)");
        Calendar cal = Calendar.getInstance();
        if (mDb != null) {
            Timestamp ts = new Timestamp(cal.getTimeInMillis());
            // We use one of two tables.  If DEBUG, use avpX_debug_log, all
            // others go in avpX_log.
            String table = mPrefix + "_log";
            String cmd = "";
            if (level == LogLevel.DEBUG) {
                table = mPrefix + "_debug_log";
                cmd = "insert into " + table + " (loc_code, source, time, message, comment, save) values(?, ?, ?, ?, ?, ?)";
            } else {
                cmd = "insert into " + table + " (loc_code, source, time, message, comment, save, level) values(?, ?, ?, ?, ?, ?, ?)";
            }
            try {
                BufferedPreparedStatement pstmt = new BufferedPreparedStatement(cmd);
//                PreparedStatement pstmt =
//                    mDb.getConnection().prepareStatement(cmd);
                pstmt.setString(1, mPrefix);
                if((src == null) || (src.equals(""))) {
                    pstmt.setString(2, "Unknown");
                } else {
                    pstmt.setString(2, src);
                }
                pstmt.setTimestamp(3, ts);
                pstmt.setString(4, msg);
                pstmt.setString(5, "");
                pstmt.setBoolean(6, true);
                if (level != LogLevel.DEBUG) {
                    pstmt.setInt(7, level.ordinal());
                }
                mDb.bufferedExecuteUpdate(pstmt);
//                pstmt.executeUpdate();
//                pstmt.close();
            } catch (Exception e) {
                e.printStackTrace();
            }
//        } else {
        } // for the moment I would like to see all messages
            /* We decided to log everything, but leaving this here in case
            we change our minds.  */
            //if (level.ordinal() <= mLevel.ordinal()) {
                SimpleDateFormat sdf = new SimpleDateFormat(LOG_DATE_FORMAT);
                String d = sdf.format(cal.getTime());
                mWriter.println("[" + d + "] [" + getLevelAsString(level) + "]"
                    + "[" + src + "] " + s);
                mWriter.flush();
            //}
//        }
    }

    
    /**
     * Get level as a string.
     * @param  l   Level.
     * @return level.
     */
    public final String getLevelAsString(final LogLevel l) {
        if (l == LogLevel.DEBUG) {
            return "DEBUG";
        } else if (l == LogLevel.INFO) {
            return "INFO";
        } else if (l == LogLevel.ERROR) {
            return "ERROR";
        } else if (l == LogLevel.WARN) {
            return "WARN";
        } else if (l == LogLevel.FATAL) {
            return "FATAL";
        }
        return "";
    }

    
    /**
     * Get all log messages.
     * Gets log messages from both the avpX_log and avpX_debug_log tables and
     * combines into a single list of messages.
     * @return All log messages.
     * @throws Exception on error.
     */
    public Object [][] getAllLogMessages() throws Exception {
        Object[][] logData = null;
        Object[][] data = getLogMessages(false);
        Object[][] debugData = getLogMessages(true);
        logData = new Object[data.length + debugData.length][6];
        System.arraycopy(data, 0, logData, 0, data.length);
        System.arraycopy(debugData, 0, logData, data.length, debugData.length);
        return logData;
    }

    
    /**
     * Get log messages.
     * @param  debug   If true, fetches messages from avpX_debug_log table,
     *     otherwise avpX_log table.  On debug, adds the level field to normalize
     *     against the standard log messages.
     */
    public Object [][] getLogMessages(boolean debug) throws Exception {
        String sel = "select * from " + mDb.getTablePrefix();
        if(debug) {
            sel += "_debug_log";
        } else {
            sel += "_log";
        }
        List<Object[]> results = new ArrayList<Object[]>();
        try {
            Statement stmt = mDb.getConnection().createStatement();
            ResultSet rs = stmt.executeQuery(sel);
            while (rs.next()) {
                Object[] x = new Object[6];
                x[0] = rs.getString("source");
                x[1] = rs.getTimestamp("time");
                x[2] = rs.getString("message");
                x[3] = rs.getString("comment");
                x[4] = rs.getBoolean("save");
                if(debug) {
                    x[5] = 0;
                } else {
                    x[5] = rs.getInt("level");
                }
                results.add(x);
            }
            stmt.close();
        } catch(Exception e) {
            System.err.println("SQLException: " + e.getMessage());
        }
        Object[][] o = new Object[results.size()][6];
        for(int i = 0;i < results.size(); i++) {
            o[i] = results.get(i);
        }
        return o;
    }
}
