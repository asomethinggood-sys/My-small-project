# Server egress research: real country exits from a hosted runner

## Executive conclusion

The runner can act as a VPN client as well as a proxy server. A different country exit does not require GitHub to relocate the VM: it requires forwarding the proxy's traffic through an authorized upstream in that country. The earlier focus on the absence of a runner-region selector was too narrow.

**Most promising no-account country-exit candidates to investigate:** VPNBook OpenVPN and VPN Gate's public volunteer OpenVPN directory. VPNBook also advertises German WireGuard endpoints, but its generator includes a verification step; unattended provisioning is not established.

**Do not conflate three goals:** country selection, lower latency and long-term free availability. An upstream can change the website-visible exit without improving the phone-to-runner leg, and adds a provider/trust dependency.

This document is source research and a proposed test design. No upstream was connected, no runner-side country/latency measurement was made, and no production server/workflow/subscription was changed. Provider pages and marketing labels are not live connectivity evidence. Date/status/expiry statements on fetched pages may be stale or inconsistent; validate actual downloaded configurations rather than trusting page timestamps.

## 1. What the runner can do

GitHub's public-repository standard Linux runner documentation lists 4 CPUs and 16 GB RAM for ubuntu-latest/ubuntu-24.04. It is a VM capable of running networking software, not merely a fixed-purpose build command. Hardware resources make routing implementation feasible; they do not determine geography, Internet peering or latency.

Source: [GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

Current logical path:

```
phone -> Cloudflare ingress -> cloudflared -> Xray on runner -> destination
```

Country-exit design:

```
phone -> Cloudflare ingress -> cloudflared -> Xray on runner
                                              |
                                  WireGuard/OpenVPN upstream
                                              |
                                      German exit -> destination
```

This is ordinary proxy chaining/policy routing. It does not require pretending the runner is in Germany. The upstream endpoint is real infrastructure supplied by someone else, whether paid, owned or publicly volunteered.

## 2. Candidate findings

### A. VPNBook OpenVPN — first no-account Germany candidate

The official free-VPN and OpenVPN pages advertise Germany endpoints `de20.vpnbook.com` and `de220.vpnbook.com`, alongside US, Canada, UK and France endpoints. They state that no account is required and publish shared OpenVPN credentials, rotated every one to two weeks. Their OpenVPN page offers TCP 443/80 and UDP 53/25000 configurations. These are provider claims, not measured availability.

Sources:
- [Free VPN and country list](https://www.vpnbook.com/freevpn)
- [OpenVPN configuration page](https://www.vpnbook.com/freevpn/openvpn)

Engineering assessment:
- A promising unattended *test* path: retrieve the official configuration/current published credentials, validate it, connect an isolated OpenVPN client, then measure actual egress.
- Prefer testing OpenVPN/UDP first when reachable, but do not assume it beats TCP on every route.
- Neither a successful page download nor the word Online proves a functional tunnel.
- Actual download automation, TLS parameters, authentication and runner connectivity remain to be tested. Do not bypass a verification challenge if the service presents one.

Trust/use constraints:
- VPNBook says it logs the connecting IP and connection time. Its contact page says weekly deletion; its features page says daily deletion. That inconsistency remains unresolved. Treat it as a logging provider, not an independently audited no-log service.
- Its contact page specifies personal use. Our existing subscription is public/shared; publishing it through this upstream is not automatically justified by the permission to make a personal VPN connection. Resolve that before using it as a publicly redistributable backend.
- Avoid PPTP despite its presence in the provider menu. Do not lower certificate verification or enable arbitrary legacy crypto just to make a candidate pass.

Sources: [Contact/privacy/use policy](https://www.vpnbook.com/contact), [features page](https://www.vpnbook.com/features).

### B. VPNBook WireGuard — attractive protocol, provisioning uncertainty

The official WireGuard page advertises the same two German endpoints and UDP port choices. It describes unique configurations, one active device per configuration and seven-day expiry. Its home-page news still describes 48-hour sessions. The generator instructs users to accept conditions and complete a check; an unattended supported provisioning API was not established in this research.

Sources: [WireGuard page](https://www.vpnbook.com/freevpn/wireguard-vpn), [homepage](https://www.vpnbook.com/).

Engineering assessment:
- Worth testing when a permitted configuration can be obtained.
- Use actual handshake results and config validity, not an assumed marketing expiry.
- Keep generated private keys out of Git, logs and artifacts.
- No blanket promise that registration-free means challenge-free or fully automatable.
- WireGuard transports IP packets, but the upstream still determines IPv6/NAT/port reachability. Protocol support is not proof of a leak-free complete VPN.

### C. VPN Gate — machine-readable country discovery, serious privacy tradeoffs

VPN Gate's official overview says it is free, accepts anonymous connections without registration, supports OpenVPN/SoftEther/L2TP/SSTP, and is supplied by volunteers. It explicitly warns that addresses and servers can change or disappear. Its server list points developers to a CSV directory for custom clients.

Sources: [overview](https://www.vpngate.net/en/about_overview.aspx), [official directory](https://www.vpngate.net/en/), [CSV endpoint](https://www.vpngate.net/api/iphone/), [FAQ](https://www.vpngate.net/en/about_faq.aspx).

Proposed country-aware selection:
1. Retrieve the official directory over HTTPS.
2. Filter country metadata, protocol support and freshness.
3. Limit the candidate budget; never test every listed relay aggressively.
4. Parse configurations as untrusted data and rebuild a safe local configuration.
5. Connect one candidate in isolation, verify actual exit and run small functional probes.
6. Keep a healthy candidate rather than switching for tiny benchmark fluctuations.

Availability of Germany must be checked at execution time. No live German VPN Gate relay is claimed here. Directory ping/speed figures are not the phone's latency.

**Logging is a material concern:** the official abuse policy says connection logs are retained for three or more months, including source/client details and destination hostname/IP/port metadata; volunteer relays retain packet-header logs for at least two weeks. The directory's short '2 Weeks' label does not summarize all logging. This is not an appropriate silent privacy upgrade.

Source: [VPN Gate anti-abuse/logging policy](https://www.vpngate.net/en/about_abuse.aspx).

### D. Cloudflare WARP — route experiment, not a free country selector

WARP can replace a source IP with a Cloudflare address. Cloudflare's own FAQ and GeoExit explanation say the address is intended to represent the user's approximate location; the connected data center need not be the geographically nearest one. A PoP label is not proof of website-visible country or physical exit.

Sources: [WARP FAQ](https://developers.cloudflare.com/warp-client/known-issues-and-faq/), [GeoExit explanation](https://blog.cloudflare.com/geoexit-improving-warp-user-experience-larger-network/).

Engineering assessment: benchmark direct versus WARP only as an alternate route/reachability experiment if provisioning/use is authorized. Do not claim that choosing an endpoint address forces a German free-WARP exit. Dedicated Cloudflare egress is a separately provisioned product, not an entitlement created by installing WARP.

Dedicated egress also distinguishes physical location and IP geolocation: behavior varies with IPv4/IPv6 and whether the destination is proxied by Cloudflare. A country result from one Cloudflare trace request is insufficient evidence of universal physical egress.

Source: [dedicated egress documentation](https://developers.cloudflare.com/cloudflare-one/traffic-controls/egress-policies/dedicated-egress-ips/).

### E. Tor — no-account country-directed TCP, not a full low-latency VPN

Tor's manual supports country codes in ExitNodes, so a country-directed TCP experiment is possible. A common tutorial error is claiming StrictNodes makes ExitNodes stricter: the manual explicitly says StrictNodes applies to ExcludeNodes, not ExitNodes. Exit selection must be checked against the deployed Tor version and observed circuits/results.

Source: [Tor node-selection manual](https://manpages.debian.org/unstable/tor/torrc.5.en.html).

Tor's official support material states ordinary Tor transports TCP streams, not arbitrary UDP packets. Research proposals for UDP are not evidence that a deployment supports it. A SOCKS connection through Tor therefore must not be advertised as full UDP/QUIC/game traffic support.

Source: [Tor transport limitation](https://support.torproject.org/relays/legal-and-abuse/ddos/).

Assessment: a possible isolated TCP-only country test, not the recommended low-latency/full-traffic backend. Country restrictions also narrow relay selection; do not attach anonymity guarantees to this design.

### F. Proton and Riseup — useful distinctions, not automatic solutions

Proton documents standard WireGuard configuration downloads after account login, including free-plan configuration support. Its app's free-plan country behavior must not be confused with what its configuration-download interface permits. Its documented free app country pool is not a guaranteed German exit. Account creation and provider plan/use permissions remain prerequisites; automated signup/public redistribution cannot be assumed authorized.

Sources: [WireGuard configurations](https://protonvpn.com/support/wireguard-configurations), [Windows/free-plan behavior](https://protonvpn.com/support/protonvpn-windows-vpn-application), [terms](https://protonvpn.com/en-us/terms-and-conditions).

Riseup documents a no-registration personal VPN service. That establishes a no-account service exists, not that it provides a supported Germany selector or permits our public relay use. Its gateway selection, CLI/provisioning interface and acceptable scope need additional validation before consideration.

Source: [Riseup official overview](https://riseup.net/en/vpn).

## 3. Recommended routing design

**Do not blindly replace the runner's global default route.** That risks routing the GitHub agent, release uploads, package downloads and cloudflared's control/ingress connections through an unstable upstream.

Keep a normal host namespace for:
- GitHub runner agent and workflow control.
- cloudflared's outgoing connection to Cloudflare.
- Authorized release/report publication.

Create an isolated data-plane namespace for Xray and the selected outbound path. The ingress connector reaches Xray over a narrow veth link. Xray's Internet-bound traffic can leave only through the chosen VPN interface. For WireGuard, the official birthplace-namespace mechanism allows the encrypted UDP socket to stay on the host while the interface lives in the isolated namespace.

Source: [WireGuard network-namespace design](https://www.wireguard.com/netns/).

For OpenVPN, preserve only the explicitly needed provider-endpoint underlay route and narrowly permitted ingress replies; deny other plaintext data-plane escape. Namespace DNS must use the intended tunneled resolver rather than host /etc/resolv.conf by accident. This design must be validated under tunnel failure; a namespace alone is not an automatic kill switch.

Security requirements:
- Never execute downloaded OpenVPN/WireGuard config files as trusted scripts. Reject arbitrary up/down/plugin/include/PostUp/PreDown hooks, unexpected file references and unsafe directives.
- Reconstruct a small allowlisted configuration, preserving proper certificate/public-key validation.
- Reject loopback/link-local/private/metadata endpoint targets where an Internet provider endpoint is required.
- Do not pass workflow tokens into VPN/proxy processes. Network namespaces isolate networking, not environment variables or the filesystem by themselves.
- Either verify both IPv4 and IPv6 egress, or deliberately block unsupported IPv6. Never quietly fall back to the runner's IPv6 route.
- In strict-country mode, upstream failure blocks data-plane traffic; it does not silently fall back to the original country.
- Switching an upstream can break existing TCP connections. Prefer stable selection with hysteresis, not constant 'fastest now' switching.

## 4. Country selection is not latency optimization

A German upstream changes the latter part of the route. It does not remove the existing phone -> Cloudflare -> runner leg. If the runner is in the US, a route through that runner and then Germany still contains that detour.

A better upstream might improve bad peering, loss, congestion or destination reachability, so it is also wrong to assume an extra hop always makes every application slower. The answer requires measurement. CPU/RAM capacity cannot substitute for that measurement.

Keep two independent policies:
- **country-strict:** require verified observed country; prefer availability/stability among eligible candidates.
- **performance:** choose among authorized candidates using functional success and latency measurements, without claiming a particular country unless verified.

Do not compare raw ICMP ping with HTTPS TTFB or call the app's endpoint-check number raw ping.

## 5. Proposed bounded workflow experiment — not implemented here

One 15–20-minute software integration test, separate from the live loop:
1. Inventory the runner's CPU, memory, kernel networking capabilities and baseline IPv4/IPv6 egress.
2. Use a small fixed candidate budget: direct baseline, a German OpenVPN candidate, and an authorized alternative if available.
3. Record which advertised endpoints could actually be downloaded, authenticated and connected. Unavailable/challenged endpoints are reported, not bypassed.
4. Verify exit addresses with independent HTTPS IP-echo services. Compare multiple geolocation sources where available; disagreement yields uncertain, not a forced country claim. Country databases still do not prove physical packet paths.
5. Exercise DNS, HTTPS with certificate verification, small upload/download, TCP and UDP independently.
6. Measure cold connection time separately from warm request latency, failure ratio and CPU/memory. Use repeated small requests with an explicit bandwidth budget; do not use volunteer services for saturation tests.
7. Kill the upstream in the test. Confirm data-plane traffic stops while GitHub reporting/control still works.
8. Reconnect; test DNS restoration and recovery time. Do not claim established TCP sessions migrated.
9. Emit a report and destroy temporary routes/processes. Do not overwrite vpn-config or self-chain the experiment.

Illustrative configuration interface, **not existing implemented switches**:

```yaml
env:
  EGRESS_MODE: openvpn
  EGRESS_PROVIDER: vpnbook
  EXIT_COUNTRY: DE
  COUNTRY_POLICY: strict
  CANDIDATE_LIMIT: "2"
  TEST_DURATION_MINUTES: "15"
  MAX_TEST_TRANSFER_MIB: "16"
  REQUIRE_UDP: "true"
  IPV6_POLICY: verified_or_blocked
  PUBLISH_PRODUCTION: "false"
```

The runner can measure its own upstream and functional behavior. It cannot establish the user's Tehran/ISP latency. A later opt-in app comparison can automate phone-side measurement without manual configuration, but still needs a running phone and must not silently upload browsing history.

## 6. Existing workflow improvements still recommended

Independent of the exit provider:
- Separate process, connector, full-data-path and publication health states.
- Bounded recovery of only the failed component; do not restart everything for one failed website.
- Several functional passes before publishing a candidate; download/read-back verification after publication.
- Generation-aware publication to prevent a late old run overwriting a newer config.
- Centralized validated settings, structured reasons for rejection and expiring research artifacts.
- Retain a fallback only while its server is demonstrably alive. Do not promise fallback from a dead predecessor.
- Keep QUIC/HTTP2 connector and early-data comparisons controlled. Test them separately from the upstream-provider change so improvements have an identifiable cause.

None of those changes were applied in this research turn.

## 7. Boundaries that affect feasibility

GitHub documents a six-hour hosted-job execution limit. Its Actions terms also restrict use to development/testing and prohibit specified unrelated/excessive infrastructure usage. A VM's resources do not create permission to operate an indefinitely self-chaining public VPN. Use bounded software tests, not a disguised always-on hosting loop or repeated runner creation to hunt a region.

Sources: [Actions limits](https://docs.github.com/en/actions/reference/limits), [Actions product terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions).

Likewise, no-registration upstream access is not blanket permission for unrestricted public re-sharing. In particular VPNBook's personal-use wording and VPN Gate's logging policy matter because the current subscription is public. Do not silently send users through a logging volunteer service or a personal-account upstream.

## Recommendation

Proceed with an **isolated, bounded country-egress integration test**, starting with VPNBook OpenVPN Germany as an advertised candidate and VPN Gate as a separately labelled volunteer alternative. Evaluate WireGuard only if supported provisioning can be completed without bypassing a challenge or provider restriction. Treat WARP as a routing experiment, Tor as TCP-only, and leave the working subscription untouched.

The corrected conclusion is: **a genuine country-specific exit can be implemented on a runner through another endpoint. The outstanding questions are actual endpoint availability, trust/use permission, full-traffic correctness and measured performance—not the absence of a GitHub region button.**
