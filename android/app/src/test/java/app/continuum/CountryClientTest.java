package app.continuum;

import org.json.*;
import org.junit.Test;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.*;
import static org.junit.Assert.*;

public class CountryClientTest {
    private final String token="T".repeat(43);
    private JSONObject settings()throws Exception{return new JSONObject().put("countryService","https://service.example").put("countryUser","alice").put("countryKey","K".repeat(43)).put("country","DE");}
    private JSONObject reply()throws Exception{return new JSONObject().put("country","DE").put("token",token).put("generation",7).put("expires_in",60).put("profile","vless://11111111-1111-4111-8111-111111111111@service.example:443?security=tls&type=ws&encryption=none&sni=service.example&host=service.example&path="+URLEncoder.encode("/s/"+token+"/7",StandardCharsets.UTF_8.name()));}
    @Test public void profileIsBoundToCountryHostTokenAndGeneration()throws Exception{
        CountryClient c=new CountryClient(new CountryClient.Source(settings()),(m,p,b)->reply());CountryClient.Lease lease=c.acquire("DE",1000);
        assertEquals(61000,lease.deadline);assertEquals(7,lease.generation);assertEquals("DE",lease.country);
        assertEquals(0,RustCore.leaseAction(1000,lease.deadline,true));assertEquals(1,RustCore.leaseAction(31000,lease.deadline,true));assertEquals(2,RustCore.leaseAction(61000,lease.deadline,true));
    }
    @Test public void rejectsWrongCountryGenerationTokenAndOrigin()throws Exception{
        for(JSONObject row:new JSONObject[]{reply().put("country","FR"),reply().put("generation",8),reply().put("token","X".repeat(43)),reply().put("profile",reply().getString("profile").replace("service.example","other.example"))}){
            CountryClient c=new CountryClient(new CountryClient.Source(settings()),(m,p,b)->row);try{c.acquire("DE",1000);fail();}catch(IllegalArgumentException expected){}
        }
    }
    @Test public void rejectsInvalidLifetimesAndNumericStrings()throws Exception{
        for(Object ttl:new Object[]{0,301,-1,"60",60.5}){CountryClient c=new CountryClient(new CountryClient.Source(settings()),(m,p,b)->reply().put("expires_in",ttl));try{c.acquire("DE",1000);fail();}catch(IllegalArgumentException expected){}}
    }
    @Test public void serviceOriginCannotCarryQueryCredentialsOrPlaintext()throws Exception{
        for(String origin:new String[]{"http://service.example","https://user:secret@service.example","https://service.example/path","https://service.example?x=1","https://service.example:8443"}){try{new CountryClient.Source(settings().put("countryService",origin));fail();}catch(IllegalArgumentException expected){}}
    }
    @Test public void selectionAndCredentialChangeInvalidateBinding()throws Exception{
        String a=CountryClient.binding(settings());assertNotEquals(a,CountryClient.binding(settings().put("country","FR")));assertNotEquals(a,CountryClient.binding(settings().put("countryKey","N".repeat(43))));assertEquals(2,RustCore.leaseAction(1000,61000,false));
    }
    @Test public void metadataCannotPretendToBeAuthenticatedAvailability()throws Exception{
        CountryClient c=new CountryClient(new CountryClient.Source(settings()),(m,p,b)->new JSONObject().put("schema_version",1).put("purpose","research_metadata_not_connection_profiles").put("countries",new JSONArray()));
        try{c.availability(1000);fail();}catch(IllegalArgumentException expected){}
    }
    @Test public void liveAvailabilityExpiresAndRejectsDuplicates()throws Exception{
        JSONObject row=new JSONObject().put("country","DE").put("pool_count",2).put("provider_count",1).put("expires_in",60).put("udp",true);
        JSONObject reply=new JSONObject().put("schema_version",1).put("purpose","authenticated_live_availability").put("countries",new JSONArray().put(row));
        CountryClient c=new CountryClient(new CountryClient.Source(settings()),(m,p,b)->reply);assertEquals(61000,c.availability(1000).get(0).deadline);
        reply.getJSONArray("countries").put(row);try{c.availability(1000);fail();}catch(IllegalArgumentException expected){}
    }
    @Test public void releaseUsesPrivateTokenBodyNotUrl()throws Exception{
        List<String> paths=new ArrayList<>();CountryClient c=new CountryClient(new CountryClient.Source(settings()),(m,p,b)->{paths.add(p);if(p.equals("/v1/disconnect")){assertEquals(token,b.getString("token"));return new JSONObject();}return reply();});
        c.release(c.acquire("DE",1000));assertEquals(List.of("/v1/sessions","/v1/disconnect"),paths);
    }
}
