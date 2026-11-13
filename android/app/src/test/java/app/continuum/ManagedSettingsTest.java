package app.continuum;

import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class ManagedSettingsTest {
    @Test public void legacyCustomSourcesProfilesAndCountryCredentialsAreRemoved()throws Exception{
        JSONObject old=new JSONObject().put("source","https://private.example/secret").put("selection",0)
            .put("profiles",new JSONArray().put(new JSONObject().put("uri","secret")))
            .put("country","DE").put("countryService","https://private.example").put("countryKey","secret")
            .put("mtu",1280).put("dualStack",true).put("interval",120);
        JSONObject safe=ManagedSettings.apply(old);
        assertEquals(SubscriptionClient.DEFAULT,safe.getString("source"));assertEquals(-1,safe.getInt("selection"));
        assertEquals(0,safe.getJSONArray("profiles").length());assertEquals("",safe.getString("country"));
        assertFalse(safe.has("countryKey"));assertFalse(safe.has("countryService"));assertFalse(safe.toString().contains("secret"));
        assertEquals(1280,safe.getInt("mtu"));assertTrue(safe.getBoolean("dualStack"));assertEquals(120,safe.getInt("interval"));
    }
    @Test public void invalidTuningGetsSafeDefaults()throws Exception{
        JSONObject safe=ManagedSettings.apply(new JSONObject().put("mtu",1).put("interval",0));
        assertEquals(1400,safe.getInt("mtu"));assertEquals(60,safe.getInt("interval"));
    }
    @Test public void uiCopyDoesNotEchoUntrustedStateOrImplementation(){
        String bad="github.com/asomethinggood-sys secret xray://private";
        for(String state:new String[]{bad,"Connected","Connecting","Offline","Reconnecting","Checking update","Waiting for network","Disconnecting"}){
            String text=(ConnectionCopy.title(state)+ConnectionCopy.detail(state,true)).toLowerCase();
            for(String forbidden:new String[]{"github","asomethinggood","secret","xray","://","subscription","profile"})assertFalse(text.contains(forbidden));
        }
    }
}
