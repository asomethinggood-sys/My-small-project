using Continuum;
using System.IO;
using System.Net;
using System.Net.Http;
using System.Text;
using System.Text.Json.Nodes;

int count = 0;
void Test(string name, Action action) { action(); count++; Console.WriteLine("PASS " + name); }
void Assert(bool value) { if (!value) throw new Exception("Assertion failed"); }
void Reject(Action action) { try { action(); } catch (FormatException) { return; } throw new Exception("Invalid input accepted"); }
string id = "f2222222-2222-4222-8222-222222222222";
string vless = $"vless://{id}@example.com:443?security=tls&type=ws&host=example.com&path=%2Fhello#Sample";
Test("VLESS WS TLS preserves endpoint and path", () => { var p = Profile.Parse(vless); Assert(p.Path == "/hello" && p.Transport == "ws" && p.Sni == "example.com"); });
Test("Trojan TCP TLS", () => Assert(Profile.Parse("trojan://test-password@example.com:443").Protocol == "trojan"));
Test("Shadowsocks SIP002", () => Assert(Profile.Parse("ss://" + Convert.ToBase64String(Encoding.UTF8.GetBytes("aes-128-gcm:test-password")) + "@127.0.0.1:12345#Test").Cipher == "aes-128-gcm"));
Test("VMess TLS", () => {
    var body = new JsonObject { ["add"] = "example.com", ["port"] = "443", ["id"] = id, ["tls"] = "tls", ["net"] = "ws", ["path"] = "/", ["aid"] = "0" };
    Assert(Profile.Parse("vmess://" + Convert.ToBase64String(Encoding.UTF8.GetBytes(body.ToJsonString()))).Protocol == "vmess");
});
Test("Reject TLS downgrade, arbitrary extensions, invalid UUID and ambiguous query", () => {
    foreach (var uri in new[] { vless.Replace("tls", "none"), vless + "&allowInsecure=1", $"vless://not-a-uuid@example.com:443?security=tls", $"vless://{id}@example.com:443?security=tls&security=none", vless.Replace("type=ws", "type=grpc") })
    {
        // Put unknown query before the fragment so it cannot be merely a label.
        Reject(() => Profile.Parse(uri.Replace("#Sample&allowInsecure=1", "&allowInsecure=1#Sample")));
    }
});
Test("Authoritative subscription supports base64 but rejects multiple profiles", () => {
    Assert(Profile.Single(Convert.ToBase64String(Encoding.UTF8.GetBytes(vless))) == vless);
    Reject(() => Profile.Single(vless + "\n" + vless)); Reject(() => Profile.Single(new string('a', 65537)));
});
Test("TUN includes IPv4 IPv6 routing, WFP DNS guards and explicit outbound interface", () => {
    var c = Profile.Parse(vless).Config(true, 23456);
    var s = c["inbounds"]![1]!["settings"]!;
    Assert(s["autoSystemRoutingTable"]!.AsArray().Count == 4 && s["autoOutboundsInterface"]!.ToString() == "auto");
    Assert(s["autoSystemWfpBlockLeak"]!.AsArray().Count == 2);
    Assert(c["outbounds"]![0]!["streamSettings"]!["tlsSettings"]!["allowInsecure"]!.GetValue<bool>() == false);
    Assert(c["dns"]!["servers"]![0]!.ToString().StartsWith("https://"));
});
Test("No direct outbound or external listener", () => {
    var c = Profile.Parse(vless).Config(false, 23456);
    Assert(c["inbounds"]!.AsArray().Count == 1 && c["inbounds"]![0]!["listen"]!.ToString() == "127.0.0.1");
    Assert(c["outbounds"]!.AsArray().All(o => o!["protocol"]!.ToString() != "freedom"));
});
var calls = new List<HttpRequestMessage>();
var handler = new Stub(async (request, token) => {
    calls.Add(request);
    if (calls.Count == 1) return new HttpResponseMessage(HttpStatusCode.Redirect) { Headers = { Location = new Uri("https://other.example/config") } };
    if (calls.Count == 2) return new HttpResponseMessage(HttpStatusCode.OK) { Content = new StringContent(vless), Headers = { ETag = new System.Net.Http.Headers.EntityTagHeaderValue("\"v1\"") } };
    await Task.Yield();
    return new HttpResponseMessage(HttpStatusCode.NotModified);
});
using (var sub = new Subscription(handler)) {
    Assert(await sub.FetchAsync("https://example.com/config", CancellationToken.None) == vless);
    Assert(await sub.FetchAsync("https://other.example/config", CancellationToken.None) == vless);
    Assert(!calls[0].Headers.Contains("If-None-Match") && !calls[1].Headers.Contains("If-None-Match") && calls[2].Headers.Contains("If-None-Match"));
    count++; Console.WriteLine("PASS Subscription redirect and exact-resource validators");
}
using (var sub = new Subscription(new Stub((_, _) => Task.FromResult(new HttpResponseMessage(HttpStatusCode.Redirect) { Headers = { Location = new Uri("http://example.com/config") } })))) {
    try { await sub.FetchAsync("https://example.com/config", CancellationToken.None); throw new Exception("Downgrade accepted"); }
    catch (InvalidOperationException) { count++; Console.WriteLine("PASS Reject HTTPS downgrade"); }
}
Console.WriteLine($"{count} tests passed");
if (args.Contains("--write-fixture")) {
    var profile = Profile.Parse("ss://" + Convert.ToBase64String(Encoding.UTF8.GetBytes("aes-128-gcm:continuum-ci-only-password")) + "@127.0.0.1:23081#LocalFixture");
    Directory.CreateDirectory("fixture");
    File.WriteAllText("fixture/client.json", profile.Config(false, 23082).ToJsonString());
    File.WriteAllText("fixture/full-tun.json", profile.Config(true, 23082).ToJsonString());
    var tun = profile.Config(true, 23082);
    var tunSettings = tun["inbounds"]![1]!["settings"]!;
    tunSettings["autoSystemRoutingTable"] = new JsonArray("198.18.0.0/15");
    tunSettings["autoSystemWfpBlockLeak"] = new JsonArray(); // Scope fixture traffic, never hijack CI control traffic.
    File.WriteAllText("fixture/scoped-tun.json", tun.ToJsonString());
}
if (args.Contains("--engine-lifecycle")) {
    var p = Profile.Parse("ss://" + Convert.ToBase64String(Encoding.UTF8.GetBytes("aes-128-gcm:continuum-ci-only-password")) + "@127.0.0.1:23081#LocalFixture");
    using var engine = new Engine();
    await engine.StartAsync(p, false, 1400, CancellationToken.None);
    Assert(engine.Running);
    await engine.HealthAsync(CancellationToken.None, "http://198.18.0.10:23080/");
    engine.Stop(); Assert(!engine.Running);
    Console.WriteLine("PASS Owned engine start, proxied request and stop");
}
sealed class Stub(Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> send) : HttpMessageHandler
{ protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) => send(request, cancellationToken); }
