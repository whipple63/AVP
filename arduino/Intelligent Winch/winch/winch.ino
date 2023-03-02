 
/*
  Intelligent winch

  Operates a solutions^3 MM3 motor controller in response to commands
  
  We are expecting Mode 4 - Serial PID (closed loop)
  
  The Serial connection to the motor controller uses TTL levels going from 
  Serial3 on the Arduino (pins 14 and 15) to the DIN and DOUT pins on the MM3.
  
  The Ethernet address defaults to 192,168,0,150.  The value can be set through the 
  command interface and will take effect when the system is restarted.  The value set 
  is persistent.  It can be reset to default by depressing both up and down buttons before
  and during startup.  DHCP will be used if the ip address is set to 0,0,0,0.  Without
  a display, the only way to find what DHCP address was issued is through the USB interface.

  Network Commands:  (Stored in EEPROM)
    ip_address xxx,xxx,xxx,xxx
    dns xxx,xxx,xxx,xxx
    gateway xxx,xxx,xxx,xxx
    subnet xxx,xxx,xxx,xxx
    port_base x
  Motor Commands:
    stop
    up_revolutions x at x
    down_revolutions x at x
    up_distance x at x
    down_distance x at x
    move_to_revolution x at x
    move_to_position x at x
    set_zero
    amps_limit x
    motor_cpr x  (Stored in EEProm)
    motor_rpm x.xx  (Stored in EEProm)
    max_revolutions x  (Stored in EEProm)
  PID Tuning Commands:
    pterm x
    iterm x
    dterm x
    pidscalar x
    vff x
    store_tuning
  System Commands:
    fb_period
    save_state
    reboot
    motor_time
    reset_motor_time
    clearreports
    ver
    uptime
 */
#include <EEPROM.h>
//#include <Ethernet.h>
#include "Ethernet.h"     // We are using a modified version of the Ethernet code that implements keepalive packets
#include "winch.h"
#include <SPI.h>
#include <SdFat.h>
#include "sdLogger.h"

// instantiate an sd logger class
sdLogger sd;

//Watchdog::CApplicationMonitor ApplicationMonitor;
CApplicationMonitor ApplicationMonitor;

// instantiate a global 
EepromAccessClass EepromAccess;

// instantiate a global ethernet class
EthernetSupport Ethernet1;

// instantiate a motor class
MotorClass Motor;

// instantiate a motor controller class
MM3Class MCtrl;

// instanitate a command processor class
cmdProcessorClass cmdProc;

// instantiate a position feedback class
PositionFeedbackClass posFB;

// up and down buttons
boolean upButtonPressed = false;
boolean downButtonPressed = false;
unsigned long speedStartTime = 0L;	// initialize to zero
int speedIndex = 0;


//
// one time initialization on start-up
//
void setup() {
//  writeEEPromLong(EE_ADDR_OF_IP, 0);  // forces DHCP - just for testing...
  ApplicationMonitor.DisableWatchdog();

  // initialize serial:
  Serial.begin(9600);
  Serial3.begin(19200);
  Serial.setTimeout(500);
  Serial3.setTimeout(500);

  sd.init();  // init before any print statements
  sd.print(sd.getSerFileName(), &Serial, F("Free RAM between stack and heap at beginning of setup: "), true);
  sd.println(sd.getSerFileName(), &Serial, freeRam());

  sd.println(sd.getSerFileName(), &Serial, "", true);
  sd.println(sd.getSerFileName(), &Serial, F("Intelligent winch processor startup."), true);
  sd.println(sd.getSerFileName(), &Serial, String("Software version ") + SWVERSION, true);
  sd.println(sd.getSerFileName(), &Serial, "", true);
  
  ApplicationMonitor.Dump(Serial);
  ApplicationMonitor.DumpToLogFile();
  sd.println(sd.getSerFileName(), &Serial, "", true);

  // Initialize the buttons and read their state
  pinMode(UP_BUTTON_PIN, INPUT_PULLUP);
  pinMode(DOWN_BUTTON_PIN, INPUT_PULLUP);
  upButtonPressed = !digitalRead(UP_BUTTON_PIN);    // low is pressed
  downButtonPressed = !digitalRead(DOWN_BUTTON_PIN);

  // If both buttons are pressed, reset IP configuration to default values
  if (upButtonPressed && downButtonPressed) {
    sd.println(sd.getSerFileName(), &Serial, F("Resetting IP configuration to defaults."), true);
    Ethernet1.resetIPDefaults();
  }
    
  // start ethernet and print errors if set to DHCP and it fails
  if (Ethernet1.start() == 0) {
    sd.println(sd.getSerFileName(), &Serial, F("ERROR Failed to configure Ethernet using DHCP"), true);
    sd.println(sd.getSerFileName(), &Serial, F("ERROR Failed to configure Ethernet using DHCP"), true);
    sd.println(sd.getSerFileName(), &Serial, F("ERROR Failed to configure Ethernet using DHCP"), true);
  }
  sd.print(sd.getSerFileName(), &Serial, F("Ethernet initialized on: "), true);
  sd.println(sd.getSerFileName(), &Serial, Ethernet1.DisplayAddress(Ethernet.localIP()));

  unsigned int p = EepromAccess.readEEPromInt(EepromAccess.PORT_BASE);
  sd.println(sd.getSerFileName(), &Serial, "", true);
  sd.print(sd.getSerFileName(), &Serial, F("Output port: "), true);             sd.println(sd.getSerFileName(), &Serial, p);
  sd.print(sd.getSerFileName(), &Serial, F("Command port: "), true);            sd.println(sd.getSerFileName(), &Serial, p+1);
  sd.print(sd.getSerFileName(), &Serial, F("Position feedback port: "), true);  sd.println(sd.getSerFileName(), &Serial, p+2);


  // Report values initialized during the constructor
  sd.println(sd.getSerFileName(), &Serial, "", true);
  sd.print(sd.getSerFileName(), &Serial, F("Counts per revolutions read from EEProm as "), true);
  sd.println(sd.getSerFileName(), &Serial, Motor.getCPR());
  sd.print(sd.getSerFileName(), &Serial, F("Motor RPM read from EEProm as "), true);
  sd.println(sd.getSerFileName(), &Serial, Motor.getRPM());
  sd.print(sd.getSerFileName(), &Serial, F("Max revolutions read from EEProm as "), true);
  sd.println(sd.getSerFileName(), &Serial, Motor.getMaxRevolutions());

  sd.print(sd.getSerFileName(), &Serial, F("Total motor run time read from EEProm as "), true);
  sd.print(sd.getSerFileName(), &Serial, Motor.getMotorTimeDays(), 3u, false);
  sd.println(sd.getSerFileName(), &Serial, F(" Days"));
  sd.println(sd.getSerFileName(), &Serial, "", true);


                //
  delay(1000);  // allow a second for the motor controller to get started
                //


  MCtrl.init(); // initialize the motor controller
  
  // Create virtual limits that will be slightly larger than the max revolutions value
  // as a failsafe in case the arduino crashes while moving.
  MCtrl.setVirtualNegativeLimit(long(-1 * Motor.getMaxRevolutions()*Motor.getCPR()) - long(0.25*Motor.getCPR()));
  MCtrl.setVirtualPositiveLimit(long(     Motor.getMaxRevolutions()*Motor.getCPR()) + long(0.25*Motor.getCPR()));

  sd.println(sd.getSerFileName(), &Serial, "", true);
  sd.println(sd.getSerFileName(), &Serial, F("PID tuning parameters read from EEPROM as:"), true);
  sd.println(sd.getSerFileName(), &Serial, "P term: " + String( MCtrl.getPTerm() ), true);
  sd.println(sd.getSerFileName(), &Serial, "I term: " + String( MCtrl.getITerm()), true);
  sd.println(sd.getSerFileName(), &Serial, "D term: " + String( MCtrl.getDTerm()), true);
  sd.println(sd.getSerFileName(), &Serial, "PIDSCALAR: " + String( MCtrl.getPIDScalar()), true);
  sd.println(sd.getSerFileName(), &Serial, "Velocity feed forward: " + String( MCtrl.getVFF()), true);
  sd.println(sd.getSerFileName(), &Serial, "", true);

  // Restore the current position from EEPRom
  sd.println(sd.getSerFileName(), &Serial, "Current position read from EEProm as " + String( MCtrl.getCurrPos() ), true);  
  sd.println(sd.getSerFileName(), &Serial, "", true);

  // Sanity check that the current position is within the virtual limits
  if (abs(MCtrl.getCurrPos()) > double(MCtrl.getVirtualPositiveLimit())/Motor.getCPR()) {
    sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("WARNING - Current position is out of range.  This should never happen."), true);
    sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("WARNING - Resetting current position to zero."), true);
    sd.println(sd.getSerFileName(), &Serial, F("WARNING - Current position is out of range.  This should never happen."), true);
    sd.println(sd.getSerFileName(), &Serial, F("WARNING - Resetting current position to zero."), true);
    sd.println(sd.getSerFileName(), &Serial, "", true);
    MCtrl.setPos(0);
    saveState();
  }

  sd.println(sd.getSerFileName(), &Serial, "Feedback period read from EEProm as " + String(posFB.getFeedbackPeriod()) + " seconds.", true);
  sd.println(sd.getSerFileName(), &Serial, "", true);

  // initialize maximum speed for position based movements
  sd.println(sd.getSerFileName(), &Serial, "Max Speed set to " + String(posFB.getFeedbackMaxSpeed()) + " percent for feedback based moves.", true);


//  ApplicationMonitor.EnableWatchdog(Watchdog::CApplicationMonitor::Timeout_4s);  // last because the above can take a long time
  ApplicationMonitor.EnableWatchdog(CApplicationMonitor::Timeout_4s);  // last because the above can take a long time

  sd.print(sd.getSerFileName(), &Serial, F("Free RAM between stack and heap at end of setup: "), true);
  sd.println(sd.getSerFileName(), &Serial, freeRam());
}



//
// Main program loop
//
void loop() {
  ApplicationMonitor.IAmAlive();  // ping the watchdog timer
  ApplicationMonitor.SetData(1);  // any 32 bit value, anywhere in the code
  
  static unsigned long loop_time;
  static int lastSpd = 0;
  ConnectionChange connStatus;
  static float speedTolerance = 0.9;   // if speed drops below this percentage during over-current the motor will be shut off

  //
  // Handle the Ethernet ports
  //

  // Command server ----------------------------------
  connStatus = Ethernet1.checkCmdConnection();
  if (connStatus == NEW_CONNECT) {
    sd.println(sd.getSerFileName(), &Serial, F("Command client connected"), true);
    sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Welcome to the intelligent winch command server."), true);
  }
  if (connStatus == NEW_DISCONNECT) { sd.println(sd.getSerFileName(), &Serial, F("Command client disconnected"), true); }

  if (Ethernet1.getCmdConnected()) {
    cmdProc.readCommand();    // will execute commands when complete
  }

  // Output server ------------------------------------
  if (Ethernet1.getOutputConnected()) {
    // a client is considered connected if the connection has been closed but there is still unread data.
    while (Ethernet1.getOutputClient().available()) Ethernet1.getOutputClient().read();
  }
  connStatus = Ethernet1.checkOutputConnection();
  if (connStatus == NEW_CONNECT) {
    sd.println(sd.getSerFileName(), &Serial, F("Output client connected"), true);
  }
  if (connStatus == NEW_DISCONNECT) {
    sd.println(sd.getSerFileName(), &Serial, F("Output client disconnected"), true);
  }


  // Position feedback server ------------------------
  connStatus = Ethernet1.checkPosConnection();
  if (connStatus == NEW_CONNECT) {
    sd.println(sd.getSerFileName(), &Serial, F("Position client connected"), true);
  }
  if (connStatus == NEW_DISCONNECT) {
    sd.println(sd.getSerFileName(), &Serial, F("Position client disconnected"), true);
  }
  
  if (Ethernet1.getPosConnected()) {  // handle the position data input
    posFB.readPos();
  }


  //
  // Handle position feedback
  //
  if ( (posFB.movingUpWithFeedback() || posFB.movingDownWithFeedback()) && posFB.haveRecentPositionFeedback() == false) {
    MCtrl.stopMoving();
    sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to no recent position feedback."), true);
  }

  //
  // Handle the up and down buttons
  // LOW value means the button is pressed
  //

  // if it is time, increment the speed
  if (upButtonPressed && millis()-speedStartTime > TIME_PER_SPEED && speedIndex < NUM_OF_SPEEDS) {
    speedIndex++;
    MCtrl.moveAtSpeed(-1 * speedIndex * 100 / NUM_OF_SPEEDS);
    speedStartTime = millis();
  }
  if (downButtonPressed && millis()-speedStartTime > TIME_PER_SPEED && speedIndex < NUM_OF_SPEEDS) {
    speedIndex++;
    MCtrl.moveAtSpeed(speedIndex * 100 / NUM_OF_SPEEDS);
    speedStartTime = millis();
  }

  // check if there is a button transition
  if (!digitalRead(UP_BUTTON_PIN) && !upButtonPressed) {
    upButtonPressed = true;
    MCtrl.stopMoving();
    sd.println(sd.getSerFileName(), &Serial, F("Up button pressed."), true);
    MCtrl.setAmpsLimit(MCtrl.MAX_AMPS);
    speedIndex = 1;
    MCtrl.moveSetup(100);
    MCtrl.moveAtSpeed(-1 * speedIndex * 100 / NUM_OF_SPEEDS);
    speedStartTime = millis();
    speedTolerance = 0.5;   // allow speed to drop to half during overcurrent before shutting off motor
  }  
  if (digitalRead(UP_BUTTON_PIN) && upButtonPressed) {
    upButtonPressed = false;
    sd.println(sd.getSerFileName(), &Serial, F("Up button released."), true);
    MCtrl.stopMoving();
    speedTolerance = 0.9;   // restore speed tolerance value
  }
  if (!digitalRead(DOWN_BUTTON_PIN) && !downButtonPressed) {
    downButtonPressed = true;
    MCtrl.stopMoving();
    sd.println(sd.getSerFileName(), &Serial, F("Down button pressed."), true);
    MCtrl.setAmpsLimit(MCtrl.MAX_AMPS);
    speedIndex = 1;
    MCtrl.moveSetup(100);
    MCtrl.moveAtSpeed(speedIndex * 100 / NUM_OF_SPEEDS);
    speedStartTime = millis();
    speedTolerance = 0.5;   // allow speed to drop to half during overcurrent before shutting off motor
  }
  if (digitalRead(DOWN_BUTTON_PIN) && downButtonPressed) {
    downButtonPressed = false;
    sd.println(sd.getSerFileName(), &Serial, F("Down button released."), true);
    MCtrl.stopMoving();
    speedTolerance = 0.9;   // restore speed tolerance value
  }
      
  //
  // Every LOOP_INTERVAL, read the MM3 registers, handle error conditions
  // and provide feedback on the output port.
  //
  if (TimeSince(loop_time) >= 0) {
    loop_time = (unsigned long) millis() + LOOP_INTERVAL;
    
    MCtrl.readController();  // update position, speed, amps, status
    
    // stop when a move is done (saves power and is safer)
    if (MCtrl.isStopped()==false) {
      if (lastSpd==0 && MCtrl.getCurrSpd()==0) {
        MCtrl.stopMoving();
      }
      lastSpd = MCtrl.getCurrSpd();
    } else {
      lastSpd = -1;  // anything other than zero to allow startup
    }
    
    // Send an empty packet to each client to insure that the link is still good.
    // (Output is not necessary since it is written to frequently.)
    Ethernet1.getCmdServer().keepalive();
    Ethernet1.getPosServer().keepalive();

    // if any of the fault conditions have happened, stop moving
    if ( (MCtrl.isNoRaise() == true) && (MCtrl.getCurrSpd() < 0) ) { 
      MCtrl.stopMoving(); 
      sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to NO_RAISE input."), true);
    }
    if ( (MCtrl.isNoLower() == true) && (MCtrl.getCurrSpd() > 0) ) {
      MCtrl.stopMoving();
      sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to NO_LOWER input."), true);
    }
    if ( (MCtrl.isBrake() == true) && MCtrl.getCurrSpd() != 0) {
      MCtrl.stopMoving();
      sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to E-STOP (BRAKE) input."), true);
    }
    if (MCtrl.isOverCurrent() == true) {
       if (abs(float(MCtrl.getCurrSpd())) < abs(speedTolerance*MCtrl.getTargetSpeed()) ) {
         MCtrl.stopMoving();
         sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to exceeding motor current limit."), true);
       }
    } 
    if (MCtrl.isOverTemp() == true) {
      MCtrl.stopMoving();
      sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to over temperature."), true);
    }     

    // Sanity check that the current position is within the virtual limits
    if (abs(MCtrl.getCurrPos()) > MCtrl.getVirtualPositiveLimit()) {
      MCtrl.stopMoving(); // in case it happened when we were moving
      sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("WARNING - Current position is out of range.  This should never happen."), true);
      sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("WARNING - Resetting current position to zero."), true);
      sd.println(sd.getSerFileName(), &Serial, F("WARNING - Current position is out of range.  This should never happen."), true);
      sd.println(sd.getSerFileName(), &Serial, F("WARNING - Resetting current position to zero."), true);
      MCtrl.setPos(0);
    }

    // if max revolutions has been reached, stop moving
    if ( (abs(MCtrl.getCurrSpd()) > 0) && ( abs(MCtrl.getCurrPos())  > Motor.getMaxRevolutions()) ) {
      // back up to just past the limit in case we overshot
      MCtrl.moveSetup(100);
      if (MCtrl.getCurrPos() > 0) {
        MCtrl.moveToPos(double(Motor.getMaxRevolutions() -0.01));
      } else {
        MCtrl.moveToPos(double(-(Motor.getMaxRevolutions() -0.01)));
      }
      sd.println(sd.getSerFileName(), &Serial, "pos: " + String(abs(MCtrl.getCurrPos())) + " maxR: " + String(Motor.getMaxRevolutions()), true);
      sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped due to reaching maximum revolution limit."), true);
    }
    
    // output feedback on console and Ethernet port
    sd.println(sd.getSerFileName(), &Serial,
      String(sd.getUpTimeString()) + ", " +
      String(MCtrl.getCurrPos()) + ", " +
      String(MCtrl.getCurrSpd()) + ", " +
      String(float(MCtrl.getCurrAmps()) * 0.02) + ", " +
      String(MCtrl.isNoRaise() != 0) + ", " +
      String(MCtrl.isNoLower() != 0) + ", " +
      String(MCtrl.isBrake() != 0) + ", " +
      String(MCtrl.isOverCurrent() != 0) + ", " +
      String(MCtrl.isOverTemp() != 0),
      false);

    if (Ethernet1.getOutputConnected()) {
      sd.println(sd.getOutFileName(), &Ethernet1.getOutputClient(), 
        String(MCtrl.getCurrPos()) + "," +
        String(MCtrl.getCurrSpd()) + "," +
        String(float(MCtrl.getCurrAmps()) * 0.02) + "," +
        String(MCtrl.isNoRaise() != 0) + "," +
        String(MCtrl.isNoLower() != 0) + "," +
        String(MCtrl.isBrake() != 0) + "," +
        String(MCtrl.isOverCurrent() != 0) + "," +
        String(MCtrl.isOverTemp() != 0),
        true);
    }
    
    // check if it is time to save the state
    if ( (Motor.getIdleTime()>0L) && (TimeSince(Motor.getIdleTime()) > 10*60*1000L) ) {  // ten minutes
      sd.println(sd.getSerFileName(), &Serial, F("Auto-saving state."), true);
      saveState();
      sd.print(sd.getSerFileName(), &Serial, F("Free RAM between stack and heap after auto-save: "), true);
      sd.println(sd.getSerFileName(), &Serial, freeRam());
    }

    // check if it is time to increment the log files
    sd.incrementIfIntervalHasBeen(1.0); // days
//    sd.incrementIfIntervalHasBeen(1.0/24.0); // One hour just for testing...
  }  

  delay(1);        // delay in between loops for stability
}  // end of main loop

