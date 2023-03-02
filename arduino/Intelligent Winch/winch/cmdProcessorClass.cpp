// 
// 
// 

#include "cmdProcessorClass.h"
#include "winch.h"

cmdProcessorClass::cmdProcessorClass() {
  memset(cmdBuf, 0, CMD_BUF_LEN);
}

void cmdProcessorClass::readCommand() {

  // read available characters and put them in the command buffer
  char c = ' ';   // init to anything other than newline
  int i = 0;      // index into cmdBuf
  while (Ethernet1.getCmdClient().available()) {
    c = Ethernet1.getCmdClient().read();
    if (c == 8) { // backspace
      cmdBuf[i--] = 0;  // set null, then decrement i
    }
    else {
      cmdBuf[i++] = c;
      if (i >= CMD_BUF_LEN) { i--; } // don't let the index go past the end
      if (c == '\n') { break; }         // if there is a newline, process the line
    }
  }

  if (c == '\n') {  // process the line
    if (strlen(cmdBuf) > 2) {   // if there is more than just <cr><lf>

      sd.print(sd.getSerFileName(), &Serial, "Processing command: " + String(cmdBuf), true);
      sd.print(sd.getCmdFileName(), NULL, "--> " + String(cmdBuf), true);      // send to command log as well

      for (i = 0; i < (int)strlen(cmdBuf); i++) { cmdBuf[i] = tolower(cmdBuf[i]); }  // convert to lower case
      char *pch;  //will point to command buf tokens as we go
      pch = strtok(cmdBuf, " \r\n");

      if ( strcmp(pch, "hiworld") == 0 ) {
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Hello, world!"), true);
      } else {

      if ( strcmp(pch, "ip_address") == 0 ) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch==0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), 
            Ethernet1.DisplayAddress(Ethernet1.longToIP( EepromAccess.readEEPromLong(EepromAccess.IP))), true);
        } else {
          unsigned long addr = Ethernet1.IPtoLong(pch);
          if ((long)addr == -1) {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("ERROR: "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" does not parse to an IP address."));
          } else {
            EepromAccess.writeEEPromLong(EepromAccess.IP, addr);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("IP address set to "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
          }
        }
      } else {

      if ( strcmp(pch, "dns") == 0 ) {
        pch = strtok(NULL, " \r\n");  // get the next token
//        Serial.print("The second token is: |"); Serial.print(pch); Serial.println("|");

        if (pch == 0) {
          if (EepromAccess.readEEPromLong(EepromAccess.IP)==0) {
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("0.0.0.0"), true);  // set through DHCP
          } else {
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(),
              Ethernet1.DisplayAddress(Ethernet1.longToIP( EepromAccess.readEEPromLong(EepromAccess.DNS))), true);
          }
        } else {
          unsigned long addr = Ethernet1.IPtoLong(pch);
          if ((long)addr == -1) {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("ERROR: "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" does not parse to an IP address."));
          } else {
            EepromAccess.writeEEPromLong(EepromAccess.DNS, addr);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("DNS address set to "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
          }
        }
      } else {
        
      if ( strcmp(pch, "gateway") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          if (EepromAccess.readEEPromLong(EepromAccess.IP)==0) {
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("0.0.0.0"), true);  // set through DHCP
          } else {
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(),
              Ethernet1.DisplayAddress(Ethernet1.longToIP( EepromAccess.readEEPromLong(EepromAccess.GATE))), true);
          }
        } else {
          unsigned long addr = Ethernet1.IPtoLong(pch);
          if ((long)addr == -1) {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("ERROR: "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" does not parse to an IP address."));
          } else {
            EepromAccess.writeEEPromLong(EepromAccess.GATE, addr);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Gateway address set to "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
          }
        }
      } else {
        
      if ( strcmp(pch, "subnet") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          if (EepromAccess.readEEPromLong(EepromAccess.IP)==0) {
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("0.0.0.0"), true);  // set through DHCP
          } else {
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(),
              Ethernet1.DisplayAddress(Ethernet1.longToIP( EepromAccess.readEEPromLong(EepromAccess.SUB))), true);
          }
        } else {
          unsigned long addr = Ethernet1.IPtoLong(pch);
          if ((long)addr == -1) {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("ERROR: "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" does not parse to an IP address."));
          } else {
            EepromAccess.writeEEPromLong(EepromAccess.SUB, addr);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Subnet mask set to "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
          }
        }
      } else {
        
      if ( strcmp(pch, "stop") == 0) {
        MCtrl.stopMoving();
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Stopped."), true);
      } else {
        
      if ( strcmp(pch, "up_revolutions") == 0) {
        int speedPct = parseMove();
        if (speedPct < 2 || speedPct > 100 || m_target <= 0.0) {
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
        } else {
        if ( MCtrl.isNoRaise() || MCtrl.isBrake() ) { 
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot raise due to NO_RAISE or E_STOP input."), true);
        } else {
          // do the move
          MCtrl.moveSetup(speedPct);
          MCtrl.moveRelative(-1.0 * m_target);
          
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Moving up "), true);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), m_target);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" revolutions at "));
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), speedPct);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent of full speed."));
          checkIfMoving();
        }}
      } else {
        
      if ( strcmp(pch, "down_revolutions") == 0) {
        int speedPct = parseMove();
        if (speedPct < 2 || speedPct > 100 || m_target <= 0.0) {
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
        } else {
        if ( MCtrl.isNoLower() || MCtrl.isBrake() ) { 
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot lower due to NO_LOWER or E_STOP input."), true);
        } else {
          // do the move
          MCtrl.moveSetup(speedPct);
          MCtrl.moveRelative(m_target);
          Serial.print("MCtrl.getTargetSpeed(): "); Serial.println(MCtrl.getTargetSpeed());

          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Moving down "), true);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), m_target);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" revolutions at "));
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), speedPct);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent of full speed."));
          checkIfMoving();
        }}
      } else {
        
      if ( strcmp(pch, "up_distance") == 0) {
        int speedPct = parseMove();
        if (speedPct < 2 || speedPct > posFB.getFeedbackMaxSpeed() || m_target <= 0.0) {
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Distance must be positive and speed must be from 2 through "));
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), posFB.getFeedbackMaxSpeed());
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent."));
        } else {
        if ( MCtrl.isNoRaise() || MCtrl.isBrake() ) { 
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot raise due to NO_RAISE or E_STOP input."), true);
        } else {
          if (posFB.haveRecentPositionFeedback() == true) {
            // do the move
            MCtrl.moveSetup(speedPct);
            posFB.setFeedbackDelta(speedPct);
            posFB.setMoveTarget(double(posFB.getFeedbackPosition()) - m_target);            // convert move target to an absolute position
            MCtrl.moveAtSpeed(-1 * speedPct);
            
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Moving up "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), m_target);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" based on position feedback at "));
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), speedPct); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent of full speed."));
            checkIfMoving();
            
            posFB.setMovingUpWithFeedback(true);
          } else {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("No recent position feedback."));
          }
        }}
      } else {
        
      if ( strcmp(pch, "down_distance") == 0) {
        int speedPct = parseMove();
        if (speedPct < 2 || speedPct > posFB.getFeedbackMaxSpeed() || m_target <= 0.0) {
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Distance must be positive and speed must be from 2 through "));
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), posFB.getFeedbackMaxSpeed());
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent."));
        } else {
        if ( MCtrl.isNoLower() || MCtrl.isBrake() ) { 
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot lower due to NO_LOWER or E_STOP input."), true);
        } else {
          if (posFB.haveRecentPositionFeedback() == true) {
            // do the move
            MCtrl.moveSetup(speedPct);
            posFB.setFeedbackDelta(speedPct);
            posFB.setMoveTarget(double(posFB.getFeedbackPosition()) + m_target);            // convert move target to an absolute position
            MCtrl.moveAtSpeed(speedPct);
          
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Moving down "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), m_target);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" based on position feedback at "));
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), speedPct); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent of full speed."));
            checkIfMoving();
            
            posFB.setMovingDownWithFeedback(true);
          } else {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("No recent position feedback."));
          }
        }}
      } else {
        
      if ( strcmp(pch, "move_to_revolution") == 0) {
        int speedPct = parseMove();
        if (speedPct < 2 || speedPct > 100) {
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
        } else {
        if ( (MCtrl.getCurrPos() < m_target) && (MCtrl.isNoLower() || MCtrl.isBrake() )) { 
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot lower due to NO_LOWER or E_STOP input."), true);
        } else {
        if ( (MCtrl.getCurrPos() > m_target) && (MCtrl.isNoRaise() || MCtrl.isBrake() )) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot raise due to NO_RAISE or E_STOP input."), true);
        } else {
          // do the command
          MCtrl.moveSetup(speedPct);
          MCtrl.moveToPos(m_target);
          
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Moving to "), true);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), m_target);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" revolutions at "));
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), speedPct);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent of full speed."));
          checkIfMoving();
        }}}
      } else {
        
      if ( strcmp(pch, "move_to_position") == 0) {
        int speedPct = parseMove();
        if (speedPct < 2 || speedPct > posFB.getFeedbackMaxSpeed()) {
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Speed must be from 2 through "));
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), posFB.getFeedbackMaxSpeed());
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent."));
        } else {
        if ( (double(posFB.getFeedbackPosition()) < m_target) && (MCtrl.isNoLower() || MCtrl.isBrake()) ) { 
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot lower due to NO_LOWER or E_STOP input."), true);
        } else {
        if ( (double(posFB.getFeedbackPosition()) > m_target) && (MCtrl.isNoRaise() || MCtrl.isBrake()) ) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot raise due to NO_RAISE or E_STOP input."), true);
        } else {
          if (posFB.haveRecentPositionFeedback() == true) {
            // do the move
            MCtrl.moveSetup(speedPct);
            posFB.setFeedbackDelta(speedPct);
            posFB.setMoveTarget(m_target);

            // do we need to move up or down
            if (double(posFB.getFeedbackPosition()) < m_target) {
              MCtrl.moveAtSpeed(speedPct);
              posFB.setMovingDownWithFeedback(true);
            }
            if (double(posFB.getFeedbackPosition()) > m_target) {
              MCtrl.moveAtSpeed(-1 * speedPct);
              posFB.setMovingUpWithFeedback(true);
            }
          
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Moving to "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), m_target);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" based on position feedback at "));
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), speedPct); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent of full speed."));
            checkIfMoving();
          } else {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" No recent position feedback."));
          }
        }}}
      } else {
        
      if ( strcmp(pch, "set_zero") == 0) {
        MCtrl.setPos(0);
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Current positon set to zero."), true);
      } else {
        
      if ( strcmp(pch, "amps_limit") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), MCtrl.getAmpsLimit(), 2u, true);
        } else {
          float al = atof(pch);
          if (!isValidNumber(pch) || al <= 0) {  // must be greater than zero (zero disables)
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
          } else {
            if (al > MCtrl.MAX_AMPS) { al = MCtrl.MAX_AMPS; }  // can't go over MAX_AMPS
            MCtrl.setAmpsLimit(al);            
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Motor current limit set to "), true); 
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), al);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" amps."));
          }
        }
      } else {
        
      if ( strcmp(pch, "max_revolutions") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), Motor.getMaxRevolutions(), 2u, true);
        } else {
          float mr = atof(pch);
          if (!isValidNumber(pch) || mr <= 0) {  // must be greater than zero
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be a number greater than zero."));
          } else if (mr < abs(MCtrl.getCurrPos())) {
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Cannot set max revolutions to less than the current position."));
          } else {
            Motor.setMaxRevolutions(mr);

            // Create virtual limits that will be slightly larger than the max revolutions value
            // as a failsafe in case the arduino crashes while moving.
            MCtrl.setVirtualNegativeLimit(long(-1 * Motor.getMaxRevolutions()*Motor.getCPR()) - long(0.25*Motor.getCPR()));
            MCtrl.setVirtualPositiveLimit(long(     Motor.getMaxRevolutions()*Motor.getCPR()) + long(0.25*Motor.getCPR()));

            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Max revolutions set to "), true);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), Motor.getMaxRevolutions());
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" revolutions."));
          }        
        }
      } else {
        
      if ( strcmp(pch, "pterm") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), MCtrl.getPTerm(), DEC, true);
        } else {
          long p = atol(pch);
          if (!isValidNumber(pch) || p < 0 || p > 65535) {  // must be positive int
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be an integer from 0 through 65535."));
          } else {
            MCtrl.setPTerm(p);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("P term set to: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), p);
          }        
        }
      } else {
        
      if ( strcmp(pch, "iterm") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), MCtrl.getITerm(), DEC, true);
        } else {
          long it = atol(pch);
          if (!isValidNumber(pch) || it < 0 || it > 65535) {  // must be positive int
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be an integer from 0 through 65535."));
          } else {
            MCtrl.setITerm(it);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("I term set to: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), it);
          }        
        }
      } else {
        
      if ( strcmp(pch, "dterm") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), MCtrl.getDTerm(), DEC, true);
        } else {
          long d = atol(pch);
          if (!isValidNumber(pch) || d < 0 || d > 65535) {  // must be positive int
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be an integer from 0 through 65535."));
          } else {
            MCtrl.setDTerm(d);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("D term set to: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), d);
          }        
        }
      } else {
        
      if ( strcmp(pch, "pidscalar") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), MCtrl.getPIDScalar(), DEC, true);
        } else {
          int p = atoi(pch);
          if (!isValidNumber(pch) || p < 0 || p > 32) {  // must be positive int
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be an integer from 0 through 32."));
          } else {
            MCtrl.setPIDScalar(p);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("PIDSCALAR set to: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), p);
          }        
        }
      } else {
        
      if ( strcmp(pch, "vff") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), MCtrl.getVFF(), DEC, true);
        } else {
          int p = atoi(pch);
          if (!isValidNumber(pch) || p < 0 || p > 255) {  // must be positive int
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be an integer from 0 through 255."));
          } else {
            MCtrl.setVFF(p);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Velocity feed forward set to: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), p);
          }        
        }
      } else {
        
      if ( strcmp(pch, "store_tuning") == 0) {
        MCtrl.storeTuning();
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("PID tuning parameters stored to EEPROM."), true);
      } else {
        
      if ( strcmp(pch, "port_base") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), EepromAccess.readEEPromInt(EepromAccess.PORT_BASE), DEC, true);
        } else {
          long p = atol(pch);
          if (!isValidNumber(pch) || p < 0 || p > 65533) {  // must be positive int
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be an integer from 0 through 65533."));
          } else {
            EepromAccess.writeEEPromInt(EepromAccess.PORT_BASE, (unsigned int) p);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Port base set to: "), true); 
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), pch);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(".  Requires restart to take effect."));
          }        
        }
      } else {
        
      if ( strcmp(pch, "save_state") == 0) {
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Saving system state."), true);
        saveState();
      } else {

        if ( strcmp(pch, "reboot") == 0) {
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("System restarting."), true);
        saveState();
        software_Reboot();
      } else {
        
      if ( strcmp(pch, "motor_time") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(),  Motor.getMotorTimeDays(), 3u, true);
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" Days"));
        } else {
          float p = atof(pch);  // argument in fractional days
          if (!isValidNumber(pch) || p < 0.0) {  // must be positive
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be a positive number."));
          } else {
            Motor.setMotorTimeDays(p);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Motor time set to: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), p, 3u);
          }        
        }
      } else {
        
      if ( strcmp(pch, "reset_motor_time") == 0) {
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Resetting total accumulated motor run time to zero."), true);
        Motor.setMotorTimeDays(0.0);
      } else {

      if ( strcmp(pch, "ver") == 0) {
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), SWVERSION, true);
      } else {
        
      if ( strcmp(pch, "clearreports") == 0) {
        ApplicationMonitor.ClearReports();
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Application Monitor Reports Cleared."), true);
      } else {        
        
      if ( strcmp(pch, "motor_cpr") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), Motor.getCPR(), DEC, true);
        } else {
          long p = atol(pch);
          if (!isValidNumber(pch) || p < 0) {  // must be positive long
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be a positive integer."));
          } else {
            Motor.setCPR(p);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Motor counts per revolution set to: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), p);
          }        
        }
      } else {

      if ( strcmp(pch, "motor_rpm") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), Motor.getRPM(), 2u, true);
        } else {
          float al = atof(pch);
          if (!isValidNumber(pch) || al <= 0) {  // must be greater than zero
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be a number greater than zero."));
          } else {
            Motor.setRPM(al);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Motor RPM set to "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), Motor.getRPM());
            posFB.setFeedbackMaxSpeed();
          }
        }
      } else {

      if ( strcmp(pch, "fb_period") == 0) {
        pch = strtok(NULL, " \r\n");  // get the next token

        if (pch == 0) {
          sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), posFB.getFeedbackPeriod(), 2u, true );
        } else {
          float al = atof(pch);
          if (!isValidNumber(pch) || al <= 0) {  // must be greater than zero
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true); 
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Must be a number greater than zero."));
          } else {
            posFB.setFeedbackPeriod(al);
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Feedback period set to "), true); 
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), al);
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" seconds."));
            posFB.setFeedbackMaxSpeed();
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Max Speed set to "), true); 
            sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), posFB.getFeedbackMaxSpeed());
            sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(" percent for feedback based moves."));
          }
        }
      } else {

      if ( strcmp(pch, "uptime") == 0) {
        char upTimeString[100];
        snprintf(upTimeString, 100, "%s Days HH:MM:SS.SSS", sd.getUpTimeString());
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), upTimeString, true);
      } else {

      if ( strcmp(pch, "help") == 0 ||  strcmp(pch, "?") == 0) {
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("\nCommands Available:\n"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("\n  Network Commands:"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    ip_address xxx,xxx,xxx,xxx"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    dns xxx,xxx,xxx,xxx"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    gateway xxx,xxx,xxx,xxx"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    subnet xxx,xxx,xxx,xxx"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    port_base x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("\n  Motor Commands:"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    stop"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    up_revolutions x at x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    down_revolutions x at x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    up_distance x at x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    down_distance x at x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    move_to_revolution x at x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    move_to_position x at x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    set_zero"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    amps_limit x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    motor_cpr x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    motor_rpm x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    max_revolutions x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("\n  PID Tuning Commands:"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    pterm x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    iterm x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    dterm x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    pidscalar x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    vff x"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    store_tuning"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("\n  System Commands:"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    fb_period"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    save_state"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    reboot"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    motor_time"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    reset_motor_time"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    clearreports"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    ver"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("    uptime"));
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F(""));
      } else {

        sd.print(sd.getCmdFileName(), &Ethernet1.getCmdClient(), F("Bad command: "), true);
        sd.println(sd.getCmdFileName(), &Ethernet1.getCmdClient(), cmdBuf);
      }}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}}

    }
      memset(cmdBuf, 0, CMD_BUF_LEN);  // clear the command buffer after processing
  }
}


// Parses the move command by setting moveTarget (global) and
// returns speed, which will be the fourth token in the command buffer
// the third token must be the word "at"
// a zero return is a failure
int cmdProcessorClass::parseMove() {
  char *pch;
  int retVal = 0;

  pch = strtok(NULL, " \r\n"); // get the first token
  if (isValidNumber(pch)) { 
    m_target = strtod(pch, NULL);

    pch = strtok(NULL, " \r\n"); // get the next token
    if (strcmp(pch, "at") == 0) {
      pch = strtok(NULL, " \r\n"); // get the next token
      retVal = atoi(pch);
    }
  }
  return retVal;
}
