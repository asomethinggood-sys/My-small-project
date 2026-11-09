package app.continuum;

import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import javax.net.ssl.HttpsURLConnection;
import org.json.*;

/** Credential-bearing control channel: certificate-verified HTTPS, no redirects. */
public final class CountryClient {
    interface Transport {JSONObject request(String method,String path,JSONObject body)throws Exception;}
    public static final class Source {
        public final String origin,user;
        private final String key;
        public Source(JSONObject settings)throws Exception{
            URI uri=new URI(settings.getString("countryService"));
            if(!"https".equals(uri.getScheme())||uri.getHost()==null||uri.getUserInfo()!=null||uri.getQuery()!=null||uri.getFragment()!=null||!(uri.getPath().isEmpty()||uri.getPath().equals("/"))||(uri.getPort()!=-1&&uri.getPort()!=443))throw new IllegalArgumentException("HTTPS service origin required");
            origin="https://"+uri.getHost().toLowerCase(Locale.ROOT);user=settings.getString("countryUser");key=settings.getString("countryKey");
            if(!user.matches("[a-z0-9_-]{1,48}")||!key.matches("[A-Za-z0-9_-]{43,128}"))throw new IllegalArgumentException("Provisioned credentials required");
        }
    }
    public static final class Lease {
        public final String country,uri;
        public final long deadline,generation;
        private final String token;
        Lease(String c,String u,String t,long g,long d){country=c;uri=u;token=t;generation=g;deadline=d;}
    }
    public static final class Available {
        public final String country;
        public final int pools,providers;
        public final long deadline;
        public final List<String> providerNames,protocols;
        Available(String c,int p,int v,long d,List<String> names,List<String> types){country=c;pools=p;providers=v;deadline=d;providerNames=Collections.unmodifiableList(names);protocols=Collections.unmodifiableList(types);}
    }
    private final Source source;
    private final Transport transport;
    private volatile HttpsURLConnection current;
    private volatile boolean cancelled;
    public CountryClient(Source s){source=s;transport=this::request;}
    CountryClient(Source s,Transport t){source=s;transport=t;}
    public void cancel(){cancelled=true;HttpsURLConnection c=current;if(c!=null)c.disconnect();}
    public static String binding(JSONObject settings)throws Exception{
        Source s=new Source(settings);String country=settings.optString("country","");
        byte[] hash=MessageDigest.getInstance("SHA-256").digest((s.origin+"\n"+s.user+"\n"+s.key+"\n"+country).getBytes(StandardCharsets.UTF_8));
        return Base64.getEncoder().encodeToString(hash);
    }
    private static long number(JSONObject j,String name,long min,long max)throws Exception{
        Object value=j.get(name);if(!(value instanceof Integer||value instanceof Long))throw new IllegalArgumentException("Integer required");
        long n=((Number)value).longValue();if(n<min||n>max)throw new IllegalArgumentException("Value out of bounds");return n;
    }
    public Lease acquire(String country,long started)throws Exception{
        if(!Arrays.asList(LocationCatalog.TARGETS.split(" ")).contains(country))throw new IllegalArgumentException("Country required");
        JSONObject reply=transport.request("POST","/v1/sessions",new JSONObject().put("country",country).put("require_udp",true));
        String token=reply.getString("token");long generation=number(reply,"generation",1,Long.MAX_VALUE),ttl=number(reply,"expires_in",1,300);
        if(!token.matches("[A-Za-z0-9_-]{43}")||!country.equals(reply.getString("country")))throw new IllegalArgumentException("Mismatched lease");
        String uri=reply.getString("profile");Profile p=Profile.parse(uri);String host=new URI(source.origin).getHost();
        if(!p.protocol.equals("vless")||!p.transport.equals("ws")||p.port!=443||!p.host.equals(host)||!p.sni.equals(host)||!p.wsHost.equals(host)||!p.path.equals("/s/"+token+"/"+generation))throw new IllegalArgumentException("Profile is not bound to this service lease");
        if(started<0||started>Long.MAX_VALUE-300000)throw new IllegalArgumentException("Invalid monotonic clock");
        return new Lease(country,uri,token,generation,started+ttl*1000);
    }
    private static List<String> labels(JSONArray rows)throws Exception{
        if(rows.length()<1||rows.length()>128)throw new IllegalArgumentException("Invalid breakdown");
        List<String> result=new ArrayList<>();for(int i=0;i<rows.length();i++){String name=rows.getString(i);if(!name.matches("[a-z0-9_-]{1,48}")||result.contains(name))throw new IllegalArgumentException("Invalid breakdown");result.add(name);}return result;
    }
    public List<Available> availability(long started)throws Exception{
        JSONObject reply=transport.request("GET","/v1/availability",null);
        if(number(reply,"schema_version",1,1)!=1||!"authenticated_live_availability".equals(reply.getString("purpose")))throw new IllegalArgumentException("Wrong catalog");
        JSONArray rows=reply.getJSONArray("countries");if(rows.length()>30)throw new IllegalArgumentException("Too many countries");
        Set<String> seen=new HashSet<>();List<Available> result=new ArrayList<>();
        for(int i=0;i<rows.length();i++){
            JSONObject row=rows.getJSONObject(i);String code=row.getString("country");
            if(!Arrays.asList(LocationCatalog.TARGETS.split(" ")).contains(code)||!seen.add(code)||!Boolean.TRUE.equals(row.get("udp")))throw new IllegalArgumentException("Invalid availability");
            int pools=(int)number(row,"pool_count",1,128),providers=(int)number(row,"provider_count",1,128);long ttl=number(row,"expires_in",1,300);
            if(providers>pools||started<0||started>Long.MAX_VALUE-300000)throw new IllegalArgumentException("Invalid availability counts");
            List<String> names=labels(row.getJSONArray("providers")),types=labels(row.getJSONArray("protocols"));if(names.size()!=providers)throw new IllegalArgumentException("Provider count mismatch");
            result.add(new Available(code,pools,providers,started+ttl*1000,names,types));
        }
        return result;
    }
    public void release(Lease lease)throws Exception{transport.request("POST","/v1/disconnect",new JSONObject().put("token",lease.token));}
    private JSONObject request(String method,String path,JSONObject body)throws Exception{
        if(cancelled)throw new IOException("Cancelled");
        HttpsURLConnection c=(HttpsURLConnection)new URL(source.origin+path).openConnection();current=c;
        try{
            c.setRequestMethod(method);c.setConnectTimeout(6000);c.setReadTimeout(6000);c.setInstanceFollowRedirects(false);c.setUseCaches(false);
            c.setRequestProperty("Authorization","Bearer "+source.key);c.setRequestProperty("X-Nyx-User",source.user);c.setRequestProperty("Accept","application/json");
            if(body!=null){byte[] bytes=body.toString().getBytes(StandardCharsets.UTF_8);c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json");c.setFixedLengthStreamingMode(bytes.length);try(OutputStream out=c.getOutputStream()){out.write(bytes);}}
            if(cancelled||c.getResponseCode()/100!=2||c.getContentLengthLong()>65536)throw new IOException("Country service unavailable");
            try(InputStream in=c.getInputStream();ByteArrayOutputStream out=new ByteArrayOutputStream()){
                byte[] b=new byte[4096];int n;long start=System.nanoTime();
                while((n=in.read(b))!=-1){if(cancelled||out.size()+n>65536||System.nanoTime()-start>12_000_000_000L)throw new IOException("Response budget exceeded");out.write(b,0,n);}
                return new JSONObject(out.toString(StandardCharsets.UTF_8.name()));
            }
        }finally{c.disconnect();if(current==c)current=null;}
    }
}
