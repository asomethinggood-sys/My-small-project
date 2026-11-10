package app.continuum;

import org.json.*;

/** Android TUN policy, kept separate from the user's immutable server profile. */
public final class NetworkConfig {
    private NetworkConfig(){}
    public static final String DNS_ADDRESS="172.30.0.1";
    public static int mtu(JSONObject settings){int n=settings.optInt("mtu",1400);return n==1280||n==1400||n==1500?n:1400;}
    public static boolean dualStack(JSONObject settings){return settings.optBoolean("dualStack",false);}
    public static String identity(JSONObject settings){return mtu(settings)+":"+dualStack(settings);}
    public static JSONObject tunnel(Profile profile,JSONObject settings)throws JSONException{
        JSONObject config=profile.config(true);
        JSONObject inbound=config.getJSONArray("inbounds").getJSONObject(0);
        inbound.getJSONObject("settings").put("mtu",mtu(settings));
        // Recover the HTTP Host / TLS SNI for remote resolution instead of forwarding
        // an ISP-poisoned or stale cached destination IP. Never decrypt TLS.
        inbound.put("sniffing",new JSONObject().put("enabled",true).put("routeOnly",false)
            .put("destOverride",new JSONArray().put("http").put("tls")));
        // Plain UDP DNS through a proxy is unreliable on some server/firewall paths.
        // Terminate port 53 inside Xray and resolve over certificate-verified DoH
        // through the proxy (not https+local and not a direct/freedom outbound).
        JSONArray servers=new JSONArray()
            .put(new JSONObject().put("address","https://1.1.1.1/dns-query").put("timeoutMs",4000))
            .put(new JSONObject().put("address","https://dns.google/dns-query").put("timeoutMs",4000));
        config.put("dns",new JSONObject().put("servers",servers).put("tag","dns-query")
            .put("queryStrategy",dualStack(settings)?"UseIP":"UseIPv4")
            .put("disableCache",false).put("serveStale",false).put("enableParallelQuery",false));
        config.getJSONArray("outbounds").put(new JSONObject().put("tag","dns-out").put("protocol","dns")
            .put("settings",new JSONObject()));
        config.put("routing",new JSONObject().put("domainStrategy","AsIs").put("rules",new JSONArray()
            .put(new JSONObject().put("type","field").put("inboundTag",new JSONArray().put("tun"))
                .put("port","53").put("network","tcp,udp").put("outboundTag","dns-out"))
            .put(new JSONObject().put("type","field").put("inboundTag",new JSONArray().put("dns-query"))
                .put("outboundTag","proxy"))));
        return config;
    }
}
