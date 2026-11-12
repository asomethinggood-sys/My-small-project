using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Text;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace Continuum;

public sealed record Profile(string Protocol, string Host, int Port, string Secret, string Label,
    string Transport = "tcp", string Sni = "", string WsHost = "", string Path = "/", string Cipher = "", string Fingerprint = "")
{
    public const string Invalid = "Unsupported or invalid profile. Use VLESS, VMess or Trojan with TCP/WS + TLS, or Shadowsocks AEAD.";
    static string Decode(string s) => Uri.UnescapeDataString(s);
    static string B64(string s) { s = Regex.Replace(s, @"\s", "").Replace('-', '+').Replace('_', '/'); return Encoding.UTF8.GetString(Convert.FromBase64String(s.PadRight((s.Length + 3) / 4 * 4, '='))); }
    static string Endpoint(string s)
    {
        s = s.Trim('[', ']');
        if (s.Length == 0 || s.Length > 253 || (!IPAddress.TryParse(s, out _) && !Regex.IsMatch(s, @"\A[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\z"))) throw new FormatException();
        return s;
    }
    static string LabelText(string s) => new string(s.Where(c => !char.IsControl(c)).Take(80).ToArray());
    static void Require(bool value) { if (!value) throw new FormatException(); }
    public static string Single(string body)
    {
        if (body.Length > 65536) throw new FormatException(Invalid);
        body = body.Trim();
        if (!Regex.IsMatch(body, @"\A(vless|vmess|trojan|ss)://")) body = B64(body);
        var lines = body.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
        if (lines.Length != 1) throw new FormatException("Automatic updates require one authoritative profile, not a server list.");
        Parse(lines[0]); return lines[0];
    }
    public static Profile Parse(string text)
    {
        try
        {
            Require(text.Length <= 65536);
            if (text.StartsWith("vmess://", StringComparison.Ordinal)) return Vmess(text[8..]);
            var u = new Uri(text.Trim());
            Require(new[] { "vless", "trojan", "ss" }.Contains(u.Scheme));
            Require(u.Port is > 0 and <= 65535 && u.UserInfo.Length > 0);
            Require(u.AbsolutePath is "" or "/");
            string host = Endpoint(u.Host), secret = Decode(u.UserInfo);
            var q = new Dictionary<string, string>();
            foreach (var item in u.Query.TrimStart('?').Split('&', StringSplitOptions.RemoveEmptyEntries))
            { var pair = item.Split('=', 2); q.Add(Decode(pair[0]), pair.Length == 2 ? Decode(pair[1]) : ""); }
            string label = LabelText(u.Fragment.Length > 1 ? Decode(u.Fragment[1..]) : u.Scheme.ToUpperInvariant());
            if (u.Scheme == "ss")
            {
                Require(q.Count == 0);
                if (!secret.Contains(':')) secret = B64(secret);
                var parts = secret.Split(':', 2);
                Require(parts.Length == 2 && parts[1].Length > 0 && new[] { "aes-128-gcm", "aes-256-gcm", "chacha20-ietf-poly1305" }.Contains(parts[0]));
                return new("shadowsocks", host, u.Port, parts[1], label, Cipher: parts[0]);
            }
            Require(q.Keys.All(k => new[] { "type", "security", "encryption", "sni", "host", "path", "fp" }.Contains(k)));
            var transport = q.GetValueOrDefault("type", "tcp");
            Require(transport is "tcp" or "ws");
            Require(q.GetValueOrDefault("security", u.Scheme == "trojan" ? "tls" : "") == "tls");
            if (u.Scheme == "vless") { secret = Guid.Parse(secret).ToString(); Require(q.GetValueOrDefault("encryption", "none") == "none"); }
            else Require(!q.ContainsKey("encryption"));
            Require(transport != "tcp" || (!q.ContainsKey("host") && !q.ContainsKey("path")));
            return Validate(new(u.Scheme, host, u.Port, secret, label, transport,
                Endpoint(q.GetValueOrDefault("sni", host)), Endpoint(q.GetValueOrDefault("host", host)),
                q.GetValueOrDefault("path", "/"), Fingerprint: q.GetValueOrDefault("fp", "")));
        }
        catch { throw new FormatException(Invalid); }
    }
    static Profile Vmess(string data)
    {
        var v = JsonNode.Parse(B64(data))!.AsObject();
        Require(v.All(p => new[] { "v", "ps", "add", "port", "id", "aid", "scy", "net", "type", "host", "path", "tls", "sni", "fp", "alpn" }.Contains(p.Key)));
        string Get(string k, string fallback = "") => v[k]?.ToString() is { Length: > 0 } s ? s : fallback;
        Require(Get("aid", "0") == "0" && Get("tls") == "tls" && Get("type") is "" or "none");
        Require(Get("alpn") is "" or "http/1.1");
        var transport = Get("net", "tcp"); var cipher = Get("scy", "auto");
        Require(transport is "ws" or "tcp");
        Require(new[] { "auto", "aes-128-gcm", "chacha20-poly1305" }.Contains(cipher));
        Require(transport != "tcp" || (Get("path", "/") == "/" && Get("host") == ""));
        string host = Endpoint(Get("add")); int port = int.Parse(Get("port")); Require(port is > 0 and <= 65535);
        return Validate(new("vmess", host, port, Guid.Parse(Get("id")).ToString(), LabelText(Get("ps", "VMess")), transport,
            Endpoint(Get("sni", host)), Endpoint(Get("host", host)), Get("path", "/"), cipher, Get("fp")));
    }
    static Profile Validate(Profile p)
    {
        Require(p.Path.StartsWith('/') && p.Path.Length <= 2048 && !p.Path.Any(char.IsControl));
        Require(new[] { "", "chrome", "firefox", "safari", "edge", "ios", "android" }.Contains(p.Fingerprint));
        return p;
    }
    public JsonObject Outbound()
    {
        var server = new JsonObject { ["address"] = Host, ["port"] = Port };
        var settings = new JsonObject();
        if (Protocol is "vless" or "vmess")
        {
            var user = new JsonObject { ["id"] = Secret };
            if (Protocol == "vless") user["encryption"] = "none";
            else { user["alterId"] = 0; user["security"] = Cipher; }
            server["users"] = new JsonArray(user); settings["vnext"] = new JsonArray(server);
        }
        else { server["password"] = Secret; if (Protocol == "shadowsocks") server["method"] = Cipher; settings["servers"] = new JsonArray(server); }
        var output = new JsonObject { ["tag"] = "proxy", ["protocol"] = Protocol, ["settings"] = settings };
        if (Protocol != "shadowsocks")
        {
            var tls = new JsonObject { ["serverName"] = Sni, ["allowInsecure"] = false };
            if (Fingerprint != "") tls["fingerprint"] = Fingerprint;
            if (Transport == "ws") tls["alpn"] = new JsonArray("http/1.1");
            var stream = new JsonObject { ["network"] = Transport, ["security"] = "tls", ["tlsSettings"] = tls };
            if (Transport == "ws") stream["wsSettings"] = new JsonObject { ["path"] = Path, ["host"] = WsHost };
            output["streamSettings"] = stream;
        }
        return output;
    }
    public JsonObject Config(bool tun, int port, int mtu = 1400)
    {
        if (mtu is not (1280 or 1400 or 1500)) throw new ArgumentException("Unsupported MTU");
        var inputs = new JsonArray(new JsonObject { ["tag"] = "health", ["listen"] = "127.0.0.1", ["port"] = port,
            ["protocol"] = "http", ["settings"] = new JsonObject() });
        if (tun) inputs.Add(new JsonObject { ["tag"] = "tun", ["protocol"] = "tun", ["settings"] = new JsonObject {
            ["name"] = "Continuum", ["desc"] = "Continuum VPN", ["mtu"] = mtu,
            ["gateway"] = new JsonArray("198.18.0.1/30", "fdfe:dcba:9876::1/126"),
            ["dns"] = new JsonArray("198.18.0.2"),
            ["autoSystemRoutingTable"] = new JsonArray("0.0.0.0/1", "128.0.0.0/1", "::/1", "8000::/1"),
            ["autoOutboundsInterface"] = "auto", ["autoSystemWfpBlockLeak"] = new JsonArray("dns", "misconfigtun")
        }, ["sniffing"] = new JsonObject { ["enabled"] = true, ["destOverride"] = new JsonArray("http", "tls"), ["routeOnly"] = false } });
        return new JsonObject {
            ["log"] = new JsonObject { ["loglevel"] = "none" }, ["inbounds"] = inputs,
            ["dns"] = new JsonObject { ["servers"] = new JsonArray("https://1.1.1.1/dns-query"), ["queryStrategy"] = "UseIPv4" },
            ["outbounds"] = new JsonArray(Outbound(), new JsonObject { ["tag"] = "dns", ["protocol"] = "dns", ["settings"] = new JsonObject { ["nonIPQuery"] = "drop" } }),
            ["routing"] = new JsonObject { ["domainStrategy"] = "AsIs", ["rules"] = new JsonArray(new JsonObject {
                ["type"] = "field", ["inboundTag"] = new JsonArray("tun"), ["port"] = "53", ["outboundTag"] = "dns" }) }
        };
    }
}
