package app.continuum;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import org.json.*;

/** Supported profiles, not a transport toggle that pretends to reconfigure a server. */
public final class Profile {
    public final String protocol,id,host,path,sni,wsHost,transport,cipher,password,label,fingerprint;
    public final int port;
    private Profile(String protocol,String id,String host,int port,String path,String sni,String wsHost,
                    String transport,String cipher,String password,String label,String fingerprint) {
        this.protocol=protocol;this.id=id;this.host=host;this.port=port;this.path=path;
        this.sni=sni;this.wsHost=wsHost;this.transport=transport;this.cipher=cipher;
        this.password=password;this.label=label;this.fingerprint=fingerprint;
    }
    public static Profile parse(String input) {
        try {
            if(input==null||input.length()>65536)throw new IllegalArgumentException();
            String text=input.trim();if(text.startsWith("vmess://"))return vmess(text);
            URI u=URI.create(text);String scheme=u.getScheme();
            if(!Set.of("vless","trojan","ss").contains(scheme))throw new IllegalArgumentException();
            String host=endpoint(u.getHost());int port=u.getPort();
            if(port<1||port>65535||u.getRawUserInfo()==null)throw new IllegalArgumentException();
            Map<String,String> q=query(u.getRawQuery());
            if("ss".equals(scheme)) {
                if(!q.isEmpty())throw new IllegalArgumentException();
                String credential=decode(u.getRawUserInfo());if(!credential.contains(":"))credential=base64(credential);
                int colon=credential.indexOf(':');if(colon<1||colon==credential.length()-1)throw new IllegalArgumentException();
                String method=credential.substring(0,colon),secret=credential.substring(colon+1);
                if(!Set.of("aes-128-gcm","aes-256-gcm","chacha20-ietf-poly1305").contains(method))throw new IllegalArgumentException();
                return new Profile("shadowsocks","",host,port,"/",host,host,"tcp",method,secret,label(u,"Shadowsocks"),"");
            }
            if(!Set.of("type","security","encryption","sni","host","path","fp").containsAll(q.keySet()))throw new IllegalArgumentException();
            String type=q.getOrDefault("type","tcp");if(!Set.of("tcp","ws").contains(type))throw new IllegalArgumentException();
            if(!"tls".equals(q.getOrDefault("security","trojan".equals(scheme)?"tls":"")))throw new IllegalArgumentException();
            String credential=decode(u.getRawUserInfo()),id="";
            if("vless".equals(scheme)) {
                id=UUID.fromString(credential).toString();
                if(!"none".equals(q.getOrDefault("encryption","none")))throw new IllegalArgumentException();
            }else if(credential.isEmpty()||q.containsKey("encryption"))throw new IllegalArgumentException();
            String path=validPath(q.getOrDefault("path","/"));
            if("tcp".equals(type)&&(q.containsKey("path")||q.containsKey("host")))throw new IllegalArgumentException();
            return new Profile(scheme,id,host,port,path,endpoint(q.getOrDefault("sni",host)),endpoint(q.getOrDefault("host",host)),
                type,"","trojan".equals(scheme)?credential:"",label(u,scheme.toUpperCase(Locale.ROOT)),validFingerprint(q.getOrDefault("fp","")));
        }catch(Exception ignored){throw new IllegalArgumentException("Unsupported or invalid profile. Credentials were not logged.");}
    }
    private static Profile vmess(String text)throws Exception {
        JSONObject v=new JSONObject(base64(text.substring(8)));
        Set<String> allowed=Set.of("v","ps","add","port","id","aid","scy","net","type","host","path","tls","sni","fp","alpn");
        Iterator<String> keys=v.keys();while(keys.hasNext())if(!allowed.contains(keys.next()))throw new IllegalArgumentException();
        if(v.optInt("aid",0)!=0||!"tls".equals(v.optString("tls"))||!Set.of("none","").contains(v.optString("type")))throw new IllegalArgumentException();
        String transport=v.optString("net","tcp"),cipher=v.optString("scy","auto");
        if(!Set.of("ws","tcp").contains(transport)||!Set.of("auto","aes-128-gcm","chacha20-poly1305").contains(cipher))throw new IllegalArgumentException();
        if(!Set.of("","http/1.1").contains(v.optString("alpn","")))throw new IllegalArgumentException();
        String host=endpoint(v.getString("add"));int port=Integer.parseInt(v.get("port").toString());
        if(port<1||port>65535)throw new IllegalArgumentException();
        String sni=v.optString("sni",host),wsHost=v.optString("host",host),path=v.optString("path","/");
        if(sni.isEmpty())sni=host;if(wsHost.isEmpty())wsHost=host;if(path.isEmpty())path="/";
        if("tcp".equals(transport)&&(!"/".equals(path)||!v.optString("host","").isEmpty()))throw new IllegalArgumentException();
        return new Profile("vmess",UUID.fromString(v.getString("id")).toString(),host,port,validPath(path),endpoint(sni),endpoint(wsHost),
            transport,cipher,"",safeLabel(v.optString("ps","VMess")),validFingerprint(v.optString("fp","")));
    }
    public static Profile subscription(String content){return parse(single(content));}
    public static String single(String content){
        if(content==null||content.length()>65536)throw new IllegalArgumentException("Subscription too large");
        String body=content.trim();if(!body.matches("(?s)^(vless|vmess|trojan|ss)://.*"))body=base64(body.replaceAll("\\s",""));
        String[] lines=body.trim().split("\\R");if(lines.length!=1)throw new IllegalArgumentException("Automatic rotation requires one authoritative profile");return lines[0];
    }
    private static String base64(String value){
        try{return new String(Base64.getDecoder().decode(value),StandardCharsets.UTF_8);}
        catch(IllegalArgumentException e){return new String(Base64.getUrlDecoder().decode(value),StandardCharsets.UTF_8);}
    }
    private static Map<String,String> query(String raw){
        Map<String,String> map=new HashMap<>();
        for(String part:(raw==null?"":raw).split("&")){
            if(part.isEmpty())continue;String[] p=part.split("=",2);
            if(map.put(decode(p[0]),p.length==2?decode(p[1]):"")!=null)throw new IllegalArgumentException();
        }return map;
    }
    private static String endpoint(String host){
        if(host==null||host.length()>253||host.chars().anyMatch(c->c<=32||c==127))throw new IllegalArgumentException();
        if(host.startsWith("[")&&host.endsWith("]"))host=host.substring(1,host.length()-1);
        if(host.contains(":")){if(!host.matches("[0-9a-fA-F:]+"))throw new IllegalArgumentException();}
        else if(!host.matches("(?i)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?"))throw new IllegalArgumentException();
        return host.toLowerCase(Locale.ROOT);
    }
    private static String validPath(String path){if(!path.startsWith("/")||path.length()>2048||path.chars().anyMatch(c->c<32||c==127))throw new IllegalArgumentException();return path;}
    private static String validFingerprint(String value){if(!Set.of("","chrome","firefox","safari","edge","ios","android").contains(value))throw new IllegalArgumentException();return value;}
    private static String safeLabel(String value){String clean=value.replaceAll("[\\p{Cntrl}]","");return clean.substring(0,Math.min(clean.length(),80));}
    private static String label(URI u,String fallback){return safeLabel(u.getRawFragment()==null?fallback:decode(u.getRawFragment()));}
    private static String decode(String s){try{return URLDecoder.decode(s.replace("+","%2B"),"UTF-8");}catch(java.io.UnsupportedEncodingException e){throw new AssertionError(e);}}
    public String protocolLabel(){return "shadowsocks".equals(protocol)?"Shadowsocks":protocol.toUpperCase(Locale.ROOT);}
    public String transportLabel(){return "shadowsocks".equals(protocol)?"TCP / UDP · AEAD":("ws".equals(transport)?"WebSocket":"TCP")+" · TLS";}
    public String key(){
        try{return Base64.getEncoder().encodeToString(MessageDigest.getInstance("SHA-256").digest(config(false).toString().getBytes(StandardCharsets.UTF_8)));}
        catch(Exception e){throw new IllegalStateException("Cannot identify profile");}
    }
    public JSONObject config(boolean tun)throws JSONException{
        JSONObject out=new JSONObject().put("tag","proxy").put("protocol",protocol),server=new JSONObject().put("address",host).put("port",port);
        if("vless".equals(protocol)||"vmess".equals(protocol)){
            JSONObject user=new JSONObject().put("id",id);
            if("vless".equals(protocol))user.put("encryption","none");else user.put("alterId",0).put("security",cipher);
            server.put("users",new JSONArray().put(user));out.put("settings",new JSONObject().put("vnext",new JSONArray().put(server)));
        }else{
            server.put("password",password);if("shadowsocks".equals(protocol))server.put("method",cipher);
            out.put("settings",new JSONObject().put("servers",new JSONArray().put(server)));
        }
        if(!"shadowsocks".equals(protocol)){
            JSONObject tls=new JSONObject().put("serverName",sni).put("allowInsecure",false);
            if(!fingerprint.isEmpty())tls.put("fingerprint",fingerprint);
            if("ws".equals(transport))tls.put("alpn",new JSONArray().put("http/1.1"));
            JSONObject stream=new JSONObject().put("network",transport).put("security","tls").put("tlsSettings",tls);
            if("ws".equals(transport))stream.put("wsSettings",new JSONObject().put("path",path).put("host",wsHost));out.put("streamSettings",stream);
        }
        JSONArray inbounds=new JSONArray();
        if(tun)inbounds.put(new JSONObject().put("tag","tun").put("protocol","tun").put("settings",new JSONObject().put("name","continuum").put("mtu",1500)));
        return new JSONObject().put("log",new JSONObject().put("loglevel","none")).put("inbounds",inbounds).put("outbounds",new JSONArray().put(out));
    }
}
