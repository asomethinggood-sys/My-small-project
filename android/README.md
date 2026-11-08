# Continuum — standalone Android client (preview)

An original, native Android app for this repository's **VLESS + WebSocket + TLS**
subscription. No Worker, purchased domain or VPS is required. Not a v2rayNG fork
or a companion launcher: it integrates the real AndroidLibXrayLite engine and
Android `VpnService`, including Xray's native TUN inbound. Requires Android 8+
(API 26). Development preview, not a claim of uninterrupted 24/7 service.

## What is implemented

- Restrained native UI: warm off-white, dark green, status ring, actual endpoint,
  measured HTTP delay, session duration, next refresh, and an activity log.
  No WebView/remote fonts/ads, artificial latency numbers, or decorative protocols.
- System VPN consent and a foreground VPN service with a disconnect notification.
- Default subscription is the existing `vpn-config/config.txt` release asset.
  HTTPS-only redirects; bounded timeouts and payload size; plain/base64 VLESS URI.
- Checks every 60 seconds while connected (30/60/120 second user setting).
  Invalid, unsupported and multi-profile subscriptions are rejected, not guessed.
- Tests changed profiles with a separate outbound-only Xray instance **before**
  stopping the active engine. Keeps last known profile on failed candidate probes.
- Does not reconnect just because the URI's display label changes.
- Holds the Android VPN interface across core replacements. Its IPv4 and IPv6
  routes remain installed while the core is restarting. Xray v26.10.31 duplicates
  the Android TUN FD internally; its stop does not close the app-owned descriptor.
- Best-effort rollback if a replacement core fails to start; retries at
  5/10/20/40/60 seconds; recovery on non-VPN network changes.
- Privately caches the last verified profile for recovery if fetching fails.
  Backups are disabled. No UUIDs, full configs or credentials in the UI activity log.
- Android Always-on start/sticky process restart support, subject to Android/OEM
  restrictions. Explicit disconnect clears the requested connection state.

## Protocol selection: honest first version

The user chose **current server first**. VLESS / WS / TLS is the single supported
protocol combination, actually used by the engine. The protocol detail sheet
shows that supported choice; VMess, Trojan, WireGuard and transport-changing
switches are not offered because this server does not provide them. TLS checking
is always enabled. WebSocket early data is preserved if the imported URI includes
it; the app does not invent or enable it. Arbitrary custom Xray configs are not
accepted. A later multi-protocol edition requires matching server provisioning.

## What this cannot guarantee

The Actions loop queues its successor, then shuts down before the next runner is
ready. No client can send traffic through a nonexistent backend, migrate an
established remote TCP connection to a new server, or preserve every download or
call. This app automates discovery, verification and recovery; it cannot remove
that infrastructure gap. Full continuity would need overlapping backends and a
separate connection-migration architecture, not a UI setting.

Subscription polling can add up to the selected interval, plus GitHub release
cache/availability delays, network timeouts and probes to recovery. The engine
probe makes up to two HTTPS requests and may take tens of seconds on failure.
Android Doze/OEM task killing can delay scheduled work; foreground does not grant
unlimited execution. The app cannot defeat force-stop, lost internet or shutdown.
No zero-downtime, battery-life, throughput or <200 ms result has been measured.

The metric labelled **HTTP CHECK · NOT PING** comes from the engine's HTTPS probe
to `https://www.gstatic.com/generate_204`; it is not raw RTT or website download
speed. The engine returns a best successful sample from its built-in attempts.
That destination might be blocked. Test reachability before drawing conclusions.

## Build / get an APK

The `Android client` GitHub workflow builds the app with JDK 17, Gradle 8.11.1,
Android Gradle Plugin 8.9.2 and compile/target SDK 35. It downloads checksum-pinned
`libv2ray.aar` v26.10.31, runs JVM tests + Android lint, and produces a **debug APK**.
It does not start/cancel VPN workflows, publish server configs or use repository
write permissions. Download the artifact named `continuum-debug-RUN_NUMBER` from
a **successful** run. `app-debug.apk` is inside. Do not install unverified copies
from strangers. There is no release-signing key in this repository.

Local build on an Android development machine:

```bash
cd android
bash scripts/fetch-core.sh
# Install Android SDK 35 and use JDK 17, then Gradle 8.11.1:
gradle :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

This sandbox has no Android SDK/JDK and blocks release asset/Google Maven hosts;
building is delegated to CI, not simulated by compiling a website. Engine license,
source and relinking information: [THIRD_PARTY.md](THIRD_PARTY.md).

Debug builds are for testing. Each fresh runner can generate a different debug
signing key: installing a later artifact may require uninstalling the older app,
which deletes settings. Production updates require one privately retained signing
key. Do not call these artifacts a stable update channel or a Play Store release.

## Phone setup

1. Install the successful build's APK, accepting installation from that source.
2. Open **Continuum**. Check Settings: the repository subscription is prefilled.
3. Tap **Connect**, accept Android's VPN permission, and allow notifications.
4. Wait for **Connected**. Open a website in another app. Inspect exit IP using a
   trusted check site and compare with VPN off; UI status alone is not a leak test.
5. In Android Settings -> VPN -> Continuum, enable **Always-on VPN** if desired.
   OEM battery settings may require allowing background activity/unrestricted use.
6. Only enable **Block connections without VPN** after testing it on your Android
   version: this app excludes its own package so native-core and subscription
   sockets don't loop into the TUN. Some lockdown/OEM configurations can block
   that excluded app and prevent bootstrap or recovery. This build is **not a
   certified kill switch**. During an active service it retains TUN routes on
   failure; after a process/service death Android policy controls bypass behavior.

The app's own control-plane traffic (subscription fetch, endpoint DNS, probes,
core transport) deliberately bypasses the TUN; other apps are routed through it.
Both IPv4 and IPv6 routes are installed. Validate DNS/IPv6 behavior on real devices.
Do not use this preview for safety-critical privacy without those tests.

## Acceptance tests on a real Android device (pending)

- Consent refusal: no connection claim; grant permission and confirm data passes.
- Verify native library loading and traffic on arm64 (and other packaged ABIs).
- Confirm TCP HTTPS, DNS, IPv4 and IPv6; no fallback/direct outbound is configured.
- Unchanged subscription: 10 refreshes, no reconnects/session interruption.
- Rotation: controlled test subscription moves from working A to working B. Observe
  preflight before engine stop; host changes; measure actual interruption.
- Invalid/empty/base64-broken/wrong-protocol update: A is not overwritten.
- Unreachable B: A stays configured; bounded retries; no false Connected status.
- A disappears before B exists: retained VPN routes, retry state, eventual recovery.
- Wi-Fi -> mobile -> offline -> Wi-Fi; screen off/Doze; process kill; Always-on
  restart; user disconnect; permission revocation; no leaked foreground service.
- Enable lockdown separately and check bootstrap and recovery on the actual OS.
- Compare battery usage at 30/60/120 seconds, with real failures and successful runs.
- Run the repository's Tehran latency plan on the phone; runner times aren't Tehran.

Until these pass, this is an installable development candidate, not verified
long-term reliability. Settings and the current configuration are private to the
app, but the repository's proxy itself remains publicly shared.

## Rollback

Disconnect in the app, disable Android Always-on/lockdown for Continuum if enabled,
and uninstall if desired. Use your existing v2rayNG subscription again. No server
migration or Worker deployment is needed. Existing workflow/configs are untouched.
