package app.continuum;

import org.junit.Test;
import org.json.*;
import java.util.*;
import static org.junit.Assert.*;

public class BetaCatalogTest {
    private JSONObject valid()throws Exception{return new JSONObject().put("schema",1).put("slot",1).put("generation","12345-1").put("issued_at",1000).put("expires_at",2000).put("country","US").put("uri","vless://f2222222-2222-4222-8222-222222222222@owned-fixture.trycloudflare.com:443?security=tls&type=ws&path=%2Ffixture");}
    @Test public void strictRecord()throws Exception{BetaCatalog.Entry e=BetaCatalog.parse(valid().toString(),1,1100);assertEquals(1,e.slot);assertTrue(e.valid(1100));assertEquals("US🇺🇸_01",BetaCatalog.label(1));}
    @Test public void rejectExpiredForeignAndWrongSlot()throws Exception{
        for(JSONObject j:new JSONObject[]{valid().put("expires_at",1090),valid().put("country","DE"),valid().put("slot",2),valid().put("schema",2),valid().put("issued_at",9000),valid().put("expires_at",999999),valid().put("uri",valid().getString("uri").replace("security=tls","security=none")),valid().put("uri",valid().getString("uri").replace("owned-fixture.trycloudflare.com","private.example"))}){
            try{BetaCatalog.parse(j.toString(),1,1100);fail("Invalid publication accepted");}catch(Exception expected){}
        }
    }
    @Test public void measuredBestPreferredFallbackAndExpiry()throws Exception{
        BetaCatalog.Entry a=BetaCatalog.parse(valid().toString(),1,1100);
        BetaCatalog.Entry b=BetaCatalog.parse(valid().put("slot",2).toString(),2,1100);
        List<BetaCatalog.Result> rows=Arrays.asList(new BetaCatalog.Result(a,90),new BetaCatalog.Result(b,40));
        assertEquals(2,BetaCatalog.choose(rows,0,1100).entry.slot);assertEquals(1,BetaCatalog.choose(rows,1,1100).entry.slot);
        assertEquals(2,BetaCatalog.choose(Arrays.asList(new BetaCatalog.Result(a,-1),new BetaCatalog.Result(b,40)),1,1100).entry.slot);
        assertNull(BetaCatalog.choose(rows,0,2000));assertNull(BetaCatalog.choose(Collections.emptyList(),0,1100));
    }
    @Test public void tenDistinctSourcesAndFixedLabels(){Set<String> sources=new HashSet<>();for(int i=1;i<=10;i++){sources.add(BetaCatalog.source(i));assertFalse(BetaCatalog.label(i).contains("github"));}assertEquals(10,sources.size());}
    @Test public void selectionIsAllowlisted()throws Exception{assertEquals(0,ManagedSettings.apply(new JSONObject().put("betaSlot",11)).getInt("betaSlot"));assertEquals(5,ManagedSettings.apply(new JSONObject().put("betaSlot",5)).getInt("betaSlot"));}
}
