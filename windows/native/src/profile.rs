use base64::{engine::general_purpose::{STANDARD, STANDARD_NO_PAD, URL_SAFE_NO_PAD}, Engine};
use serde_json::{json, Value};
use std::collections::BTreeMap;
use url::Url;

pub const SOURCE: &str = "https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt";
fn decode(s: &str) -> Result<String, ()> {
    let s: String = s.chars().filter(|c| !c.is_whitespace()).collect();
    String::from_utf8(STANDARD.decode(&s).or_else(|_| STANDARD_NO_PAD.decode(&s)).or_else(|_| URL_SAFE_NO_PAD.decode(&s)).map_err(|_| ())?).map_err(|_| ())
}
fn unescape(s: &str) -> Result<String, ()> {
    percent_encoding::percent_decode_str(s).decode_utf8().map(|s| s.into_owned()).map_err(|_| ())
}
fn uuid(s: &str) -> bool {
    s.len() == 36 && s.bytes().enumerate().all(|(i,b)| if [8,13,18,23].contains(&i) { b == b'-' } else { b.is_ascii_hexdigit() })
}
fn host(s: &str) -> bool { !s.is_empty() && s.len() <= 253 && s.chars().all(|c| c.is_ascii_alphanumeric() || ".-:[]".contains(c)) }
pub fn parse(body: &str) -> Result<Value, ()> {
    if body.len() > 65536 { return Err(()); }
    let raw = if ["vless://", "vmess://", "trojan://", "ss://"].iter().any(|s| body.trim().starts_with(s)) { body.trim().to_string() } else { decode(body)? };
    let lines: Vec<_> = raw.lines().filter(|s| !s.trim().is_empty()).collect();
    if lines.len() != 1 { return Err(()); }
    let raw = lines[0].trim();
    if let Some(encoded) = raw.strip_prefix("vmess://") {
        let v: Value = serde_json::from_str(&decode(encoded)?).map_err(|_| ())?;
        let get = |k: &str, default: &str| -> String { v.get(k).map(|s| s.as_str().map(str::to_owned).unwrap_or_else(|| s.to_string())).unwrap_or_else(|| default.to_string()) };
        let id = get("id", ""); let h = get("add", ""); let port: u16 = get("port", "0").parse().map_err(|_| ())?;
        let net = get("net", "tcp"); let cipher = get("scy", "auto");
        if !uuid(&id) || !host(&h) || port == 0 || get("tls", "") != "tls" || get("aid", "0") != "0" || !["auto","aes-128-gcm","chacha20-poly1305"].contains(&cipher.as_str()) { return Err(()); }
        let allowed = ["v","ps","add","port","id","aid","scy","net","type","host","path","tls","sni","fp","alpn"];
        if !v.as_object().ok_or(())?.keys().all(|k| allowed.contains(&k.as_str())) || !["","none"].contains(&get("type", "").as_str()) || !["","http/1.1"].contains(&get("alpn", "").as_str()) { return Err(()); }
        let mut out = json!({"tag":"proxy","protocol":"vmess","settings":{"vnext":[{"address":h,"port":port,"users":[{"id":id,"security":cipher,"level":0}]}]}});
        out["streamSettings"] = stream(&net, &get("sni", &h), &get("host", &h), &get("path", "/"), &get("fp", ""))?;
        return Ok(out);
    }
    let u = Url::parse(raw).map_err(|_| ())?;
    let protocol = u.scheme(); let h = u.host_str().ok_or(())?; let port = u.port().ok_or(())?;
    if !host(h) || port == 0 || !["", "/"].contains(&u.path()) { return Err(()); }
    let mut q = BTreeMap::new();
    for (k,v) in u.query_pairs() { if q.insert(k.to_string(), v.to_string()).is_some() { return Err(()); } }
    if !q.keys().all(|k| ["type","security","encryption","sni","host","path","fp"].contains(&k.as_str())) { return Err(()); }
    let mut secret = unescape(u.username())?;
    if let Some(p) = u.password() { secret.push(':'); secret.push_str(&unescape(p)?); }
    let settings;
    if protocol == "ss" {
        if !q.is_empty() { return Err(()); }
        if !secret.contains(':') { secret = decode(&secret)?; }
        let (cipher, password) = secret.split_once(':').ok_or(())?;
        if !["aes-128-gcm","aes-256-gcm","chacha20-ietf-poly1305"].contains(&cipher) || password.is_empty() { return Err(()); }
        return Ok(json!({"tag":"proxy","protocol":"shadowsocks","settings":{"servers":[{"address":h,"port":port,"method":cipher,"password":password,"level":0}]}}));
    } else if protocol == "vless" {
        if !uuid(&secret) || q.get("encryption").map_or(false, |v| v != "none") { return Err(()); }
        settings = json!({"vnext":[{"address":h,"port":port,"users":[{"id":secret,"encryption":"none","level":0}]}]});
    } else if protocol == "trojan" && !secret.is_empty() && !q.contains_key("encryption") {
        settings = json!({"servers":[{"address":h,"port":port,"password":secret,"level":0}]});
    } else { return Err(()); }
    let get = |k: &str, default: &str| q.get(k).cloned().unwrap_or_else(|| default.to_string());
    if get("security", if protocol == "trojan" {"tls"} else {""}) != "tls" { return Err(()); }
    Ok(json!({"tag":"proxy","protocol":protocol,"settings":settings,
        "streamSettings":stream(&get("type","tcp"), &get("sni",h), &get("host",h), &get("path","/"), &get("fp",""))?}))
}
fn stream(net: &str, sni: &str, h: &str, path: &str, fp: &str) -> Result<Value, ()> {
    if !["tcp","ws"].contains(&net) || !host(sni) || !host(h) || !path.starts_with('/') || path.len() > 2048 || path.chars().any(char::is_control) || !["","chrome","firefox","safari","edge","ios","android"].contains(&fp) { return Err(()); }
    let mut s = json!({"network":net,"security":"tls","tlsSettings":{"serverName":sni,"allowInsecure":false},"sockopt":{"tcpKeepAliveIdle":30,"tcpKeepAliveInterval":15}});
    if !fp.is_empty() { s["tlsSettings"]["fingerprint"] = json!(fp); }
    if net == "ws" { s["wsSettings"] = json!({"host":h,"path":path}); }
    Ok(s)
}
pub fn config(outbound: &Value, port: u16, scoped: bool) -> Value {
    json!({
        "log":{"loglevel":"none"},
        "policy":{"levels":{"0":{"handshake":10,"connIdle":600,"uplinkOnly":30,"downlinkOnly":30,"bufferSize":64}}},
        "inbounds":[{"tag":"health","listen":"127.0.0.1","port":port,"protocol":"http","settings":{}},
            {"tag":"tun","protocol":"tun","settings":{"name":"Continuum","desc":"Continuum VPN","mtu":1280,
                "gateway":["198.18.0.1/30","fdfe:dcba:9876::1/126"],"dns":["198.18.0.2"],
                "autoSystemRoutingTable":if scoped {vec!["198.18.0.0/15"]} else {vec!["0.0.0.0/1","128.0.0.0/1","::/1","8000::/1"]},
                "autoOutboundsInterface":"auto","autoSystemWfpBlockLeak":if scoped {vec![]} else {vec!["dns","misconfigtun"]}},
             "sniffing":{"enabled":true,"destOverride":["http","tls"],"routeOnly":true}}],
        "dns":{"servers":[{"address":"https://1.1.1.1/dns-query","timeoutMs":4000},{"address":"https://8.8.8.8/dns-query","timeoutMs":4000}],"tag":"dns-query","queryStrategy":"UseIPv4","disableCache":false,"serveStale":false,"enableParallelQuery":true},
        "outbounds":[outbound,{"tag":"dns","protocol":"dns","settings":{}},{"tag":"no-quic","protocol":"blackhole","settings":{}}],
        "routing":{"domainStrategy":"AsIs","rules":[
            {"type":"field","inboundTag":["tun"],"port":"53","network":"tcp,udp","outboundTag":"dns"},
            {"type":"field","inboundTag":["dns-query"],"outboundTag":"proxy"},
            {"type":"field","inboundTag":["tun"],"port":"443","network":"udp","outboundTag":"no-quic"}]}
    })
}
/// A publication is not evidence that an active call should be disconnected.
/// Only fail over after repeated failed probes AND an actually different peer.
pub fn replace(running: bool, failures: u32, current: &Value, next: &Value) -> bool {
    !running || (failures >= 3 && current != next)
}
#[cfg(test)] mod tests {
    use super::*;
    const LINK: &str = "vless://f2222222-2222-4222-8222-222222222222@example.com:443?type=ws&security=tls&path=%2Fx#Label";
    #[test] fn labels_do_not_change_identity() { assert_eq!(parse(LINK), parse(&LINK.replace("Label","Other"))); }
    #[test] fn reject_unsafe_input() {
        for s in [LINK.replace("tls","none"), LINK.replace("f2222222","invalid"), LINK.replace("#Label","&security=none"), format!("{LINK}\n{LINK}"), LINK.replace("#Label","&allowInsecure=1")] { assert!(parse(&s).is_err()); }
    }
    #[test] fn preserve_calls_during_publication_and_probes() {
        let a=parse(LINK).unwrap();let b=parse(&LINK.replace("example.com","other.example.com")).unwrap();
        for _ in 0..100 { assert!(!replace(true,0,&a,&b)); }
        assert!(!replace(true,100,&a,&a));assert!(!replace(true,2,&a,&b));assert!(replace(true,3,&a,&b));assert!(replace(false,0,&a,&a));
    }
    #[test] fn routing_keeps_voice_and_avoids_cdn_rewrite() {
        let c=config(&parse(LINK).unwrap(),23082,false);
        assert_eq!(c["inbounds"][1]["sniffing"]["routeOnly"],true);
        assert_eq!(c["policy"]["levels"]["0"]["connIdle"],600);
        assert_eq!(c["routing"]["rules"][2]["port"],"443");
        assert_eq!(c["routing"]["rules"][2]["network"],"udp");
        assert!(c["outbounds"].as_array().unwrap().iter().all(|v|v["protocol"]!="freedom"));
        assert_eq!(c["dns"]["enableParallelQuery"],true);
    }
}
