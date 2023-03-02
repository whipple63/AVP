package edu.unc.ims.avp.gui;

/**
Compass data model.
*/
public class CompassModel {
    /**
    The compass reading.
    */
    private double mValue = 0.0;

    /**
    The compass title.
    */
    private String mTitle = "Compass";

    /**
    Get the current compass reading.
    @return the reading in degrees.
    */
    public final double getValue() {
        return mValue;
    }

    /**
    Get the current compass title.
    @return the title
    */
    public final String getTitle() {
        return mTitle;
    }

    /**
    Set the current compass reading.
    @param  value   reading.
    */
    public final void setValue(final double value) {
        mValue = value;
    }

    /**
    Set the current compass title.
    @param  title   title
    */
    public final void setTitle(final String title) {
        mTitle = title;
    }
}
