package edu.unc.ims.avp;

import org.json.JSONObject;
import org.json.JSONException;
import java.util.HashMap;
import java.util.Map;

/**
 * Create a BrokerError JSON object with an error code, an error message
 * and optional additional data.
 * 
 */
public class BrokerError {

  int mCode;
  int getCode() { return mCode; }
  
  String mMessage;
  String getMessage() { return mMessage; }
  
  String mData = "";
  String getData() { return mData; }

  BrokerError(int code) {
    this(code, "");
  }

  BrokerError(int code, String data) {
    mCode = code;
    mMessage = errorMessages.get(code);
    mData = data;
  }

  
  JSONObject toJSONObject() throws JSONException {
    return toJSONObject(false);
  }

  JSONObject toJSONObject(boolean status) throws JSONException {
    JSONObject obj = new JSONObject();
    if(status) {
      obj.put("status", "error");
    }
    obj.put("code",mCode);
    obj.put("message",mMessage);
    if((mData!=null) && (!mData.isEmpty())) {
      obj.put("data",mData);
    }
    return obj;
  }

  // error codes from -32000 to -32768 come from JSON 2.0 spec
  public static final int E_PARSE =                  -32700;
  public static final int E_UNSUPPORTED_METHOD =     -32601;
  public static final int E_PARAMS_PARSE =           -32602;

  public static final int E_SYSTEM_ERROR =           -31999;
  public static final int E_TIMEOUT =                -31998;
  public static final int E_IO =                     -31997;
  public static final int E_INST_RESPONSE =          -31996;
  public static final int E_BAD_COMMAND =            -31995;
  public static final int E_CONNECTION =             -31994;
  public static final int E_EXCEPTION =              -31990;

  public static final int E_UNSUPPORTED_REQUEST =    -31989;
  public static final int E_METHOD_PARSE =           -31988;
  public static final int E_ID_PARSE =               -31987;

  public static final int E_UNSUPPORTED_SET_PARAM =  -31979;
  public static final int E_SET_PARAM_RO =           -31978;
  public static final int E_UNSUPPORTED_VALUE =      -31977;

  public static final int E_UNSUPPORTED_STATUS_PARAM=-31969;
  public static final int E_STYLE_PARSE =            -31968;

  public static final int E_UNSUPPORTED_SUB_PARAM =  -31959;
  public static final int E_SUB_INTERVAL =           -31958;
  public static final int E_UPDATES_PARSE =          -31957;

  public static final int E_INVALID_RESPONSE =       -31949;
  public static final int E_INVALID_DATA =           -31948;

  public static final int E_SUB_NOT_FOUND =          -31939;

  public static final int E_TOKEN_NOT_AVAILABLE =    -31929;
  public static final int E_TOKEN_REQUIRED =         -31928;

  public static final int E_POWER_SET_FAILED =       -31919;
  public static final int E_POWER_CHECK_FAILED =     -31918;
  public static final int E_BROKER_IS_SUSPENDED =    -31917;
  public static final int E_INSTRUMENT_BUSY =        -31916;
  public static final int E_UNSUCCESSFUL =           -31915;

  public static final Map<Integer, String> errorMessages = new HashMap<Integer, String>();
  static {
    errorMessages.put(E_INVALID_RESPONSE, "Invalid response received.");
    errorMessages.put(E_INVALID_DATA, "Data has not been received or is invalid.");
    errorMessages.put(E_UNSUPPORTED_REQUEST, "Request not supported.");
    errorMessages.put(E_PARAMS_PARSE, "\"params\" could not be parsed.");
    errorMessages.put(E_STYLE_PARSE, "\"style\" could not be parsed.");
    errorMessages.put(E_UPDATES_PARSE, "\"updates\" could not be parsed.");
    errorMessages.put(E_METHOD_PARSE, "\"method\" could not be parsed.");
    errorMessages.put(E_ID_PARSE, "\"id\" could not be parsed.");
    errorMessages.put(E_UNSUPPORTED_METHOD, "Method not supported.");
    errorMessages.put(E_UNSUPPORTED_SET_PARAM, "Set parameter not supported.");
    errorMessages.put(E_UNSUPPORTED_SUB_PARAM, "Subscribe parameter not supported.");
    errorMessages.put(E_UNSUPPORTED_STATUS_PARAM, "Status parameter not supported.");
    errorMessages.put(E_SET_PARAM_RO, "Set parameter is read-only.");
    errorMessages.put(E_UNSUPPORTED_VALUE, "Parameter value not supported.");
    errorMessages.put(E_TIMEOUT, "Response from MM3 timed out.");
    errorMessages.put(E_IO, "MM3 threw IOException.");
    errorMessages.put(E_INST_RESPONSE, "MM3 returned unexpected response.");
    errorMessages.put(E_BAD_COMMAND, "MM3 returned 'BAD COMMAND'.");
    errorMessages.put(E_SUB_INTERVAL, "MM3 subscription \"min_update_rate\" greater than \"max_update_rate\".");
    errorMessages.put(E_SUB_NOT_FOUND, "No such subscription in unsubscribe request.");
    errorMessages.put(E_PARSE, "Parse error.");
    errorMessages.put(E_SYSTEM_ERROR, "System error.");
    errorMessages.put(E_CONNECTION, "Broker not connected to instrument.");
    errorMessages.put(E_TOKEN_NOT_AVAILABLE, "Another listener currently has the control token.");
    errorMessages.put(E_TOKEN_REQUIRED, "Control token required for requested method.");
    errorMessages.put(E_EXCEPTION, "Unspecified Java exception.");
    errorMessages.put(E_POWER_SET_FAILED, "Setting power failed.");
    errorMessages.put(E_POWER_CHECK_FAILED, "Checking power failed.");
    errorMessages.put(E_BROKER_IS_SUSPENDED, "Broker is suspended");
    errorMessages.put(E_INSTRUMENT_BUSY, "Instrument is busy");
    errorMessages.put(E_UNSUCCESSFUL, "Unsuccessful");
  }
}
