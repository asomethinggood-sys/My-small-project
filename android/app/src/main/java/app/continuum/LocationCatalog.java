package app.continuum;

import org.json.*;
import java.util.*;

/** Public metadata only. This type deliberately cannot produce a connection profile. */
public final class LocationCatalog {
    public static final String TARGETS="US CA MX BR AR GB IE FR DE NL BE CH AT IT ES PT SE NO DK FI PL CZ RO TR JP KR SG IN AU NZ";
    public static final Set<String> PROVIDERS=Set.of("vpngate","vpnbook","cloudflare","psiphon","proton","riseup","tor");
    public static final class Exit {
        public final String provider,type,udp;
        public final int discovered,advertised;
        Exit(JSONObject j)throws JSONException{
            provider=j.getString("provider");type=j.getString("type");udp=j.optString("udp","unverified");
            if(!PROVIDERS.contains(provider)||!Set.of("openvpn","wireguard","warp","psiphon","socks_tcp").contains(type))throw new JSONException("Unknown adapter");
            discovered=count(j,"discovered_servers");advertised=count(j,"advertised_endpoints");
        }
    }
    public static final class Country {
        public final String code;
        public final int discovered,providers,advertised;
        public final List<Exit> exits;
        Country(JSONObject j)throws JSONException{
            code=j.getString("country");discovered=count(j,"discovered_servers");providers=count(j,"discovered_providers");advertised=count(j,"advertised_endpoints");
            if(!Arrays.asList(TARGETS.split(" ")).contains(code))throw new JSONException("Unknown country");
            JSONArray a=j.optJSONArray("exits");List<Exit> rows=new ArrayList<>();
            if(a!=null){if(a.length()>16)throw new JSONException("Too many adapters");for(int i=0;i<a.length();i++)rows.add(new Exit(a.getJSONObject(i)));}
            exits=Collections.unmodifiableList(rows);
        }
    }
    public final long generated,expires;
    public final Map<String,Country> countries;
    private LocationCatalog(long g,long e,Map<String,Country> c){generated=g;expires=e;countries=Collections.unmodifiableMap(c);}
    private static int count(JSONObject j,String key)throws JSONException{
        Object v=j.opt(key);if(v==null)return 0;
        if(!(v instanceof Integer)||((Integer)v)<0||((Integer)v)>10000)throw new JSONException("Invalid count");return (Integer)v;
    }
    public static LocationCatalog parse(String text)throws JSONException{
        if(text.length()>1048576)throw new JSONException("Oversized metadata");
        JSONObject j=new JSONObject(text);
        if(j.getInt("schema_version")!=1||!"research_metadata_not_connection_profiles".equals(j.getString("purpose")))throw new JSONException("Unsupported catalog");
        long g=j.getLong("generated_at"),e=j.getLong("expires_at");
        if(g<=0||e<=g||e-g>900)throw new JSONException("Invalid lifetime");
        JSONArray rows=j.getJSONArray("countries");if(rows.length()>30)throw new JSONException("Too many countries");
        Map<String,Country> result=new LinkedHashMap<>();
        for(int i=0;i<rows.length();i++){Country c=new Country(rows.getJSONObject(i));if(result.put(c.code,c)!=null)throw new JSONException("Duplicate country");}
        return new LocationCatalog(g,e,result);
    }
    public boolean fresh(long now){return RustCore.exitEligibility(now,generated,expires,0,1)==1;}
    public String status(Country c,long now){
        // Never trust remote selectable/verified fields to authorize routing.
        int p=RustCore.exitEligibility(now,generated,expires,0,c.discovered+c.advertised>0?1:0);
        return p==2?"Snapshot expired":p==1?"Discovered · not available":"No eligible exit";
    }
}
