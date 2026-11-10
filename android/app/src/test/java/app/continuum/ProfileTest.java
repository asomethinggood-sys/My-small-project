package app.continuum;
import org.junit.Test;
import static org.junit.Assert.*;
import java.util.Base64;
import java.nio.charset.StandardCharsets;

public class ProfileTest {
    static final String URI="vless://123e4567-e89b-12d3-a456-426614174000@one.trycloudflare.com:443?encryption=none&security=tls&sni=one.trycloudflare.com&type=ws&host=one.trycloudflare.com&path=%2Fabc#Test";
    @Test public void supportsPlainAndBase64Subscriptions(){
        assertEquals(Profile.subscription(URI).key(),Profile.subscription(Base64.getEncoder().encodeToString(URI.getBytes(StandardCharsets.UTF_8))).key());
    }
    @Test public void onlyValidSupportedProfiles(){
        for(String value:new String[]{URI.replace("security=tls","security=none"),URI.replace("type=ws","type=tcp"),
            URI+"\n"+URI, URI.replace("path=%2Fabc","path=%0A"), URI.replace("vless://","vmess://"),
            URI.replace("#Test","&allowInsecure=1"),URI.replace("#Test","&type=ws"), URI.replace(":443?",":0?")}) {
            try { Profile.subscription(value);fail("Accepted invalid profile"); }catch(IllegalArgumentException expected){}
        }
    }
    @Test public void preservesEarlyDataAndCertificateChecks() throws Exception {
        Profile p=Profile.parse(URI.replace("%2Fabc","%2Fabc%3Fed%3D2048"));
        assertEquals("/abc?ed=2048",p.path);
        var config=p.config(true);
        assertFalse(config.getJSONArray("outbounds").getJSONObject(0).getJSONObject("streamSettings").getJSONObject("tlsSettings").getBoolean("allowInsecure"));
        assertEquals("tun",config.getJSONArray("inbounds").getJSONObject(0).getString("protocol"));
        assertEquals(1,config.getJSONArray("outbounds").length());
        assertEquals(0,p.config(false).getJSONArray("inbounds").length());
    }
    @Test public void labelsDoNotTriggerReconnect(){assertEquals(Profile.parse(URI).key(),Profile.parse(URI.replace("#Test","#Renamed")).key());}
    @Test public void urlPolicyRejectsDowngradeAndCredentials(){
        for(String s:new String[]{"http://example.com/sub","https://user:secret@example.com/sub","file:///etc/passwd","https://example.com/#fragment"}) {
            try{SubscriptionClient.validate(s);fail();}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void oversizedSubscriptionRejected(){try{Profile.subscription("x".repeat(65537));fail();}catch(IllegalArgumentException expected){}}
}
