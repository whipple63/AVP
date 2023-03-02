// 
// Ethernet class implements some utility functions to help manage our Ethernet connections.
// 

#include "EthernetClass.h"

// Constructor - constructs servers with default port numbers
// 
// Note: As far as I can tell, there must be a port number in order to declare these
// servers.  These port numbers will be overwritten by values in EEPROM during setup
// (if necessary).
EthernetSupport::EthernetSupport()
  : outputServer(DEFAULT_PORT_BASE),
       cmdServer(DEFAULT_PORT_BASE+1),
       posServer(DEFAULT_PORT_BASE+2) {


  // Mac address for the arduino is set via software.  If there is no address assigned
  // (on a sticker) then just make one up.
  // I just made one up for this one:  FAB DECAF CAFE
  uint8_t mMac[6] = { 0xFA, 0xBD, 0xEC, 0xAF, 0xCA, 0xFE };

  // initialize variables       
  outputConnected = false; // whether or not the client was connected previously
  cmdConnected = false;
  posConnected = false;
}


bool EthernetSupport::resetIPDefaults() {
  EepromAccess.writeEEPromLong(EepromAccess.IP, IPtoLong(F("192.168.0.150")));
  EepromAccess.writeEEPromLong(EepromAccess.DNS, IPtoLong(F("192.168.0.1")));
  EepromAccess.writeEEPromLong(EepromAccess.GATE, IPtoLong(F("192.168.0.1")));
  EepromAccess.writeEEPromLong(EepromAccess.SUB, IPtoLong(F("255.255.255.0")));
  EepromAccess.writeEEPromInt(EepromAccess.PORT_BASE, (unsigned int)DEFAULT_PORT_BASE);

  return(true); // for now...
}

// initialize the arduino ethernet library
bool EthernetSupport::start() {
  bool retval = true;

  // Read the ip address etc from EEPROM
  IPAddress ipaddr = longToIP(EepromAccess.readEEPromLong(EepromAccess.IP));
  IPAddress dns = longToIP(EepromAccess.readEEPromLong(EepromAccess.DNS));
  IPAddress gate = longToIP(EepromAccess.readEEPromLong(EepromAccess.GATE));
  IPAddress sub = longToIP(EepromAccess.readEEPromLong(EepromAccess.SUB));

  if (EepromAccess.readEEPromLong(EepromAccess.IP) == 0) {
    if (Ethernet.begin(mMac) == 0) {  // start using DHCP
      retval = false;
    }
  }
  else {
    Ethernet.begin(mMac, ipaddr, dns, gate, sub); // this call does not return a value
  }

  // start listening for clients
  unsigned int p = EepromAccess.readEEPromInt(EepromAccess.PORT_BASE);
  outputServer = EthernetServer(p);
  cmdServer = EthernetServer(p + 1);
  posServer = EthernetServer(p + 2);
  outputServer.begin();
  cmdServer.begin();
  posServer.begin();

  return retval;
}

ConnectionChange EthernetSupport::checkOutputConnection() {
  ConnectionChange retval = NO_CHANGE;

  if (!outputConnected) {
    outputClient = outputServer.available();
  }
  // when the output client sends the first byte
  if (outputClient.connected()) {
    if (!outputConnected) {
      // clear out the input buffer:
      outputClient.flush();
      outputConnected = true;
      retval = NEW_CONNECT;
    }
  }
  else {
    if (outputConnected) {
      retval = NEW_DISCONNECT;
    }
    outputConnected = false;
  }

  return retval;
}

ConnectionChange EthernetSupport::checkCmdConnection() {
  ConnectionChange retval = NO_CHANGE;

  if (!cmdConnected) {
    cmdClient = cmdServer.available();
  }
  // when the cmd client sends the first byte
  if (cmdClient.connected()) {
    if (!cmdConnected) {
      // clear out the input buffer
      cmdClient.flush();
      cmdConnected = true;
      retval = NEW_CONNECT;
    }
  }
  else {
    if (cmdConnected) {
      retval = NEW_DISCONNECT;
    }
    cmdConnected = false;
  }

  return retval;
}

ConnectionChange EthernetSupport::checkPosConnection() {
  ConnectionChange retval = NO_CHANGE;

  if (!posConnected) {
    posClient = posServer.available();
  }
  // when the pos client sends the first byte
  if (posClient.connected()) {
    if (!posConnected) {
      // clear out the input buffer:
      posClient.flush();
      posConnected = true;
      retval = NEW_CONNECT;
    }
  }
  else {
    if (posConnected) {
      retval = NEW_DISCONNECT;
    }
    posConnected = false;
  }

  return retval;
}


// converts a period separated list of four ints in the form of an IP address
// to a long value and returns it.  Returns -1 if failed.
unsigned long EthernetSupport::IPtoLong(String rb) {
  String s;
  byte bytes[4];
  unsigned long retVal = 0;

  // parse the values we are interested in
  int itemNum = 0;
  int b = 0;
  int i = 0;
  while (i != -1) {
    // find the next s
    if (i != 0) { b = i + 1; }  // skip the first time
    i = rb.indexOf('.', b);
    if (i == -1) {
      s = rb.substring(b);  // to the end
    }
    else {
      s = rb.substring(b, i);
    }
    s.trim();

    bytes[itemNum] = (byte)s.toInt();
    if ((s.toInt() < 0) || (s.toInt() > 255)) {
      retVal = -1;  // fail
      break;
    }

    retVal += (unsigned long)bytes[itemNum] << (24 - itemNum * 8);
    itemNum++;
  }

  if (itemNum != 4) {
    retVal = -1;  // fail
  }
  return retVal;
}


IPAddress EthernetSupport::longToIP(unsigned long addr) {
  byte b[4];
  for (int i = 0; i<4; i++) {
    b[i] = (byte)((addr >> (24 - i * 8)) & 0xFF);
  }
  return IPAddress(b[0], b[1], b[2], b[3]);
}

String EthernetSupport::DisplayAddress(IPAddress address)
{
  return String(address[0]) + "." +
    String(address[1]) + "." +
    String(address[2]) + "." +
    String(address[3]);
}

