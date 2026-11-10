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

## Current delivery status

The incorrect verified-country claim is now rejected. There is currently **no newly accepted German phone endpoint** to deliver. Full multi-country service, stable production signing and sustained deployment are not complete. Workflow ownership is not the blocker demonstrated here: upstream country evidence and compatible available pools are. No permanent hosted-runner loop, automatic trial renewal, PR, main-branch change or replacement release was made.
