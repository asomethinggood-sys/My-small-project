package app.continuum;
import org.junit.Test;
import org.json.*;
import java.util.Base64;
import java.nio.charset.StandardCharsets;
import static org.junit.Assert.*;

public class ProtocolTest {
    private static String b64(String s){return Base64.getUrlEncoder().withoutPadding().encodeToString(s.getBytes(StandardCharsets.UTF_8));}
    private static String vmess(String net)throws Exception{return "vmess://"+b64(new JSONObject().put("add","example.com").put("port",443).put("id","123e4567-e89b-12d3-a456-426614174000").put("aid",0).put("net",net).put("tls","tls").toString());}
    @Test public void vlessTcpTlsIsARealOutbound()throws Exception{
        Profile p=Profile.parse("vless://123e4567-e89b-12d3-a456-426614174000@example.com:443?security=tls&type=tcp");
        JSONObject o=p.config(false).getJSONArray("outbounds").getJSONObject(0);
        assertEquals("vless",o.getString("protocol"));assertEquals("tcp",o.getJSONObject("streamSettings").getString("network"));
        assertFalse(o.getJSONObject("streamSettings").getJSONObject("tlsSettings").getBoolean("allowInsecure"));
    }
    @Test public void vmessTcpAndWsUseAEADAndTls()throws Exception{
        for(String t:new String[]{"tcp","ws"}){JSONObject o=Profile.parse(vmess(t)).config(false).getJSONArray("outbounds").getJSONObject(0);assertEquals("vmess",o.getString("protocol"));assertEquals(t,o.getJSONObject("streamSettings").getString("network"));assertEquals(0,o.getJSONObject("settings").getJSONArray("vnext").getJSONObject(0).getJSONArray("users").getJSONObject(0).getInt("alterId"));}
    }
    @Test public void trojanTcpAndWsPreservePassword()throws Exception{
        for(String t:new String[]{"tcp","ws"}){JSONObject o=Profile.parse("trojan://secret%3Apass@example.com:443?type="+t).config(false).getJSONArray("outbounds").getJSONObject(0);assertEquals("trojan",o.getString("protocol"));assertEquals("secret:pass",o.getJSONObject("settings").getJSONArray("servers").getJSONObject(0).getString("password"));}
    }
    @Test public void shadowsocksSIP002AllSupportedAeadMethods()throws Exception{
        for(String method:new String[]{"aes-128-gcm","aes-256-gcm","chacha20-ietf-poly1305"}){Profile p=Profile.parse("ss://"+b64(method+":secret:pass")+"@127.0.0.1:8388");JSONObject o=p.config(false).getJSONArray("outbounds").getJSONObject(0);assertEquals("shadowsocks",o.getString("protocol"));assertFalse(o.has("streamSettings"));assertEquals(method,o.getJSONObject("settings").getJSONArray("servers").getJSONObject(0).getString("method"));}
    }
    @Test public void unsupportedOptionsAreRejected(){
        for(String uri:new String[]{ProfileTest.URI.replace("security=tls","security=reality"),ProfileTest.URI.replace("#Test","&flow=xtls-rprx-vision"),"ss://"+b64("aes-128-gcm:password")+"@example.com:8388?plugin=obfs", "trojan://pass@example.com:443?allowInsecure=1", "ss://"+b64("none:password")+"@example.com:8388"}){try{Profile.parse(uri);fail("Unsupported option accepted");}catch(IllegalArgumentException expected){}}
    }
}
