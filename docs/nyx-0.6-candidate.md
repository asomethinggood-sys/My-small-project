# Nyx 0.6 candidate: country-session integration and packaging

## Status — not a completed public country service

The Android client now implements authenticated availability, country selection, acquisition, lease renewal and fail-closed expiration. This is no longer only a discovery screen. A provisioned, authenticated HTTPS gateway and approved live pools are still necessary. No such public service is deployed by this candidate, and no working countries are invented from discovery metadata.

The reported installation rejection on the user's **POCO X7 Pro** has not been independently reproduced on that device. The exact OS/HyperOS build is unknown. Changes below are concrete compatibility improvements, not a proven diagnosis of that phone's error.

## Packaging changes

- Native libraries are uncompressed and directly loadable instead of extracted at install time.
- `check-apk.py` validates the final deliverable's ZIP CRC, ARM64 ELF headers, each load segment's 16 KB compatibility, and the actual ZIP payload offsets for 16 KB alignment.
- APK signing enables v1, v2 and v3. CI verifies the relevant signature paths separately.
- If stable signing is not provisioned, the build generates a dedicated ephemeral release certificate rather than using Android's generic debug certificate. The private key stays in runner temporary storage, never in the repository or artifacts. **Ephemeral signing still does not provide stable update compatibility.**
- The candidate uses version code 6 / `0.6.0-candidate`, preserving the separate `app.nyx.vpn` identity.
- The directly loadable candidate is larger: the initial packaging build measured approximately **41.43 MB**, rather than the previous compressed 19.23 MB. The final candidate's own size/hash report is authoritative.
- After debug instrumentation, CI builds the minified x86_64 release, installs and launches it, then installs the saved exact ARM64 candidate using the emulator's ABI override. An ARM64 override is package-manager validation, **not physical ARM execution**.

The first expanded release audit stopped because Gradle had already uninstalled its instrumentation target and a redundant `adb uninstall` failed. That harness error was corrected; it was not evidence of the user's installation issue. A later run hit an external fixture read timeout; failed tests were not suppressed.

## Real Android country-session flow

`CountryClient` uses certificate-verified HTTPS with no credential-bearing redirects. Service origin, owner and key are provisioned in private app settings; the credential dialog blocks screenshots/autofill and app backups remain disabled.

Availability must come from the authenticated service, not the public discovery release. The service advertises only fresh ready pools with UDP evidence and configured ingress profiles. The client validates country codes, bounded counts, provider/protocol breakdowns and relative lifetime. It keeps this availability in memory rather than converting a saved public snapshot into eligibility.

The user can select a fresh available country or explicitly choose the default connection. Country profiles are checked against the exact service hostname, TLS, VLESS/WebSocket transport, session token path, generation and requested country. TTL is at most 300 seconds and is converted conservatively to a monotonic local deadline.

The service:

- acquires a country lease instead of fetching the default subscription;
- renews near expiry, using Rust lease-policy decisions;
- rechecks settings and connection generation before installing asynchronous results;
- retires superseded leases without logging their tokens;
- retains a blackhole TUN when a requested country is unavailable;
- replaces an existing default tunnel with a blackhole TUN before switching to an unavailable country;
- blocks expired country traffic rather than selecting a default route;
- cancels pending requests and revokes leases on explicit disconnect;
- only resumes default routing when the user explicitly selects it.

This adds no control over other users' settings or host default routes.

## Validation scope

The local Python suite has **121 passing tests**, including backend and APK-packaging regression checks, plus four browser-policy tests. New JVM tests cover lease binding, wrong-country/token/generation/host rejection, TTL limits, credential-bound settings changes, redirect-origin restrictions, private revocation bodies and separation of discovery from authenticated availability.

Android instrumentation includes a separate-UID positive/negative/positive control: direct traffic is reachable before connection, blocked after changing a working default VPN to an unavailable country, and reachable again after explicit disconnect. The existing four-protocol TUN suite is retained.

Run **42683224822**, source **d5b3613**, passed **21 Rust, 55 JVM and 10 Android instrumentation tests**, including the additional temporary TLS fixture exercising actual UI selection, HTTPS session issuance, traffic through the Android TUN and gateway, lease-generation renewal, switching countries and disconnect. Minified x86_64 release installation/startup and ARM64 override installation also passed. Its overall workflow was not green: two additional compatibility harness checks needed fixes (Android 8 lacks getconf; 16 KB accessibility was not ready immediately after startup). Its DE/FR labels are **synthetic test data** and must never be counted as public German or French exits. Test credentials are ephemeral and excluded from published artifacts. The fixture runs only within the bounded Android CI job.

Subsequent complete runs **42687844848** and **42690395450** passed the build plus all five installation/startup matrix jobs: API 26/x86, API 29/35/36 x86_64, and API 35 x86_64 with measured 16 KB pages. The latter also integrates the bounded pool supervisor and passes the authenticated Android country-session flow. See [exact hashes and scope](nyx-android-compatibility.md). These successes do not prove ARM hardware execution, live country geography or deployment.

## Remaining acceptance gates

1. A legitimately provisioned real upstream pool and a permitted runtime, with ongoing health supervision.
2. Secure app-to-service provisioning for the deployed gateway, not hand-written fake endpoints.
3. A real phone country connection with independent exit-geography and UDP checks, alongside an unaffected default/second-user connection.
4. Successful installation and execution on the affected POCO/HyperOS configuration.
5. Sustained recovery/handoff and phone-network measurements; no Tehran latency guarantee is made.

Automatic preview release publication remains disabled, including the former release-marker path. No PR or change to main is part of this work.
