# Nyx investigation: current branch

## Scope and status

This branch started from the legacy `main` tree; the Nyx source and historical
results were restored from `arena/f056ce38-my-small-project` without switching
branches. The earlier 45-minute Japanese trial has ended. The old encrypted
handoff is not a current route. No current country pool or complete release APK
has been validated or deployed in this session. The exact historical test scopes
and build hashes are in `nyx-exit-acceptance-results.md` and
`nyx-android-compatibility.md`. Previously measured runner results do not prove
current availability or physical phone behavior.

The VPNGate and VPNBook bounded personal-probe adapters are real, but there is
no generally deployed multi-country control service, and the individual-provider
permission and availability gates still apply. Local country fixtures are not live
geography. The default route is not a fallback for a selected country. The new
branch's research workflow no longer publishes over the shared metadata release.
No trial was started and no shared deployment or default route was changed.

## Provider research (checked 2026-11-10)

- **VPNGate:** the [official server page](https://www.vpngate.net/en/) explicitly
  says its displayed list is partial to prevent DoS. Its
  [overview](https://www.vpngate.net/en/about_overview.aspx) describes mirrors,
  volatile volunteer servers, and multiple protocols. This establishes that the
  web list is partial, not that the CSV API has a fixed 100-server cap or is
  random. No official complete-inventory API or API sampling rule was verified.
  A snapshot is not the whole inventory, and an ingress IP is not necessarily the
  resulting exit. The [anti-abuse policy](https://www.vpngate.net/en/about_abuse.aspx)
  says connection logs are retained at least three months and volunteer servers
  retain packet-header logs at least two weeks; disclose this before use. It does
  not establish permission to run a public multi-user redistribution service.
- **VPNBook OpenVPN:** the [provider](https://www.vpnbook.com/freevpn/openvpn)
  advertises TCP and UDP configs and changing credentials; previously sampled
  German exits have conflicting geo evidence and remain unavailable as Germany.
  The [privacy and contact page](https://www.vpnbook.com/contact) says the free
  service is for personal use, logs connection IP/time and deletes those logs
  weekly; business/commercial options require contacting the provider.
- **VPNBook WireGuard:** the [official page](https://www.vpnbook.com/freevpn/wireguard-vpn)
  describes a user-generated, one-device configuration with a 7-day lifetime and
  a required check. No bypass, working acquisition adapter, tested UDP route, or
  redistribution permission is claimed. The homepage has also mentioned a different
  lifetime; live generated config terms take precedence and need verification.
- **WARP:** [Cloudflare states](https://developers.cloudflare.com/warp-client/warp-modes/)
  that WARP does not let a user pretend to access from a different country. It is
  not an arbitrary-country adapter. No WARP account or Cloudflare domain is required
  for the research tools; the historical temporary phone trial used a quick tunnel.
- **Psiphon:** its [official page](https://psiphon.ca/en/why-psiphon.html) describes
  region choice subject to subscription. Crucially, its [service license](https://psiphon.ca/en/license.html)
  permits only Psiphon-created clients on its service. The local OSSH fixture is not
  permission to connect Nyx to the Psiphon network; no such integration is enabled.
- **Proton:** the [free-plan guidance](https://protonvpn.com/support/increase-vpn-speeds)
  describes automatic/random free server selection, not reliable selection of an
  arbitrary target country. Account/entitlement and sharing rights need assessment;
  no live adapter is claimed.

These are provider descriptions, not evidence of working exit counts. Provider
policies and inventories can change. The sandbox permits outbound traffic only to
specified code/package hosts, so the fresh directory observation below was taken
in a bounded GitHub workflow, not in the sandbox. No new tunnel was tested.

### Fresh official directory observation

[Run 42841788578](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42841788578)
inspected one response on 2026-11-10. Unique advertised ingress IPs / inspected /
accepted TCP configurations were: JP 52 / 3 / 3; KR 21 / 3 / 3; US 3 / 3 / 3;
IN 2 / 2 / 2; AU 1 / 1 / 1; RO 1 / 1 / 1. Zero inspected configurations had
UDP transport; no tunnel or UDP capability test was performed. Other target
countries had no eligible OpenVPN ingress in that snapshot. These are transient
snapshot counts, not the full provider inventory, country-verified exits, or
current usable pools. The run's success means inspection executed, not that any
VPN connected. Its sanitized output and artifact contain no profiles.

## Bounded inspection utility

`python3 -m scripts.egress_vpngate_inventory --live` retrieves one official
snapshot in a permitted network environment. `--fixture PATH` supports offline
review. It validates the complete bounded snapshot before counting unique ingress
IPs by target country, inspects at most three distinct IPs per country and 60 in
all, in directory order, under the explicit CBC/HMAC-SHA256 compatibility policy.
Counts distinguish advertised IPs, inspected IPs, accepted TCP/UDP *configurations*
and rejected configurations. They are not an estimate of unlisted servers or a
random sample; the total budget and input order can leave later countries
uninspected. Accepted UDP transport is not a UDP capability test. No profile,
address, credential, verified exit, or usable pool is published by this utility.

## Exact-IP safety correction

Previously, VPNGate's namespace path used an explicit IP lookup, but the
VPNBook private-trial path could satisfy the mandatory country.is check with a
self-location response. The shared binding now first requires two matching IP
observations through the tunnel and performs the explicit-IP metadata lookup for
both providers. The explicit metadata response is not a second tunnel observation.
A self-location result is retained as conflict evidence, not counted as an
independent geography provider in addition to the same provider's explicit
lookup. Mismatched IPs, disagreement, missing evidence or lookup failure reject
acceptance. This is covered by offline tests; no new issued route was measured.

## Delivery and performance constraints

The prior universal candidate measured 143,832,708 bytes and the ARM64 candidate
41,431,421 bytes; they are not newly built or accepted here. The old 19.23 MB
compressed Continuum preview is not a complete Nyx release. Rust/JNI, Android
orchestration and Go/Xray have distinct roles; this is not an all-Rust VPN engine.
The home orbit now has a translucent gradient and bounded touch parallax, with a
reduced-motion-aware return. It is not a verified replica of any iOS material.
No Android SDK, JDK, Gradle, or Rust toolchain is installed in the local sandbox.
[Android run 42841631158](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42841631158)
compiled and tested the changed interface; its build and API 26, 35, 35/16 KB,
and 36 compatibility jobs passed. API 29 installed, reinstalled and launched the
exact universal APK, but UI Automator repeatedly failed to obtain an idle tree;
the overall run failed. A subsequent change avoids setting identical TextView
contents every second, a possible source of repeated accessibility events.
The full follow-up [run 42844019946](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42844019946)
passed the build and all five compatibility jobs, including API 29, although this
does not conclusively establish the earlier timeout's cause. The follow-up ARM64
candidate measured 41,447,805 bytes (SHA-256
`5e95a07f2b86a8253319547173c10eb428059f835a8f7c9a9427dd9698050465`);
the universal candidate measured 143,849,100 bytes (SHA-256
`937b5ce0f7d7168d79cc17c8f12ca5a57a76f24f954803038585350172ccc877`).
Both use an ephemeral release signer. These are routing-incomplete CI candidates,
not finished release APKs. No physical POCO result or stable signer is established;
never commit signing keys or credentials.

Local validation passed 153 Python tests and 13 Node tests. The bounded backend
workflow [42841631088](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42841631088)
and legacy published-APK install audit
[42841631089](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42841631089)
passed; neither proves a new public VPN deployment or country route.

The removed local forwarding stage is a structural change, not a measured phone
speedup. The connector, runner-to-upstream and destination paths may dominate.
Use `latency-testing.md` for client-side measurements, including failures. No
Tehran performance or uninterrupted TCP across replacement is established. A
finite workflow experiment is not a six-hour or permanent no-cost service;
no permitted sustainable multi-country no-cost host is established.
