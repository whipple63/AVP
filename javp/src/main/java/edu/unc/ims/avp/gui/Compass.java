package edu.unc.ims.avp.gui;

import java.io.Serializable;
import javax.swing.JComponent;
import javax.swing.SwingConstants;
import javax.swing.UIManager;
import javax.swing.event.ChangeListener;
import javax.swing.event.ChangeEvent;
import java.awt.Dimension;
import java.awt.Color;

/**
Compass component.
*/
public class Compass extends JComponent implements SwingConstants {
    /**
    Change event.
    */
    private transient ChangeEvent changeEvent = null;

    /**
    Data model.
    */
    private CompassModel mModel;

    /**
    Change listener.
    */
    private final ChangeListener mChangeListener = createChangeListener();

    /**
    ID.
    */
    private static final String UI_CLASS_ID = "Compass";

    /**
    Create the model listener.
    @return model listener.
    */
    protected final ChangeListener createChangeListener() {
        return new ModelListener();
    }

    /**
    Constructor.
    @param  title   Title of compass
    */
    public Compass(final String title) {
        mModel = new CompassModel();
        mModel.setTitle(title);
        this.setPreferredSize(new Dimension(200, 200));
        this.setBackground(Color.red);
        updateUI();
    }

    /**
    Get the model.
    @return model
    */
    public final CompassModel getModel() {
        return mModel;
    }

    /**
    Get the current compass value.
    @return degrees
    */
    public final double getValue() {
        return mModel.getValue();
    }

    /**
    Set the current compass value.
    @param  v   degrees
    */
    public final void setValue(final double v) {
        mModel.setValue(v);
        revalidate();
        repaint();
    }

    /**
    Get the current compass title.
    @return title
    */
    public final String getTitle() {
        return mModel.getTitle();
    }

    /**
    Set the current compass title.
    @param  v   title
    */
    public final void setTitle(final String v) {
        mModel.setTitle(v);
        revalidate();
        repaint();
    }

    /**
    Set the UI.
    @param  ui  the ui
    */
    public final void setUI(final CompassUI ui) {
        super.setUI(ui);
    }

    /**
    Update the UI.
    */
    public final void updateUI() {
        if (UIManager.get(getUIClassID()) != null) {
            setUI((CompassUI) UIManager.getUI(this));
        } else {
            setUI(new BasicCompassUI(mModel));
        }
    }

    /**
    Get the UI.
    @return ui.
    */
    public final CompassUI getUI() {
        return (CompassUI) ui;
    }

    /**
    Notify listeners of state change.
    */
    protected final void fireStateChanged() {
        Object[] listeners = listenerList.getListenerList();
        for (int i = listeners.length - 2; i >= 0; i -= 2) {
            if (listeners[i] == ChangeListener.class) {
                if (changeEvent == null) {
                    changeEvent = new ChangeEvent(this);
                }
                ((ChangeListener) listeners[i + 1]).stateChanged(changeEvent);
            }
        }
    }

    /**
    Get id.
    @return id.
    */
    public final String getUIClassID() {
        return UI_CLASS_ID;
    }

    /**
    Model listener.
    */
    private class ModelListener implements ChangeListener, Serializable {
        /**
        State changed.
        @param  e   change event.
        */
        public void stateChanged(final ChangeEvent e) {
            fireStateChanged();
        }
    }
}
