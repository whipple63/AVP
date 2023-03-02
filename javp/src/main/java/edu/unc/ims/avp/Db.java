package edu.unc.ims.avp;

import java.util.Properties;
import java.util.Queue;
import java.util.LinkedList;
import edu.unc.ims.avp.Logger.LogLevel;
import java.sql.PreparedStatement;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.SQLException;

/**
 * Maintain the postgresql database connection.
 */
public class Db {

    private Connection mConn;   // The SQL database connection
    public final Connection getConnection() { return mConn; }
    private String mUrl;
    private Properties mP;
    private Logger mLogger;
    private String mTablePrefix;
    public final String getTablePrefix() { return mTablePrefix; }
    
    // A queue for statement in case db connection goes down
    Queue<BufferedPreparedStatement> mPsQueue = new LinkedList<BufferedPreparedStatement>();

    
    /**
     * New Database connection.
     * 
     * @param  p   Properties.
     * @throws Exception on error
     */
    public Db(final Properties p) throws Exception {
        try {
            mP = p; // save the properties
            mLogger = Logger.getLogger();

            // Create a new instance of the postgres driver class
            Class.forName( p.getProperty("db_driver", "org.postgresql.Driver")).newInstance();

            // build the url to the database
            mUrl = p.getProperty("db_url_prefix", "jdbc:postgresql://") + p.getProperty("db_host",
                "localhost") + ":" + Integer.parseInt(p.getProperty("db_port", "5432")) + "/" + 
                    p.getProperty("db_name", "avp");

            mLogger.log("Connecting to Database \"" + mUrl + "\"", "Db",  LogLevel.DEBUG);
            mConn = DriverManager.getConnection(mUrl,
                p.getProperty("db_username", "postgres"),
                p.getProperty("db_password", ""));
            mLogger.log("Connected to Database \"" + mUrl + "\"", "Db", LogLevel.DEBUG);
            
            mTablePrefix = p.getProperty("db_table_prefix", "avp5");

        } catch (Exception ex) {
            mLogger.log(ex.toString(), "Db", LogLevel.FATAL);
            throw ex;
        }
    }

    
    /**
     * Tests Db connectivity, attempts to maintain connection
     * and buffers db updates if the connection is down.
     */
    public synchronized void bufferedExecuteUpdate(BufferedPreparedStatement bPS) throws SQLException {
        try {
            mPsQueue.add(bPS);   // add this to the buffer
            // Try to execute all buffered statements
            while (mPsQueue.peek() != null) { // the queue is not empty
//                System.out.println("Q Size: "+((Integer) mPsQueue.size()).toString());
                // Create a prepared statement from the buffere info
                PreparedStatement ps;
                ps = mPsQueue.peek().createPreparedStatement(mConn);
//                System.out.println("Sending: "+mPsQueue.peek().toString());
                ps.executeUpdate();    // if this throws exception it will remain in queue
                ps.close();
                mPsQueue.remove();
            }
        } catch (SQLException e) {
            // If there was an exception related to the db connection,
            // try to re-establish the connection and
            // try again.  If there is another exception remove the statement from
            // the buffer, since it may never clear.
            System.out.println("Caught SQLException: "+e.getMessage());
            e.printStackTrace();
            if (e.getMessage().contains("I/O error") || e.getMessage().contains("statement has been closed")) {
                try {
                    mConn = DriverManager.getConnection(mUrl,
                        mP.getProperty("db_username", "postgres"),
                        mP.getProperty("db_password", ""));
                    System.out.println("Database connection re-established.  Emptying queue.");
                    while (mPsQueue.peek() != null) { // the queue is not empty
                        // Create a prepared statement from the buffere info
                        PreparedStatement ps;
                        ps = mPsQueue.peek().createPreparedStatement(mConn);
                        ps.executeUpdate();    // if this throws exception it will remain in queue
                        ps.close();
                        mPsQueue.remove();
                    }
                } catch (Exception ee) {
//                    mLogger.setDatabase(null, getTablePrefix());    // so following call won't recurse!
//                    mLogger.log("Unable to log to database.  Will try later.", "Db", LogLevel.WARN);
                    System.out.println(" ----- Unable to log to database.  Will try later. -----");
//                    System.out.println("Caught SQLException: "+e.getMessage());
//                    e.printStackTrace();
                }
            } else {
                mPsQueue.remove();  // remove statement that caused unhandled exception
                throw(e);   // Not the one(s) we're looking for, so throw it on.
            }
        }
        
    }


    /**
    Shut down the JDBC connection.
    */
    public final void shutdown() {
        try {
            mLogger.log("Shutting down the connection", "Db", LogLevel.FATAL);
            mConn.close();
        } catch (SQLException e) {
            mLogger.log(e.toString(), "Db", LogLevel.ERROR);
        }
    }

}
