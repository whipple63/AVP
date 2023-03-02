package edu.unc.ims.avp.dashboard;

import javax.swing.*;
import java.awt.event.*;
import java.awt.*;

public class GeneralPanel extends JPanel {
    public JTextField mTxtHost = new JTextField("localhost");
    public JTextField mTxtPort = new JTextField("8888");
    public JButton mBtnConnect = new JButton("Connect");
    public JButton mBtnList = new JButton("List");
    public JButton mBtnStatus = new JButton("Status");
    public JButton mBtnAcquire = new JButton("Acquire");
    public JButton mBtnSoftReset = new JButton("Reset");
    public JButton mBtnShutdown = new JButton("Shutdown");
    public JTable mTable;
    private ParamTableModel mTableModel;
    private Component mParent;

    public GeneralPanel(Component parent, String defaultHost, int defaultPort) {
        mParent = parent;

        JPanel pnlHostPort = createHostPortPanel(defaultHost, defaultPort);
        JPanel pnlParamTable = createParamTablePanel();

        GroupLayout layout = new GroupLayout(this);
        layout.setAutoCreateGaps(true);
        layout.setAutoCreateContainerGaps(true);
        layout.setHorizontalGroup(
            layout.createParallelGroup()
                .addComponent(pnlHostPort)
                .addComponent(pnlParamTable)
        );
        layout.setVerticalGroup(
            layout.createSequentialGroup()
                .addComponent(pnlHostPort)
                .addComponent(pnlParamTable)
        );
        this.setLayout(layout);
    }

    private JPanel createParamTablePanel() {
        JPanel p = new JPanel();
        mTableModel = new ParamTableModel();
        mTable = new JTable(mTableModel);
        JScrollPane scrollPane = new JScrollPane(mTable);
        mTable.setFillsViewportHeight(true);
        p.add(scrollPane);
        GroupLayout layout = new GroupLayout(p);
        layout.setAutoCreateGaps(true);
        layout.setAutoCreateContainerGaps(true);
        layout.setHorizontalGroup(
            layout.createParallelGroup()
                .addComponent(scrollPane)
                .addGroup(layout.createSequentialGroup()
                    .addComponent(mBtnList)
                    .addComponent(mBtnStatus)
                    .addComponent(mBtnAcquire)
                    .addComponent(mBtnSoftReset)
                    .addComponent(mBtnShutdown)
                )
        );
        layout.setVerticalGroup(
            layout.createSequentialGroup()
                .addComponent(scrollPane)
                .addGroup(layout.createParallelGroup()
                    .addComponent(mBtnList)
                    .addComponent(mBtnStatus)
                    .addComponent(mBtnAcquire)
                    .addComponent(mBtnSoftReset)
                    .addComponent(mBtnShutdown)
                )
        );
        mBtnList.addActionListener((ActionListener)mParent);
        mBtnStatus.addActionListener((ActionListener)mParent);
        mBtnAcquire.addActionListener((ActionListener)mParent);
        mBtnSoftReset.addActionListener((ActionListener)mParent);
        mBtnShutdown.addActionListener((ActionListener)mParent);
        p.setLayout(layout);
        return p;
    }

    private JPanel createHostPortPanel(String defaultHost, int defaultPort) {
        mTxtHost.setText(defaultHost);
        mTxtPort.setText(defaultPort+"");
        mTxtHost.setPreferredSize(new Dimension(200,
            mTxtHost.getPreferredSize().height));
        mTxtPort.setPreferredSize(new Dimension(50,
            mTxtPort.getPreferredSize().height));
        JLabel lblHost = new JLabel("Host:");
        JLabel lblPort = new JLabel("Port:");
        JPanel top = new JPanel();
        GroupLayout layout = new GroupLayout(top);
        layout.setAutoCreateGaps(true);
        layout.setAutoCreateContainerGaps(true);
        layout.setHorizontalGroup(
            layout.createSequentialGroup()
                .addComponent(lblHost)
                .addComponent(mTxtHost)
                .addComponent(lblPort)
                .addComponent(mTxtPort)
                .addComponent(mBtnConnect)
        );
        layout.setVerticalGroup(
            layout.createParallelGroup(GroupLayout.Alignment.BASELINE)
                .addComponent(lblHost)
                .addComponent(mTxtHost)
                .addComponent(lblPort)
                .addComponent(mTxtPort)
                .addComponent(mBtnConnect)
        );
        top.setLayout(layout);
        mBtnConnect.addActionListener((ActionListener)mParent);
        return top;
    }

    public ParamTableModel getModel() {
        return mTableModel;
    }
}
