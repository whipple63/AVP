// EthernetClass.h

#ifndef _ETHERNETCLASS_h
#define _ETHERNETCLASS_h

#if defined(ARDUINO) && ARDUINO >= 100
	#include "arduino.h"
#else
	#include "WProgram.h"
#endif

//#include <Ethernet.h>
#include "Ethernet.h"     // We are using a modified version of the Ethernet code that implements keepalive packets
#include "EepromAccess.h"
extern EepromAccessClass EepromAccess;

const int DEFAULT_PORT_BASE = 63520;  // port number for output (cmd and pos - add 1 each)

// flags when a connection makes a transition from connected to disconnected or vice versa
enum ConnectionChange {
  NO_CHANGE,
  NEW_CONNECT,
  NEW_DISCONNECT
};

class EthernetSupport {

  uint8_t mMac[6];

  IPAddress ipaddr, dns, gate, sub;

  EthernetServer outputServer;
  EthernetServer cmdServer;
  EthernetServer posServer;
  EthernetClient outputClient;
  EthernetClient cmdClient;
  EthernetClient posClient;

  bool outputConnected = false; // whether or not the client was connected previously
  bool cmdConnected = false;
  bool posConnected = false;


public:
  EthernetSupport();

  uint8_t *getMac() { return mMac; }
  IPAddress getIPAddress()  { return ipaddr; }
  IPAddress getDNS()        { return dns;    }
  IPAddress getGateway()    { return gate;   }
  IPAddress getSubnetMask() { return sub;    }
  EthernetClient& getOutputClient() { return outputClient; }
  EthernetClient& getCmdClient() { return cmdClient; }
  EthernetClient& getPosClient() { return posClient; }
  EthernetServer& getOutputServer() { return outputServer; }
  EthernetServer& getCmdServer() { return cmdServer; }
  EthernetServer& getPosServer() { return posServer; }
  bool getOutputConnected() { return outputConnected; }
  bool getCmdConnected()    { return cmdConnected; }
  bool getPosConnected()    { return posConnected; }

  ConnectionChange checkOutputConnection();
  ConnectionChange checkCmdConnection();
  ConnectionChange checkPosConnection();

  // reset the stored IP configuration values to their defaults
  bool resetIPDefaults();

  bool start();

  // converts a period separated list of four ints in the form of an IP address
  // to a long value and returns it.  Returns -1 if failed.
  unsigned long IPtoLong(String);

  IPAddress longToIP(unsigned long);

  String DisplayAddress(IPAddress address);   // convert an ip address to a string
};

#endif

