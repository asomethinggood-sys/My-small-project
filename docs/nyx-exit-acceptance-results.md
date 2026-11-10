# Exit-country correction: measured acceptance results

## What the phone established

The user confirmed that the private workflow-hosted connection works, but reported French exits after choosing Germany and high latency. That confirmation does not establish country correctness or production readiness.

## Disputed addresses must not be advertised as verified Germany

- `51.75.145.220` (VPNBook DE220): explicit lookup comparison in workflow **42706938695** reported DE from ipapi.co, ipwho.is, ipinfo.io and iplocation.net, but **FR from country.is**. This is independently reproduced disagreement, not a demonstrated phone failure.
- `51.75.145.20` (VPNBook DE20): workflow **42749766988** measured this exact address through the issued TLS/VLESS/WebSocket route. Two through-route geography responses reported DE, while the mandatory explicit-IP country.is lookup reported **FR**. Startup was rejected; no new phone settings were published.
- An earlier self-location response from country.is reported DE for the alternate. The explicit-IP lookup disagreed. The code now binds the mandatory lookup to the exact measured exit IP instead of relying on the self-location response.

Neither address is eligible for the private German service under the current strict policy. This does not establish either server's physical location; it establishes that the available evidence conflicts with the promised unambiguous country label. Do not silently relabel either address as France: other evidence still disagrees.

## Implemented controls

- End-to-end inspection of an actual authenticated issued route before handing out settings.
- At least two matching public-IP observations, agreeing country evidence, and the mandatory France-reporting source bound to that exact IP.
- Missing mandatory metadata, disagreement, unverified UDP, expiry or failed health means unavailable—not default fallback.
- HTTPS connector readiness is a bounded read-only check; session creation is never blindly retried.
- Country failure reports retain issued-route evidence and clear `verified_country` after failed acceptance.
- A running private trial terminates if its pool becomes unhealthy rather than silently remaining advertised until the nominal cutoff.

## Routing work and tests

The gateway now uses one tracked forwarding stage into the isolated pool rather than a second loopback relay. Quotas, generation checks, expiry, socket teardown and default-route independence are retained. This removes a local hop and forwarding worker; **no measured phone-latency improvement is claimed**.

The local Python suite passes **134 tests**. Backend verification **42750758988** passed the kernel/Xray/sources/local-Psiphon jobs. Android run **42703027845** passed its build and all 10 routing instrumentation tests; four compatibility jobs passed, while the 16 KB emulator UI-navigation check failed after successful installation and startup. That overall run is not green and is not being used to publish a new APK. Earlier full green compatibility evidence remains in `nyx-android-compatibility.md`.

## Alternative provider review

The bounded VPN Gate review **42750758966** inspected up to five configurations per advertised target country, after supporting OpenVPN's standard TCP client alias. The current snapshot had 47 JP, 36 KR and 2 AR advertised configurations; twelve sampled profiles were inspected and **none passed the current authentication-digest policy**. No German candidate appeared in that snapshot. These counts are transient metadata, not live exits, and this sample does not prove that every VPN Gate profile is unusable.

No untrusted configuration was executed, no profile/private key was published, and the cryptographic policy was not weakened to force availability. Provider coverage beyond the verified adapter paths remains incomplete.

### Subsequent AEAD-only inspection and live test

Review **42828928713** accepted twelve sampled profiles for AEAD-only experimentation (five JP, five KR, two AU), after normalizing inline PEM whitespace. These were configuration candidates, not verified exits.

The new `egress_vpngate` adapter reads the official directory, deduplicates public endpoints, binds each sanitized endpoint to its directory IP, rejects interactive credentials, and tests at most three candidates. It does not publish a phone service. The explicit experimental cipher policy pins both negotiated and non-negotiated data channels to AES-128-GCM. `data-ciphers-fallback AES-128-GCM` supports peers without negotiation; it does **not** permit CBC or SHA1 data protection. TLS 1.2 minimum and server-certificate verification remain mandatory. Default sanitizer behavior still rejects SHA1 hints; experimental mode replaces that data-MAC hint only without a tls-auth block.

Live workflow **42829732452**, job **129876333704**, tested three advertised JP candidates. One returned `authentication_rejected`; two returned `connection_not_established`, all at the authentication stage. **Zero tunnels or country exits were verified.** All three reported unchanged host main routes. The workflow's successful completion means the bounded experiment ran, not that a VPN connection worked. No settings or keys were published.

The local suite now passes **139 tests**, including endpoint binding, target filtering, deduplication, bounded candidate limits, credential rejection, and pinned-GCM configuration. The VPNGate connection path remains experimentally unsuccessful; phone integration is not enabled. Successful future namespace probes would still need issued-route acceptance before any phone handoff.

### Diagnosed cipher mismatch and verified Japanese namespace exits

Diagnostics **42832212095** established that peers passed certificate-chain checks and reached TLS/configuration exchange; two then failed cipher negotiation. Broader AEAD negotiation in **42832475217** still failed, with AES-128-CBC reported. This is not a transport or certificate failure.

A separate, explicit compatibility experiment uses AES-128-CBC with **HMAC-SHA256**, both already permitted by the strict sanitizer. It replaces the downloaded SHA1 hint with a SHA256 request; it does not enable SHA1, change TLS certificate checks, or silently fall back from AEAD. Profiles with tls-auth cannot use this rewriting mode. A peer that cannot use the requested data MAC must fail live traffic tests.

Workflow **42832808690**, job **129887022861**, tested three JP candidates. One rejected authentication. Two established tunnels and passed independent country evidence, explicit-IP country.is matching, UDP DNS, tunnel-drop blocking, and unchanged host main-route checks:

| Observed exit | Country observations | UDP | Tunnel-drop block | Host routes |
| --- | --- | --- | --- | --- |
| 219.100.37.240 | JP / JP / JP | passed | passed | unchanged |
| 219.100.37.239 | JP / JP / JP | passed | passed | unchanged |

These were initially **namespace verification results**, not phone or production availability. Acquisition trials **42833374807** and **42833743583** failed before connection: an exit address is not necessarily a directory ingress, and a previously observed ingress can disappear from a subsequent directory snapshot.

The phone supervisor now binds availability, evidence, issued-route tests, and encrypted provisioning to the verified country/provider instead of hardcoding Germany. Startup takes at most three deduplicated candidates from one fresh official snapshot, all for the same selected country. It never rotates an already-issued phone session, never changes country on failure, and stops if the phone callback fails. Server-pushed `auth` overrides are rejected so SHA256 cannot silently become SHA1. Local tests: **143 passed**.

### Issued phone route accepted

Trial **42834620957**, startup job **129893430866**, passed startup and published only encrypted provisioning. Decrypted acceptance metadata reports exit **219.100.37.240**, country **JP**, and observations **JP / JP / JP**. Handoff is gated on the real authenticated TLS/VLESS/WebSocket route, matching explicit-IP geography, and successful UDP DNS. The private settings were delivered through the workspace viewer, not committed or printed in logs. The runtime cutoff is 45 minutes after successful issuance; this does not imply permanent service or phone-measured latency improvement. Ongoing health still terminates the trial on failure.

## Current delivery status

The incorrect verified-country claim is now rejected. There is currently **no newly accepted German phone endpoint** to deliver. Full multi-country service, stable production signing and sustained deployment are not complete. A Japanese issued route is now accepted for the bounded personal trial above; this does not validate Germany or the other catalog targets. Workflow ownership is not the blocker demonstrated here: upstream country evidence, compatible available pools, and a sustained deployment remain unresolved. No permanent hosted-runner loop, automatic trial renewal, PR, main-branch change or replacement release was made.
