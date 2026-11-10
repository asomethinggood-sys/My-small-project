package app.continuum;
import org.json.*;
import org.junit.Test;
import java.net.URL;
import static org.junit.Assert.*;

public class LocationCatalogTest {
    private JSONObject sample()throws Exception{return new JSONObject().put("schema_version",1).put("purpose","research_metadata_not_connection_profiles").put("generated_at",100).put("expires_at",200).put("countries",new JSONArray().put(new JSONObject().put("country","DE").put("discovered_servers",3).put("discovered_providers",1).put("selectable",true).put("verified_servers",999)));}
    @Test public void metadataCannotPromoteOrBecomeAProfile()throws Exception{
        LocationCatalog c=LocationCatalog.parse(sample().toString());assertTrue(c.fresh(150));assertFalse(c.fresh(200));assertFalse(c.fresh(99));assertEquals("Discovered · not available",c.status(c.countries.get("DE"),150));assertEquals("Snapshot expired",c.status(c.countries.get("DE"),201));
    }
    @Test public void duplicateCountriesRejected()throws Exception{JSONObject j=sample();j.getJSONArray("countries").put(j.getJSONArray("countries").get(0));try{LocationCatalog.parse(j.toString());fail();}catch(JSONException expected){}}
    @Test public void negativeAndFractionalCountsRejected()throws Exception{for(Object n:new Object[]{-1,1.5,"3",10001}){JSONObject j=sample();j.getJSONArray("countries").getJSONObject(0).put("discovered_servers",n);try{LocationCatalog.parse(j.toString());fail();}catch(JSONException expected){}}}
    @Test public void lifetimesAndSchemaRestricted()throws Exception{for(JSONObject j:new JSONObject[]{sample().put("expires_at",1001),sample().put("expires_at",99),sample().put("schema_version",2),sample().put("purpose","profiles")}){try{LocationCatalog.parse(j.toString());fail();}catch(JSONException expected){}}}
    @Test public void redirectsNeverDowngradeOrSendToUnknownHost()throws Exception{assertTrue(CatalogClient.allowed(new URL(CatalogClient.URL)));assertTrue(CatalogClient.allowed(new URL("https://release-assets.githubusercontent.com/x")));for(String s:new String[]{"http://github.com/x","https://github.com.evil.example/x","https://user:password@github.com/x","https://github.com:444/x","https://localhost/x"})assertFalse(CatalogClient.allowed(new URL(s)));}
    @Test public void rustPresentationAndMotionAbi(){assertEquals(2,RustCore.connectionPhase(true,true,true,true,false));assertEquals(1,RustCore.connectionPhase(true,false,true,true,false));assertEquals(3,RustCore.connectionPhase(true,true,true,true,true));assertEquals(500,RustCore.motionProgress(500,1000,false));assertEquals(1000,RustCore.motionProgress(0,1000,true));assertEquals(3,RustCore.exitEligibility(100,90,190,1,14));}
}
