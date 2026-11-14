package app.continuum;

import org.json.*;

/** Release configuration policy: there is no user-selectable server/source. */
public final class ManagedSettings {
    private ManagedSettings(){}
    public static JSONObject apply(JSONObject old){
        try{
            int interval=old.optInt("interval",60);if(interval!=30&&interval!=60&&interval!=120)interval=60;
            int mtu=old.optInt("mtu",1400);if(mtu!=1280&&mtu!=1400&&mtu!=1500)mtu=1400;
            int slot=old.optInt("betaSlot",0);if(slot<0||slot>10)slot=0;
            return new JSONObject().put("betaSlot",slot).put("source",SubscriptionClient.DEFAULT).put("selection",-1)
                .put("profiles",new JSONArray()).put("country","").put("interval",interval)
                .put("mtu",mtu).put("dualStack",old.optBoolean("dualStack",false));
        }catch(JSONException e){throw new IllegalStateException("Could not prepare connection settings");}
    }
}
