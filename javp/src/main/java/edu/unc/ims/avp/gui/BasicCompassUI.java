package edu.unc.ims.avp.gui;

import java.awt.Graphics;
import java.awt.Color;
import java.awt.Font;
import java.awt.FontMetrics;
import java.awt.Stroke;
import java.awt.BasicStroke;
import java.awt.Dimension;
import java.awt.Graphics2D;
import javax.swing.JComponent;
import java.awt.geom.Ellipse2D;
import java.awt.geom.Line2D;

/**
Compass UI.
*/
public class BasicCompassUI extends CompassUI {
    /**
    The model.
    */
    private CompassModel mModel;

    /**
    Create the UI.
    @param  m   The model
    */
    public BasicCompassUI(final CompassModel m) {
        mModel = m;
    }

    /**
    Paint.
    @param  g   Graphics.
    @param  c   Component.
    */
    public final void paint(final Graphics g, final JComponent c) {
        Graphics2D g2d = (Graphics2D) g;
        g2d.setBackground(c.getParent().getBackground());
        g2d.setColor(Color.black);
        Dimension d = c.getSize();
        g2d.clearRect(0, 0, d.width, d.height);

        // draw the outer circle
        g2d.setColor(new Color(210, 210, 210));
        int circleDiameter = d.width;
        if (d.width > d.height) {
            circleDiameter = d.height;
        }
        int center = circleDiameter / 2;
        Ellipse2D circle = new Ellipse2D.Double(0, 0, circleDiameter,
            circleDiameter);
        Stroke stroke = new BasicStroke((float) 2.0);
        g2d.setStroke(stroke);
        g2d.fill(circle);
        g2d.setColor(Color.black);
        g2d.draw(circle);

        // draw the needle
        stroke = new BasicStroke((float) 2.0);
        g2d.setStroke(stroke);
        g2d.setColor(Color.red);
        int halfNeedleLen = (circleDiameter / 2) - (circleDiameter / 20);
        drawSegmentFromCenter(g2d, center, center, halfNeedleLen,
            mModel.getValue());
        drawSegmentFromCenter(g2d, center, center, circleDiameter / 12,
            mModel.getValue() - 180.0);

        // draw the center pivot point
        g2d.setColor(Color.black);
        int pivotW = circleDiameter / 20;
        Ellipse2D pivot = new Ellipse2D.Double(center - (pivotW / 2), center
            - (pivotW / 2), pivotW, pivotW);
        stroke = new BasicStroke((float) 1.0);
        g2d.setStroke(stroke);
        g2d.fill(pivot);

        // prepare font
        g2d.setColor(new Color(180, 180, 180));
        Font font = new Font("SansSerif", Font.PLAIN, pivotW * 3);
        g2d.setFont(font);
        FontMetrics metrics = g2d.getFontMetrics(font);
        int hgt = metrics.getHeight();

        // draw digital value
        String v = "" + mModel.getValue();
        int adv = metrics.stringWidth(v);
        Dimension size = new Dimension(adv + 2, hgt + 2);
        g2d.drawString(v, center - (size.width / 2), center + size.height
            + pivotW);

        // draw title
        font = new Font("SansSerif", Font.PLAIN, pivotW * 2);
        g2d.setFont(font);
        metrics = g2d.getFontMetrics(font);
        hgt = metrics.getHeight();
        String t = mModel.getTitle();
        adv = metrics.stringWidth(t);
        size = new Dimension(adv + 2, hgt + 2);
        g2d.drawString(t, center - (size.width / 2), center - size.height
            - pivotW);
    }

    /**
    Draw segment from center.
    @param  g2d Context
    @param  centerX Center X value
    @param  centerY Center Y value
    @param  length  Length of line
    @param  theta   Angle from straight up, to the right, in degrees
    */
    private void drawSegmentFromCenter(final Graphics2D g2d, final double
        centerX, final double centerY, final double length, final double
        theta) {
        double ltheta = (((theta - 90) * Math.PI) / 180.0);
        double x2 = length * Math.cos(ltheta);
        double y2 = length * Math.sin(ltheta);
        Line2D pointer = new Line2D.Double(centerX, centerY, (double) x2
            + centerX, (double) y2 + centerY);
        g2d.draw(pointer);
    }
}
