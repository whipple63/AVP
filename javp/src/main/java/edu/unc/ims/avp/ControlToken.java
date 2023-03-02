package edu.unc.ims.avp;

import org.json.JSONObject;
import org.json.JSONException;

/**
 * Handle the control token for this broker.  Keeps track of who has it if anyone,
 * and allows for acquiring and releasing.  Keeps a readable ID associated with the owner.
 * 
 */
public class ControlToken {

    private ControllerClientHandler owner = null;
    private String ownerID = "";

    /**
     * Take the token away from the ControllerClientHandler (release it)
     * Used during clean-up when the client handler is exiting.
     */
    public synchronized void take() {
        owner.releaseToken();
        owner = null;
        ownerID = "";
    }

    
    /**
     * Give the token to the ControllerClientHandler (acquire it)
     * @param handler
     * @param id 
     */
    private synchronized void give(ControllerClientHandler handler, String id) {
        owner = handler;
        owner.acquireToken();
        ownerID = id;
    }

    
    private synchronized boolean inUse() {
        return (owner != null);
    }

    
    /**
     * Acquire the token either politely, or by force
     * @param handler
     * @param request
     * @param force
     * @param reply
     * @throws Exception 
     */
    private void acquire(ControllerClientHandler handler, JSONObject request, 
            boolean force, BrokerMessage reply) throws Exception {
        
        if( !inUse() || handler.equals(owner) || force ) {
            String id = "(unnamed)";
            JSONObject params = request.optJSONObject("params");
            if(params != null) {
                id = params.optString("name", id);
            }
            if( force && inUse() ) {
                take();
            }
            give(handler, id);
            reply.addResult("ok");
        } else {
            reply.addError(BrokerError.E_TOKEN_NOT_AVAILABLE, ownerID);
        }
    }

    
    /**
     * Release the token if we have it.
     * @param handler
     * @param reply
     * @throws Exception 
     */
    private void release(ControllerClientHandler handler, BrokerMessage reply) throws Exception {
        if(handler.equals(owner)) {
            take();
            reply.addResult("ok");
        } else {
            reply.addError(BrokerError.E_TOKEN_REQUIRED); /* could do this in the broker */
        }
    }

    
    /**
     * add the ownerID to the result
     * 
     * @param reply
     * @throws Exception 
     */
    private void owner(BrokerMessage reply) throws Exception {
        reply.addResult(ownerID);
    }

    
    /**
     * Handle client requests for the control token.
     * @param handler   the calling client
     * @param request   
     * @param reply
     * @throws JSONException
     * @throws Exception 
     */
    public void processJSONRequest(ControllerClientHandler handler, JSONObject request, BrokerMessage reply)
            throws JSONException, Exception {
        
      String method = request.getString("method");
      
      if (method.equals("tokenAcquire")) {
          acquire(handler, request, false, reply);
          
      } else if (method.equals("tokenForceAcquire")) {
          acquire(handler, request, true, reply);
          
      } else if (method.equals("tokenRelease")) {
          release(handler, reply);
          
      } else if (method.equals("tokenOwner")) {
          owner(reply);
      }
    }
    

}
