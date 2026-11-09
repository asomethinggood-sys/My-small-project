package app.continuum;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;
public class NetworkConfigTest {
    @Test public void dnsNeverUsesDirectOutboundOrLocalDoh()throws Exception{
        JSONObject c=NetworkConfig.tunnel(Profile.parse(ProfileTest.URI),new JSONObject());
        assertEquals("UseIPv4",c.getJSONObject("dns").getString("queryStrategy"));
        assertFalse(c.getJSONObject("dns").getBoolean("disableCache"));
        for(int i=0;i<c.getJSONArray("outbounds").length();i++)assertNotEquals("freedom",c.getJSONArray("outbounds").getJSONObject(i).getString("protocol"));
        for(int i=0;i<c.getJSONObject("dns").getJSONArray("servers").length();i++)assertTrue(c.getJSONObject("dns").getJSONArray("servers").getJSONObject(i).getString("address").startsWith("https://"));
        JSONObject rule=c.getJSONObject("routing").getJSONArray("rules").getJSONObject(0);
        assertEquals("53",rule.getString("port"));assertEquals("tun",rule.getJSONArray("inboundTag").getString(0));assertEquals("dns-out",rule.getString("outboundTag"));
    }
    @Test public void hostnameRecoveryUsesHttpAndTlsNotTlsDecryption()throws Exception{
        JSONObject sniff=NetworkConfig.tunnel(Profile.parse(ProfileTest.URI),new JSONObject()).getJSONArray("inbounds").getJSONObject(0).getJSONObject("sniffing");
        assertTrue(sniff.getBoolean("enabled"));assertFalse(sniff.getBoolean("routeOnly"));assertEquals("http",sniff.getJSONArray("destOverride").getString(0));assertEquals("tls",sniff.getJSONArray("destOverride").getString(1));
    }
    @Test public void tunMtuMatchesValidatedSetting()throws Exception{
        for(int mtu:new int[]{1280,1400,1500}){JSONObject options=new JSONObject().put("mtu",mtu);assertEquals(mtu,NetworkConfig.mtu(options));assertEquals(mtu,NetworkConfig.tunnel(Profile.parse(ProfileTest.URI),options).getJSONArray("inbounds").getJSONObject(0).getJSONObject("settings").getInt("mtu"));}
        assertEquals(1400,NetworkConfig.mtu(new JSONObject().put("mtu",500)));
    }
    @Test public void dualStackIsExplicitAndChangesInstallationIdentity()throws Exception{
        JSONObject options=new JSONObject(),both=new JSONObject().put("dualStack",true);
        assertNotEquals(NetworkConfig.identity(options),NetworkConfig.identity(both));assertEquals("UseIP",NetworkConfig.tunnel(Profile.parse(ProfileTest.URI),both).getJSONObject("dns").getString("queryStrategy"));
    }
    @Test public void userProfileAndPreflightRemainUnchanged()throws Exception{
        Profile p=Profile.parse(ProfileTest.URI);String before=p.key();NetworkConfig.tunnel(p,new JSONObject());assertEquals(before,p.key());assertFalse(p.config(false).has("dns"));assertEquals(0,p.config(false).getJSONArray("inbounds").length());
    }
}
