package edu.unc.ims.instruments.isco;

/**
 * Holds most recent data from the ISCO
 *
 * @author Tony Whipple
 */
public class IscoData {

    private String mModel;          /** model of ISCO */
    private String mID;             /** ID number of ISCO */
    private String mHardwareRevision;
    private String mSoftwareRevision;

    private Long mStatusTimestamp;  /** computer time of last status */
    private Double mIscoStatusTime; /** ISCO time of last status */
    private Integer mIscoStatus;    /** ISCO status number */
    private Double mIscoSampleTime; /** ISCO time of last sample */
    private Integer mBottleNum;     /** Bottle number of last sample */
    private Integer mSampleVolume;  /** Volume of last sample in mL */
    private Integer mSampleStatus;  /** Status of last sample */

    /** access routines */
    public final String getModel() {return mModel;}
    public final String getID() {return mID;}
    public final String getHardwareRevision() {return mHardwareRevision;}
    public final String getSoftwareRevision() {return mSoftwareRevision;}
    public final Long getStatusTimestamp() {return mStatusTimestamp;}
    public final Double getIscoStatusTime() {return mIscoStatusTime;}
    public final Integer getIscoStatus() {return mIscoStatus;}
    public final Double getIscoSampleTime() {return mIscoSampleTime;}
    public final Integer getBottleNum() {return mBottleNum;}
    public final Integer getSampleVolume() {return mSampleVolume;}
    public final Integer getSampleStatus() {return mSampleStatus;}

    public void setModel(String m) { mModel = m; }
    public void setID(String id) { mID = id; }
    public void setHardwareRevision(String h) { mHardwareRevision = h; }
    public void setSoftwareRevision(String s) { mSoftwareRevision = s; }
    public void setStatusTimeStamp(Long t) { mStatusTimestamp = t; }
    public void setIscoStatusTime(Double t) { mIscoStatusTime = t; }
    public void setIscoStatus(Integer s) { mIscoStatus = s; }
    public void setIscoSampleTime(Double t) { mIscoSampleTime = t; }
    public void setBottleNum(Integer b) { mBottleNum = b; }
    public void setSampleVolume(Integer v) { mSampleVolume = v; }
    public void setSampleStatus(Integer s) { mSampleStatus = s; }

    /** constructor */
    public IscoData() {
        // Initialize everything to null
        mModel = null;
        mID = null;
        mHardwareRevision = null;
        mSoftwareRevision = null;

        mStatusTimestamp = null;
        mIscoStatusTime = null;
        mIscoStatus = null;
        mIscoSampleTime = null;
        mBottleNum = null;
        mSampleVolume = null;
        mSampleStatus = null;
    } // Isco Data

    /**
    Get string representation.
    @return string.
    */
    @Override
    public final String toString() {
        StringBuilder sb = new StringBuilder();
        if (mIscoStatus != null) {
            sb.append("ISCO Model:\t").append(mModel).append("\n");
            sb.append("ID:\t").append(mID).append("\n");
            sb.append("Hardware Revision:\t").append(mHardwareRevision).append("\n");
            sb.append("Software Revision:\t").append(mSoftwareRevision).append("\n");
            sb.append("Status time:\t").append(mStatusTimestamp.toString()).append("\n");
            sb.append("ISCO Status Time:\t").append(mIscoStatusTime.toString()).append("\n");
            sb.append("ISCO Status:\t").append(mIscoStatus.toString()).append("\n");
            sb.append("Last Sample Time:\t").append(mIscoSampleTime.toString()).append("\n");
            sb.append("Last Bottle Number:\t").append(mBottleNum.toString()).append("\n");
            sb.append("Last Bottle Volume:\t").append(mSampleVolume.toString()).append("\n");
            sb.append("Last Sample Status:\t").append(mSampleStatus.toString()).append("\n");
        } else {
            sb.append("Values have not been set");
        }
        return sb.toString();
    }
}
