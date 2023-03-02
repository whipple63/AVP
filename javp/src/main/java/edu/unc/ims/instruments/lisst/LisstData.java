package edu.unc.ims.instruments.lisst;

/**
 * Holds most recent data from the LISST
 *
 * @author Tony Whipple
 */
public class LisstData {

    private Long mStatusTimestamp;    /** computer time of last status */
    private Boolean mSeawaterPump;    /** Is seawater pump on? */
    private Boolean mCleanWaterFlush; /** Is clean water flush on? */
    private Boolean mDataCollection;  /** Is data collection going on? */
    private Integer mCleanWaterLevel; /** Clean water tank percent full */
    private String  mSerialNumber;    /** Instrument serial number */
    private String  mFirmwareVersion; /** Instrument firmware version */
    private Integer mMeasPerAvg;      /** Measurements per average */
    private String  mDataFileName;    /** Most recent data file name */
    private Boolean mDataFileTransferred;  /** true if data file has been copied */
    private Boolean mZeroFile;        /** Is this a zero file */

    /** access routines */
    public final Long getStatusTimestamp() {return mStatusTimestamp;}
    public final Boolean getSeawaterPump()    {return mSeawaterPump;}
    public final Boolean getCleanWaterFlush() {return mCleanWaterFlush;}
    public final Boolean getDataCollection()  {return mDataCollection;}
    public final Integer getCleanWaterLevel() {return mCleanWaterLevel;}
    public final String  getSerialNumber()    {return mSerialNumber;}
    public final String  getFirmwareVersion() {return mFirmwareVersion;}
    public final Integer getMeasPerAvg()      {return mMeasPerAvg;}
    public final String  getDataFileName()    {return mDataFileName;}
    public final Boolean getDataFileTransferred() {return mDataFileTransferred;}
    public final Boolean getZeroFile()        {return mZeroFile;}

    public void setStatusTimeStamp(Long t) { mStatusTimestamp = t; }
    public void setSeawaterPump(Boolean b)    {mSeawaterPump=b;}
    public void setCleanWaterFlush(Boolean b) {mCleanWaterFlush=b;}
    public void setDataCollection(Boolean b)  {mDataCollection=b;}
    public void setCleanWaterLevel(Integer i) {mCleanWaterLevel=i;}
    public void setSerialNumber(String s)     {mSerialNumber=s;}
    public void setFirmwareVersion(String s)  {mFirmwareVersion=s;}
    public void setMeasPerAvg(Integer i)      {mMeasPerAvg=i;}
    public void setDataFileName(String s)     {mDataFileName=s;}
    public void setDataFileTransferred(Boolean b) {mDataFileTransferred=b;}
    public void setZeroFile(Boolean b)        {mZeroFile=b;}

    /** constructor */
    public LisstData() {
        mSeawaterPump = false;
        mCleanWaterFlush = false;
        mDataCollection = false;
        mDataFileTransferred = false;
        mZeroFile = false;

        mStatusTimestamp = null;
        mCleanWaterLevel = null;
        mSerialNumber = null;
        mFirmwareVersion = null;
        mMeasPerAvg = null;
        mDataFileName = null;
    }

    /**
    Get string representation.
    @return string.
    */
    @Override
    public final String toString() {
        StringBuilder sb = new StringBuilder();
        if (mSerialNumber != null) {
            sb.append("LISST Serial Number:\t").append(mSerialNumber).append("\n");
            sb.append("LISST Firmware:\t").append(mFirmwareVersion).append("\n");
            sb.append("Clean Water Tank Level:\t").append(mCleanWaterLevel.toString()).append("\n");
            sb.append("Seawater pumping?:\t").append(mSeawaterPump.toString()).append("\n");
            sb.append("Clean Water Flush Operating?:\t").append(mCleanWaterFlush.toString()).append("\n");
            sb.append("Data Collection in progress?:\t").append(mDataCollection.toString()).append("\n");
            sb.append("Most recent data file name:\t").append(mDataFileName).append("\n");
            sb.append("Data file transferred?:\t").append(mDataFileTransferred.toString()).append("\n");
            sb.append("Measurements per average:\t").append(mMeasPerAvg.toString()).append("\n");
            sb.append("Zero file?:\t").append(mZeroFile.toString()).append("\n");
        } else {
            sb.append("Values have not been set");
        }
        return sb.toString();
    }
}
