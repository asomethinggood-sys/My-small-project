# Architecture decision — 2026-11-07

## Where the latency comes from

Original path: Tehran ISP -> international transit/filtering -> a reachable
Cloudflare edge -> Cloudflare tunnel connector in US Azure -> destination.
A nearby Cloudflare edge does **not** mean nearby VLESS egress: Xray still exits
from the US runner. Return routing can be asymmetric. Packet loss and congestion,
TCP retransmissions/head-of-line blocking, TLS and WebSocket setup, DNS delays,
shared runner CPU and shared proxy users also contribute. Transport tuning cannot
remove the US leg. A named tunnel fixes hostname stability, not origin geography.

**Different metrics:** ICMP ping to Cloudflare only probes the edge. TCP connect
to port 443 also does not traverse VLESS. v2rayNG real-delay tests typically involve
a destination HTTP request through the proxy, not pure RTT; record the version,
mode and test URL. A cold TLS/WS/HTTPS request includes several round trips.
Download Mbps depends on congestion, loss, TCP windows, parallelism and destination;
low RTT does not imply high throughput, nor does high throughput imply low RTT.

## Comparison

| Architecture | Cost (planning estimates) | Latency feasibility and tradeoffs |
|---|---|---|
| Direct Istanbul VPS | ~$5–10/month + domain | Leading candidate if Iranian ISP peers well into Turkey; fewer legs. Direct IP blocking, provider quality, transfer limits, admin/abuse responsibility. Not measured. |
| Direct Frankfurt VPS | ~$5–10/month + domain | Candidate even though farther: better peering may beat Istanbul. Same operational costs. Not measured. |
| Nearby VPS + named Cloudflare Tunnel | VPS cost + domain | Can help reachability and avoid inbound ports, but adds edge-to-origin route; must compare against direct from Tehran. Cannot assume lower RTT. Not implemented in this change. |
| US GitHub runner + Quick Tunnel | No VPS invoice, subject to account/service limits | Reported >350 ms; wrong origin location for this objective. Rotating endpoints, no SLA, Actions terms mismatch for standalone shared proxy hosting. Not a viable recommended free service. |
| Existing friend/community nearby server with permission | $0 incremental to user, someone pays infrastructure | Genuinely plausible if allowed, sufficient capacity, reachable from Iran and good route. Use the same direct installer; Tehran measurements still required. No such host is available here. |
| Cloud free-tier VM / trial credits | Conditional $0, possibly IPv4/traffic fees | Only viable if lawful signup/payment verification, available nearby capacity, persistent public IP and proxy use are allowed. Reclamation/expiry can break service. No qualifying account/capacity verified here. Do not plan on unlimited free hosting. |
| Cloudflare Worker | Free quota or paid plan | Not an Xray server or an automatic low-latency VLESS egress. Custom protocol implementation needed; destination restrictions and routing can defeat general proxy use. Not selected. |

**Decision:** move the data plane off Actions onto a direct nearby VPS. Only a
Tehran trial can choose the region/provider. Preserve the old loop gated off for
permitted testing, not as a claimed latency solution. No viable free infrastructure
has been verified in this environment; if you do not already have permitted nearby
compute, budget for a VPS. Do not purchase a long commitment based on this table.

## Worker and service checks (documentation, not deployment validation)

Cloudflare supports [incoming WebSockets](https://developers.cloudflare.com/workers/runtime-apis/websockets/)
and [outbound TCP sockets](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/).
This can support parts of a custom WS-to-TCP implementation; it does not imply a
ready, correct VLESS relay or arbitrary UDP proxying. TCP sockets reject Cloudflare
IP destinations, private addresses and port 25; public inbound raw TCP is not
provided by that API. A naive VLESS Worker cannot therefore be assumed equivalent
to general Xray egress. Neither Worker execution location, socket egress route,
Iran reachability, DNS handling nor UDP behavior was tested here.

[Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
currently list Free: 100,000 requests/day, 10ms CPU per request, 128 MB memory,
and six simultaneous outgoing connections per request. These are not promises of
unlimited proxy bandwidth; WebSocket invocation and CPU accounting must also be
reviewed for an actual implementation. Account eligibility, abuse enforcement,
[Cloudflare terms](https://www.cloudflare.com/terms/) and
[service-specific terms](https://www.cloudflare.com/service-specific-terms-application-services/)
need review before use. The CDN terms limit disproportionate large-file use on
non-Enterprise plans; do not infer from that either a blanket Worker prohibition
or blanket permission for a public VPN. No terms approval or Iran availability
has been established for a Worker alternative. It is not recommended here.

[Quick Tunnel documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
states no uptime guarantee, changing hostnames, and 200 in-flight requests before
429 responses. Interactive email authentication is incompatible with a normal
v2rayNG client. This is not a production uptime mechanism.

[GitHub Actions terms](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions)
restrict GitHub-hosted runner activities to the repository software project's
production/testing/deployment/publication and prohibit disproportionate burdens.
They also limit Actions access/use to development/testing. A continuously hosted
public proxy is not something this project can represent as compliant free
infrastructure. CI config validation is separate from using runners as the data
plane. Confirm current terms and applicable law; do not evade account restrictions.
