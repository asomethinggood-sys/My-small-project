# Country-route follow-up

## Bounded VPNGate measurements (2026-11-10 UTC)

[Namespace probe 42850850672](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42850850672)
used one fresh directory fetch per country and at most two candidates per country.
These are separate changing snapshots, not an inventory survey. An absent candidate
is not proof that the provider has no server in a country.

| Advertised country | Inspected and connection-tested | Result |
| --- | ---: | --- |
| KR | 2 TCP | One established and passed KR geography, UDP DNS, tunnel-drop blocking and unchanged host main routes; the other did not establish. |
| AU | 1 TCP, 1 UDP | Neither established. |
| IN | 1 UDP | Did not establish. |
| US | 0 | No eligible candidate in that snapshot. |
| RO | 0 | No eligible candidate in that snapshot. |

A profile's UDP transport is not the same as a passed UDP-through-tunnel test.
Each failed connection stopped at authentication/establishment; the cause was not
determined. The successful KR probe used explicitly pinned AES-128-CBC with
HMAC-SHA256, not AEAD, and retained TLS certificate verification and rejected
server-pushed auth overrides. The workflow's success says the experiment ran;
individual reports determine whether any VPN connection passed.

## Authenticated issued route, not merely namespace connectivity

[Issued-route diagnostic 42851333052](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42851333052)
acquired a fresh KR candidate and exercised a scoped authenticated
TLS/VLESS/WebSocket route through an isolated VPNGate OpenVPN tunnel. Namespace
and actual issued-route exit both measured `112.167.64.3`, despite ingress
`221.144.146.230`. Four route country observations agreed on KR, including the
mandatory explicit-IP lookup; issued-route UDP DNS passed. Namespace tunnel-down
and recovery controls passed, as did the post-test tunnel-drop block and unchanged
host main-route checks. Those observations apply only to that temporary diagnostic,
which closed its pool and connector immediately. No user/phone credential or
settings were issued. This is not an actual phone test or currently usable pool.

Runner-origin cold HTTPS observations were 2504, 2748, 1991 and 1911 ms for four
different endpoints; UDP DNS was 368 ms. These numbers include different provider
and destination paths and are not Tehran phone latency, an A/B comparison, or a
claim of an improvement. Dynamic provider ingress/exit availability can change.

## Implementation scope

The country-specific probe now validates the complete bounded snapshot before
applying its candidate limit and inspects the same explicit cipher policy it uses
for a live test. `egress_route_acceptance.py` adds a finite diagnostic path: up to
two same-country startup candidates, no replacement after entering the authenticated
route callback, strict route/country/UDP/drop checks, and no handoff publication.
Its workflow is deliberately commit-gated; it never self-chains or retries an old
session. Successful diagnostics do not register a production pool.

This does **not** finish a multi-country Android service. The earlier Japanese
issued-route test and this Korean diagnostic occurred at different times, and no
current concurrent JP/KR pools, durable free hosting, provider permission for a
shared service, stable signing, physical phone testing, or finished APK have been
established. Previous German address evidence remains disputed. The old default
on `main` remains untouched.

After the diagnostic, backend verification
[42851332383](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42851332383)
passed kernel, source and local-Psiphon jobs but failed the separate Xray download
step with curl exit 22. The exact HTTP cause was not visible via the available log
path. The diagnostic independently downloaded its pinned Xray and passed. A green
diagnostic does not make the backend workflow green.
