# Continuum Android verification

## Implemented, not a website prototype

`android/` contains an original Android Activity and foreground VpnService backed
by a checksum-pinned AndroidLibXrayLite AAR. The device data path is Xray's native
TUN inbound -> VLESS -> WebSocket -> TLS. It uses the repository's existing public
subscription; the abandoned Worker setup is not required or activated.

The first version supports only the current server protocol, as selected by the
user. Other protocols are not decorative controls. Source parsing rejects them.
No PR, merge, server restart, Cloudflare deployment, or production signing-key
change was made as part of the app build.

## Verified

- GitHub-hosted Java/Android compilation produced `app-debug.apk`.
- JVM unit tests passed: plain/base64 subscription parsing, unsupported/insecure
  profiles and duplicate options rejected, TLS verification retained, early-data
  path preserved, bounded payload size, HTTPS-only source, label-only changes do
  not reconnect, failed candidate rejection and bounded recovery backoff.
- Android lint passed after fixing API-level compatibility and constant usage.
  Non-fatal warnings/deprecations remain; this is a preview, not a Play release.
- On an **Android 35 x86_64 emulator**, both instrumented tests passed:
  1. The real packaged native engine loaded, reported the expected Xray version,
     started an outbound-only VLESS configuration, and stopped successfully.
  2. The native app screen launched offline and the screenshot API worked.
- These are not end-to-end VPN traffic, handover, physical-device or Tehran tests.

Reference run: [42477069976](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42477069976),
app code at `dc05a2a` (production Java code last changed at `c855512`). Its build,
unit tests, lint and both device tests passed. The **overall workflow failed only
afterwards**: pulling the screenshot from app-scoped storage failed after Gradle
uninstalled the test app. That failure was not an app crash or failed native test.
A subsequent test-only change captures a shell-owned screenshot before uninstall
and distinguishes screenshot export failure from test failure.

Earlier failures included CI Android SDK tooling/adb/AVD discovery and lint issues.
They were fixed rather than marked as passing. The final recheck,
[42477610392](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42477610392),
**passed in full** at commit `ecc048f`: build, JVM tests, lint, both Android 35
instrumented smoke tests, and screenshot export. The actual emulator screenshot
is available as [continuum-screen-10](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42477610392/artifacts/13615598572).
No fabricated UI mockup is being presented as a device screenshot.

## Download / phone test

The final built development artifact is
[continuum-debug-10](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42477610392/artifacts/13615993429).
Sign into GitHub, download/extract the ZIP and install `app-debug.apk` (inside
`app/build/outputs/apk/debug/` in the archive). If you already installed build 9,
the subsequent changes only fix test screenshot export; there is no need to
reinstall just for that. Artifacts
expire after seven days; the installed app itself has no artificial expiry.
The archive also contains exact app source and engine source/license references.

1. Android 8+ is required. Disconnect the old VPN first; Android normally permits
   only one active VPN. Disable the old app's Always-on setting if it prevents
   switching VPN providers.
2. Open Continuum, tap **Connect**, and accept Android's VPN consent.
3. The current GitHub subscription is already filled in. Do not paste a temporary
   Worker profile. Give the app time to fetch and verify the actual current URL.
4. Check another app's HTTPS browsing/exit IP, DNS and IPv6 behavior. Report the
   displayed status and sanitized activity log if it fails (not private profiles).
5. Only after basic connection works, test Settings -> Android VPN -> Continuum ->
   Always-on, and OEM background/battery restrictions. Lockdown requires separate
   verification because the app's own control/core sockets bypass its TUN.
6. Leave the app connected across a controlled server rotation. Record the actual
   outage/recovery duration and whether foreground/background changes affect it.

The phone must be able to reach GitHub directly for subscription recovery. If the
ISP blocks that control endpoint while the old tunnel is dead, the app cannot
magically retrieve a new profile. Native engine probes run through the proxy;
subscription fetches and endpoint bootstrapping bypass the TUN to avoid loops.

## Not verified / no guarantees

Physical ARM devices, real TUN traffic, IPv6/DNS leak behavior, failover with a real
rotating subscription, lock-screen/Doze/OEM behavior, Android lockdown, battery
cost, 24-hour operation and Tehran latency are pending. The full acceptance plan
is in `android/README.md`. Emulator native startup does not establish any of these.

The app keeps the VPN interface while replacing the core and preflights changed
profiles, but the existing Actions backend still disappears before its successor
is ready. Existing TCP sessions cannot be preserved by pretending the old server
is alive. A core replacement also rebuilds its packet-flow state. This automates
reconnection; it is not seamless connection migration or a 24/7 uptime guarantee.

Debug APKs are intentionally marked preview. Fresh CI runners can use different
debug signing keys; a later build may require uninstall/reinstall. Establish a
privately stored stable release signing key before treating this as a normal app
update channel. No private signing keys belong in the repository.
