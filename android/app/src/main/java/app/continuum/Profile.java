package app.continuum;

import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** Strict allowlist for this project's VLESS+WS+TLS profiles, not a generic importer. */
public final class Profile {
    public final String id, host, path, sni, wsHost;
    public final int port;
    private Profile(String id, String host, int port, String path, String sni, String wsHost) {
        this.id=id; this.host=host; this.port=port; this.path=path; this.sni=sni; this.wsHost=wsHost;
    }
    public static Profile parse(String text) {
        URI uri = URI.create(text.trim());
        if (!"vless".equals(uri.getScheme()) || uri.getUserInfo()==null) throw new IllegalArgumentException("Only VLESS profiles are supported");
        String id = UUID.fromString(uri.getUserInfo()).toString();
        String host = dns(uri.getHost());
        int port = uri.getPort();
        if (port<1 || port>65535) throw new IllegalArgumentException("Invalid server port");
        Map<String,String> q = new HashMap<>();
        for (String pair : Objects.requireNonNullElse(uri.getRawQuery(), "").split("&")) {
            if (pair.isEmpty()) continue;
            String[] kv = pair.split("=",2);
            String k=decode(kv[0]), v=kv.length==2?decode(kv[1]):"";
            if (q.put(k,v)!=null) throw new IllegalArgumentException("Duplicate profile option");
        }
        Set<String> allowed=Set.of("type","security","encryption","sni","host","path");
        if (!allowed.containsAll(q.keySet())) throw new IllegalArgumentException("Unsupported profile option; nothing was changed");
        if (!"ws".equals(q.get("type")) || !"tls".equals(q.get("security")) || !"none".equals(q.get("encryption")))
            throw new IllegalArgumentException("This server requires VLESS / WebSocket / TLS");
        String path=q.getOrDefault("path","/");
        if (!path.startsWith("/") || path.length()>2048 || path.chars().anyMatch(c->c<32 || c==127))
            throw new IllegalArgumentException("Invalid WebSocket path");
        return new Profile(id,host,port,path,dns(q.getOrDefault("sni",host)),dns(q.getOrDefault("host",host)));
    }
    public static Profile subscription(String content) {
        if (content.length()>65536) throw new IllegalArgumentException("Subscription is too large");
        String body=content.trim();
        if (!body.startsWith("vless://")) {
            try { body=new String(Base64.getDecoder().decode(body.replaceAll("\\s", "")),StandardCharsets.UTF_8).trim(); }
            catch (Exception e) { throw new IllegalArgumentException("Invalid subscription encoding"); }
        }
        // Do not silently pick an arbitrary profile from a multi-server subscription.
        String[] lines=body.split("\\R");
        if (lines.length!=1) throw new IllegalArgumentException("Use a single-profile subscription for automatic rotation");
        return parse(lines[0]);
    }
    static String dns(String host) {
        if (host==null || host.length()>253 || !host.matches("(?i)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\\.)+[a-z]{2,63}"))
            throw new IllegalArgumentException("Expected a DNS hostname");
        return host.toLowerCase(Locale.ROOT);
    }
    static String decode(String s) { return URLDecoder.decode(s, StandardCharsets.UTF_8); }
    public String key() { return id+"|"+host+"|"+port+"|"+path+"|"+sni+"|"+wsHost; }
    public JSONObject config(boolean tun) throws JSONException {
        JSONObject stream=new JSONObject().put("network","ws").put("security","tls")
            .put("tlsSettings",new JSONObject().put("serverName",sni).put("allowInsecure",false))
            .put("wsSettings",new JSONObject().put("path",path).put("host",wsHost));
        JSONObject server=new JSONObject().put("address",host).put("port",port).put("users",new JSONArray().put(
            new JSONObject().put("id",id).put("encryption","none")));
        JSONObject outbound=new JSONObject().put("tag","proxy").put("protocol","vless")
            .put("settings",new JSONObject().put("vnext",new JSONArray().put(server))).put("streamSettings",stream);
        JSONArray inbounds=new JSONArray();
        if (tun) inbounds.put(new JSONObject().put("tag","tun").put("protocol","tun")
            .put("settings",new JSONObject().put("name","continuum").put("mtu",1500)));
        // No freedom/direct fallback. All device traffic entering TUN uses this outbound.
        return new JSONObject().put("log",new JSONObject().put("loglevel","none"))
            .put("inbounds",inbounds).put("outbounds",new JSONArray().put(outbound));
    }
}
