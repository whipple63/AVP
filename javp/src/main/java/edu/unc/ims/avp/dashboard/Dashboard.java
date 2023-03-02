package edu.unc.ims.avp.dashboard;

import edu.unc.ims.avp.BrokerClient;
import edu.unc.ims.avp.BrokerClientListener;
import edu.unc.ims.avp.Db;
import edu.unc.ims.avp.Logger;
import javax.swing.ImageIcon;
import javax.swing.JFrame;
import java.awt.event.KeyEvent;
import javax.swing.SwingUtilities;
import javax.swing.JComponent;
import javax.swing.JLabel;
import javax.swing.JCheckBox;
import javax.swing.JTabbedPane;
import javax.swing.JScrollPane;
import javax.swing.JOptionPane;
import java.io.File;
import java.io.PrintWriter;
import java.io.FileInputStream;
import java.util.Properties;
import java.util.Map;
import java.util.Hashtable;
import java.util.List;
import java.util.Vector;
import java.util.ArrayList;
import java.sql.Statement;
import java.sql.Timestamp;
import java.sql.ResultSet;
import java.util.Iterator;
import edu.unc.ims.avp.Logger.LogLevel;
import javax.swing.table.TableColumn;
import javax.swing.table.TableRowSorter;
import javax.swing.RowSorter;
import javax.swing.SortOrder;
import javax.swing.JPanel;
import javax.swing.JButton;
import javax.swing.JTable;
import java.awt.GridLayout;
import java.awt.BorderLayout;
import java.awt.Container;
import java.awt.Color;
import javax.swing.JMenuBar;
import javax.swing.table.DefaultTableModel;
import javax.swing.table.TableModel;
import javax.swing.JMenu;
import javax.swing.JMenuItem;
//import java.awt.FlowLayout;
import java.awt.event.ActionListener;
import javax.swing.event.ChangeListener;
import javax.swing.event.ChangeEvent;
import java.awt.event.ActionEvent;
import edu.unc.ims.avp.gui.Compass;
import org.json.JSONArray;
import org.json.JSONObject;

/**
AVP Broker Dashboard.
*/
public class Dashboard extends JFrame implements Runnable,
    BrokerClientListener, ActionListener, ChangeListener {
    /**
    Logger.
    */
    private Logger mLogger = Logger.getLogger();

    /**
    Configuration properties.
    */
    private Properties mProperties = new Properties();

    /**
    The compass.
    */
    private static Compass mCompass = new Compass("Compass");

    /**
    Wind direction.
    */
    private static Compass mWindDir = new Compass("Wind");

    /**
    Wind direction (uncorrected).
    */
    private static Compass mUncorrectedWindDir = new Compass(
        "Uncorrected Wind");

    private DefaultTableModel mLogTableModel;
    private TableRowSorter<TableModel> mLogTableSorter;

    /**
    Database connection.
    */
    Db mDb;

    /**
    Log table.
    */
    JTable mLogTable;

    /**
    Menu bar.
    */
    JMenuBar mMnuBar;

    /**
    File menu.
    */
    JMenu mMnuFile;

    /**
    Exit menu item.
    */
    JMenuItem mMnuExit;

    /**
    Reload menu item.
    */
    JMenuItem mMnuReload;

    /**
    Column names for log table.
    */
    String[] mLogColumnNames = {"Source",
                        "Time",
                        "Message",
                        "Comment",
                        "Save",
                        "Level"};
    /**
    Constructor.
    @param  config  Configuration file
    @throws Exception on error
    */
    public Dashboard(final List<File> config) throws Exception {
        super("AVP Dashboard");

        // load configuration file(s)
        Iterator<File> i = config.iterator();
        while (i.hasNext()) {
            mProperties.load(new FileInputStream(i.next()));
        }
        // Establish a connection to the database.
        //mDb = new Db(mProperties);

        // setup logging
        mLogger.setLevel(mProperties.getProperty("log_level", "FATAL"));
        mLogger.setLogFile(mProperties.getProperty("log_file", "-"));

        this.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        this.getContentPane().setLayout(new GridLayout(1, 1));

        // Make the tabbed pane and panels
        mTab = new JTabbedPane();
        JPanel p = makeSonde6Panel();

        mTab.addTab("Sonde", null, p, "Sonde 6 Series");
        mCurState = mTab2State.get(p);
        mCurPanel = mTab2Panel.get(p);

        mTab.addTab("Digital I/O", null, makeAccesIOPanel(),
                "Acces I/O");

        mTab.addTab("Wind", null, makeWindPanel(),
                "Young 32500 Wind Sensor");

        mTab.addTab("Sounder", null, makeSounderPanel(),
                "Depth Sounder");

        mTab.addTab("Motor", null, makeMotorPanel(),
                "Motor Controller");

        mTab.setTabLayoutPolicy(JTabbedPane.SCROLL_TAB_LAYOUT);
        mTab.addChangeListener(this);
        add(mTab);

        // build the menu
        mMnuBar = new JMenuBar();
        mMnuFile = new JMenu("File");
        mMnuReload = new JMenuItem("Reload Log Data");
        mMnuReload.addActionListener(this);
        mMnuFile.add(mMnuReload);
        mMnuExit = new JMenuItem("Exit");
        mMnuExit.addActionListener(this);
        mMnuFile.add(mMnuExit);
        mMnuBar.add(mMnuFile);
        this.setJMenuBar(mMnuBar);

        setAppState(State.S_IDLE);

        this.setBounds(100,100, 800, 600);
        this.setVisible(true);
    }

    private JPanel makePortGrid(final String name) {
        JPanel outer = new JPanel(new BorderLayout());
        outer.add(new JLabel(name), BorderLayout.NORTH);
        JPanel grid = new JPanel(new GridLayout(8,3));
        for(int row=0;row<8;row++) {
            grid.add(new JLabel(""+row));
            grid.add(new JCheckBox("out", true));
            grid.add(new JLabel(""+row));
        }
        outer.add(grid, BorderLayout.CENTER);
        return outer;
    }

    protected JPanel makeAccesIOPanel() {
        JPanel p = new JPanel();
        p.setLayout(new GridLayout(1,1));
        GeneralPanel gp = new GeneralPanel(this, "avp3.dyndns.org", 8880);
        mTab2Panel.put(p, gp);
        mTab2State.put(p, new AppState(State.S_IDLE));
        p.add(gp);
        //p.add(makePortGrid("test"));

        return p;
    }

    protected JPanel makeWindPanel() {
        JPanel p = new JPanel();
        p.setLayout(new GridLayout(1,1));
        GeneralPanel gp = new GeneralPanel(this, "avp3.dyndns.org", 8882);
        mTab2Panel.put(p, gp);
        mTab2State.put(p, new AppState(State.S_IDLE));
        p.add(gp);
        return p;
    }

    protected JPanel makeSounderPanel() {
        JPanel p = new JPanel();
        p.setLayout(new GridLayout(1,1));
        GeneralPanel gp = new GeneralPanel(this, "avp3.dyndns.org", 8887);
        mTab2Panel.put(p, gp);
        mTab2State.put(p, new AppState(State.S_IDLE));
        p.add(gp);
        return p;
    }

    protected JPanel makeMotorPanel() {
        JPanel p = new JPanel();
        p.setLayout(new GridLayout(1,1));
        GeneralPanel gp = new GeneralPanel(this, "avp3.dyndns.org", 8881);
        mTab2Panel.put(p, gp);
        mTab2State.put(p, new AppState(State.S_IDLE));
        p.add(gp);
        return p;
    }

    protected JPanel makeSonde6Panel() {
        JPanel p = new JPanel();
        p.setLayout(new GridLayout(2,1));
        GeneralPanel gp = new GeneralPanel(this, "avp3.dyndns.org", 8883);
        mTab2Panel.put(p, gp);
        mTab2State.put(p, new AppState(State.S_IDLE));
        p.add(gp);

        // make sonde-specific sub-panel
        JPanel sp = new JPanel();
        //sp.setLayout(new GridLayout(2,1));
        mBtnSondeCollect = new JButton("Collect Data");
        mBtnSondeCollect.addActionListener(this);
        sp.add(mBtnSondeCollect);
        mBtnSondeWipe = new JButton("Wipe");
        mBtnSondeWipe.addActionListener(this);
        sp.add(mBtnSondeWipe);
        p.add(sp);
        
        return p;
    }

    protected void reloadLogData() {
        // get the latest log messages
        // KAG - should support date filtering in the future
        try {
            mLogTableModel.setDataVector(mLogger.getAllLogMessages(),
                mLogColumnNames);
            //mLogTableSorter.allRowsChanged();
        } catch(Exception e) {
            e.printStackTrace();
        }
    }

    protected void addTable(Container c) throws Exception {
        mLogTableModel = new DefaultTableModel(
            mLogger.getAllLogMessages(), mLogColumnNames);
        mLogTable = new JTable(mLogTableModel);
        //mLogTable.setAutoResizeMode(JTable.AUTO_RESIZE_OFF);
        int def_widths[] = { 341, 170, 560, 26, 33, 32 };
        /*for (int i = 0; i < mLogColumnNames.length; i++) {
            ((TableColumn)mLogTableModel.getColumnClass(i)).setPreferredWidth(def_widths[i]);
        }*/
        //mLogTable.setAutoCreateRowSorter(false);
        mLogTable.setFillsViewportHeight(true);
        //mLogTableSorter = new TableRowSorter<TableModel>(mLogTable.getModel());
        //mLogTable.setRowSorter(mLogTableSorter);
        //List <RowSorter.SortKey> sortKeys = new ArrayList<RowSorter.SortKey>();
        //sortKeys.add(new RowSorter.SortKey(1, SortOrder.DESCENDING));
        //mLogTableSorter.setSortKeys(sortKeys); 

        JScrollPane scrollPane = new JScrollPane(mLogTable);
        c.add(scrollPane);
    }

    private void setAppState(State state) {
        if(mCurState == null)
            return;
        mCurState.setState(state);
        if(state == State.S_IDLE) {
            mCurPanel.mBtnList.setEnabled(false);
            mCurPanel.mBtnStatus.setEnabled(false);
            mCurPanel.mBtnAcquire.setEnabled(false);
            mCurPanel.mBtnSoftReset.setEnabled(false);
            mCurPanel.mBtnShutdown.setEnabled(false);
            mBtnSondeCollect.setEnabled(false);
        } else if(state == State.S_CONNECTED) {
            mCurPanel.mBtnList.setEnabled(true);
            mCurPanel.mBtnStatus.setEnabled(false);
            mCurPanel.mBtnAcquire.setEnabled(true);
            mCurPanel.mBtnSoftReset.setEnabled(false);
            mCurPanel.mBtnShutdown.setEnabled(false);
            mBtnSondeCollect.setEnabled(false);
        }
    }

    private State getAppState() {
        return mCurState.getState();
    }

    protected void tick() {
        //reloadLogData();
    }

    /**
    Run.
    */
    public final void run() {
        int cnt = 0;
        for (;;) {
            try {
                Thread.sleep(mTickCnt);
                tick();
                cnt++;
            } catch (Exception e) {
                e.printStackTrace();
                break;
            }
        }
    }

    /**
    Main.
    @param  args    args
    @throws Exception on error
    */
    public static void main(final String[] args) throws Exception {
        if (args.length < 1) {
            System.err.println("usage: " + Dashboard.class.getName()
                + "<configuration_file>");
            System.exit(1);
        }
        final List<File> cfs = new Vector<File>();
        for(int i = 0;i < args.length; i++) {
            File cf = new File(args[i]);
            if (!cf.exists()) {
                System.err.println("Configuration file does not exist: " + cf);
                System.exit(2);
            }
            if (!cf.canRead()) {
                System.err.println("Unable to read configuration file: " + cf);
                System.exit(3);
            }
            cfs.add(cf);
        }
        //Schedule a job for the event-dispatching thread:
        //creating and showing this application's GUI.
        javax.swing.SwingUtilities.invokeLater(new Runnable() {
            public void run() {
                try {
                    Thread t = new Thread(new Dashboard(cfs));
                    t.start();
                } catch (Exception e) {
                    e.printStackTrace();
                }
            }
        });
    }

    /**
    Convenience lookup.
    Temporary helper method.
    @param  jo  Main JSON response 
    @param  id  Id of desired data element
    @return value
    @throws Exception on error
    */
    private double getDoubleValue(final JSONObject jo, final int id) throws
        Exception {
            JSONArray ja = jo.getJSONArray(null);
            JSONObject ida = ja.getJSONObject(0);
            JSONObject value = ja.getJSONObject(1);
            JSONObject desc = ja.getJSONObject(2);
            for (int i = 0; i < ida.length(); i++) {
                if (ida.getInt(null) == id) {
                    return value.getDouble(null);
                }
            }
            return 0.0;
    }

    /**
    Data update.
    @param  d   data
    */
    public final void onData(final JSONObject d) {
        boolean error = false;
        JSONObject o = d;
        System.out.println(o);
        System.out.flush();
        if(o.has("error")) {
            error = true;
            try {
                JOptionPane.showMessageDialog(this, o.getJSONObject(
                    "error").get("message") + "(" + o.getJSONObject(
                    "error").get("code") + ")",
                    "Error", JOptionPane.ERROR_MESSAGE);
            } catch(Exception e) {
            }
        }
        if(mCurState.mCommand == Command.ACQUIRE) {
            mCurPanel.mBtnAcquire.setText("Release");
            mCurPanel.mBtnShutdown.setEnabled(true);
            mCurPanel.mBtnSoftReset.setEnabled(true);
            mBtnSondeCollect.setEnabled(true);
        } else if(mCurState.mCommand == Command.RELEASE) {
            mCurPanel.mBtnAcquire.setText("Acquire");
            mCurPanel.mBtnShutdown.setEnabled(false);
            mCurPanel.mBtnSoftReset.setEnabled(false);
            mBtnSondeCollect.setEnabled(false);
        } else if(mCurState.mCommand == Command.RESET) {
        } else if(mCurState.mCommand == Command.SHUTDOWN) {
        } else if(mCurState.mCommand == Command.STATUS) {
            mCurPanel.getModel().setData(o);
        } else if(mCurState.mCommand == Command.SONDE_COLLECT) {
            if(!error) {
                mBtnSondeCollect.setText("Stop Collecting");
            }
        } else if(mCurState.mCommand == Command.SONDE_STOP_COLLECT) {
            if(!error) {
                mBtnSondeCollect.setText("Collect Data");
            }
        } else if(mCurState.mCommand == Command.LIST) {
            mCurPanel.getModel().setData(o);
            mCurPanel.mBtnStatus.setEnabled(true);
        }
        mCurState.mCommand = Command.NONE;
        this.setEnabled(true);
    }

    /**
    Milliseconds to delay 
    */
    private int mTickCnt = 5000;

    /**
    Fast animation.
    */
    private static final int FAST_TICK = 10;

    private void sendCmd(Command c) {
        sendCmd(c, null);
    }

    private void sendCmd(Command c, JSONObject request) {
        this.setEnabled(false);
        try {
            JSONObject o = new JSONObject();
            if(c == Command.ACQUIRE) {
                o.put("method", "tokenAcquire");
                JSONObject p = new JSONObject();
                p.put("name", "helloworld");
                o.put("params", p);
            } else if(c == Command.SONDE_COLLECT) {
                o.put("method", "startCollection");
            } else if(c == Command.SONDE_STOP_COLLECT) {
                o.put("method", "stopCollection");
            } else if(c == Command.SONDE_WIPE) {
                o.put("method", "wipe");
            } else if(c == Command.RELEASE) {
                o.put("method", "tokenRelease");
            } else if(c == Command.LIST) {
                o.put("method", "list_data");
            } else if(c == Command.RESET) {
                o.put("method", "reset");
            } else if(c == Command.STATUS) {
                o = request;
            } else if(c == Command.SHUTDOWN) {
                o.put("method", "shutdown");
            }
            o.put("id", "1");
            mCurClient.send(o);
            mCurState.mCommand = c;
        } catch (Exception ee) {
            JOptionPane.showMessageDialog(this, ee.toString(),
                "Critical Error", JOptionPane.ERROR_MESSAGE);
        }
    }

    /**
    Slow animation.
    */
    private static final int SLOW_TICK = 100;

    public void actionPerformed(ActionEvent e) {
        if(e.getSource() == mMnuExit) {
            // save gui settings
            /*
            TableColumn column = null;
            for (int i = 0; i < mLogColumnNames.length; i++) {
                column = mLogTable.getColumnModel().getColumn(i);
                //System.out.println(i + ")" + column.getWidth());
            }*/
            System.out.println(this.getBounds());
            System.exit(1);
        } else if(e.getSource() == mCurPanel.mBtnAcquire) {
            if(mCurPanel.mBtnAcquire.getText().equals("Release")) {
                sendCmd(Command.RELEASE);
            } else {
                sendCmd(Command.ACQUIRE);
            }
        } else if(e.getSource() == mBtnSondeCollect) {
            if(mBtnSondeCollect.getText().equals("Collect Data")) {
                sendCmd(Command.SONDE_COLLECT);
            } else {
                sendCmd(Command.SONDE_STOP_COLLECT);
            }
        } else if(e.getSource() == mBtnSondeWipe) {
            sendCmd(Command.SONDE_WIPE);
        } else if(e.getSource() == mCurPanel.mBtnSoftReset) {
            sendCmd(Command.RESET);
        } else if(e.getSource() == mCurPanel.mBtnShutdown) {
            sendCmd(Command.SHUTDOWN);
            setAppState(State.S_IDLE);
            mCurPanel.mBtnConnect.setText("Connect");
            mCurPanel.mBtnAcquire.setText("Acquire");
        } else if(e.getSource() == mCurPanel.mBtnConnect) {
            if(getAppState() == State.S_CONNECTED) {
                mCurClient.shutdown();
                mCurPanel.mBtnConnect.setText("Connect");
                setAppState(State.S_IDLE);
            } else {
                try {
                    mCurClient = new BrokerClient(mCurPanel.mTxtHost.getText(),
                        Integer.parseInt(mCurPanel.mTxtPort.getText()));
                    Thread mClientThread = new Thread(mCurClient);
                    mClientThread.start();
                    mCurClient.addListener(this);
                    mCurPanel.mBtnConnect.setText("Disconnect");
                    mCurState.setClient(mCurClient);
                    setAppState(State.S_CONNECTED);
                } catch(Exception ee) {
                    JOptionPane.showMessageDialog(this, ee.toString(),
                        "Critical Error", JOptionPane.ERROR_MESSAGE);
                }
            }
        } else if(e.getSource() == mCurPanel.mBtnStatus) {
            // compose our request from listed data elements
            try {
                JSONObject request = new JSONObject();
                request.put("method", "status");
                request.put("id", "1");
                JSONObject response = mCurPanel.getModel().getData();
                JSONObject result = response.getJSONObject("result");
                Iterator i = result.keys();
                List<String> p = new Vector<String>();
                while(i.hasNext()) {
                    p.add(i.next().toString());
                }
                JSONArray dataArray = new JSONArray(p);
                JSONObject data = new JSONObject();
                data.put("data", dataArray);
                request.put("params", data);
System.out.println(request);
                sendCmd(Command.STATUS, request);
            }catch(Exception ee) {
                ee.printStackTrace();
            }
        } else if(e.getSource() == mCurPanel.mBtnList) {
            sendCmd(Command.LIST);
        }
    }

    protected static ImageIcon createImageIcon(String path) {
        java.net.URL imgURL = Dashboard.class.getResource(path);
        if (imgURL != null) {
            return new ImageIcon(imgURL);
        } else {
            System.err.println("Couldn't find file: " + path);
            return null;
        }
    }

    public void stateChanged(ChangeEvent e) {
        mCurPanel = mTab2Panel.get(mTab.getSelectedComponent());
        mCurState = mTab2State.get(mTab.getSelectedComponent());
        mCurClient = mCurState.getClient();
        setAppState(mCurState.getState());
    }


    GeneralPanel mCurPanel;
    private Map<JPanel, AppState> mTab2State = new Hashtable<JPanel,
        AppState>();
    private Map<JPanel, GeneralPanel> mTab2Panel = new Hashtable<JPanel,
        GeneralPanel>();
    private int mSelectedTab = -1;
    JTabbedPane mTab;
    JButton mBtnSondeCollect;
    JButton mBtnSondeWipe;
    AppState mCurState;
    private enum State { S_IDLE, S_CONNECTED, S_ACQUIRING, S_RELEASING };
    private BrokerClient mCurClient;
    private enum Command { NONE, ACQUIRE, RELEASE, LIST, RESET, SHUTDOWN, STATUS, SONDE_COLLECT, SONDE_STOP_COLLECT, SONDE_WIPE };

    public class AppState {
        private State mState;
        public Command mCommand = Command.NONE;
        private BrokerClient mClient;
        public AppState(State s) {
            mState = s;
        }
        public State getState() {
            return mState;
        }
        public void setState(State s) {
            mState = s;
        }
        public void setClient(BrokerClient c) {
            mClient = c;
        }
        public BrokerClient getClient() {
            return mClient;
        }
    }
}
