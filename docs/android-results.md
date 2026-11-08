# Continuum 0.2 preview — download and verification

## Complete APK (not an artifact ZIP)

[Download continuum-0.2.0-arm64.apk](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-0.2.0-preview-13/continuum-0.2.0-arm64.apk)

- Android 8+; **ARM64 only**. Not an x86 or 32-bit ARM installer.
- Download size: **19,057,107 bytes — 19.06 MB / 18.17 MiB**.
- SHA256: `c20081b5b977448cebf497061f06659e2603ee47194b0e6e06e1da59831574cc`.
- Non-debuggable, R8/resource-shrunk release build with compressed ARM64 JNI libraries. Installed storage is larger than the download.
- Preview certificate, not a stable production signing identity. If Android rejects an update, uninstall the previous preview first; this deletes settings.
- [Release, source and licenses](https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-0.2.0-preview-13).

## Changes responding to the reported defects

Disconnect now explicitly closes the TUN and native engine instead of waiting for `onDestroy()`. The VPN runs in a separate process; Binder carries status to the UI. Generation tokens discard stale asynchronous results. A saved pause prevents sticky/system Always-on start actions from undoing a manual disconnect. A bounded shutdown watchdog can terminate only the VPN process if native shutdown blocks.

HTTPS updates have cancellation and bounded timeouts. Unchanged healthy endpoints are probed every five minutes rather than on every subscription poll. Subscription polling remains selectable at 30/60/120 seconds. The health metric is an endpoint HTTPS check, not proof that every app's traffic is working or a raw ping.

Actual imported configurations support:

| Protocol | Supported combinations |
| --- | --- |
| VLESS | TCP + TLS, WebSocket + TLS |
| VMess AEAD | TCP + TLS, WebSocket + TLS |
| Trojan | TCP + TLS, WebSocket + TLS |
| Shadowsocks | SIP002; aes-128-gcm, aes-256-gcm, chacha20-ietf-poly1305; TCP/UDP |

Protocols, transports and encryption are separate layers, not independent VPN alternatives. Other combinations require a compatible server profile. The default project subscription remains VLESS + WebSocket + TLS, unchanged. Plain VLESS, REALITY, plugins, insecure certificate options and unsupported profile options are rejected. No Worker deployment or server purchase is required for the existing subscription.

## Verified evidence

Successful workflow: [42525696093](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42525696093), application source commit `2d0f11d`.

- Compilation, **18 JVM tests**, debug and release Android lint, and compressed single-ABI release packaging passed.
- **Two Android API 35 x86_64 instrumentation tests passed.** These now exercise a real Android VPN, not just native startup:
  - Four controlled profiles: Shadowsocks aes-128-gcm plus VLESS, VMess and Trojan over WebSocket + certificate-verified TLS.
  - A separate probe app UID reached `198.18.0.42` through Android TUN and the proxy. Only the fixture server redirects that benchmark address to a local marker response. The main app UID bypasses TUN, so testing from that UID would not have proved this path.
  - The real UI Disconnect button closed reported native/TUN resources and removed the Android VPN network while an observer kept the service bound.
  - A simulated system Always-on start action did not undo the saved pause.
  - Disconnect during a blocked HTTPS subscription request, subsequent reconnect, second disconnect and absence of stale-work resurrection passed.
- The temporary protocol servers were CI fixtures only. No production config, server workflow or Worker was changed.
- Earlier failed runs caught a private-address restriction in the fixture, cross-test cleanup interference, and a missing-path VMess parser bug. The passing run includes their corrections.

## Not yet verified

The shipped ARM64 release binary has not been run on a physical phone; runtime testing used the x86_64 debug build of the same source. TCP+TLS variants and other Shadowsocks methods have parser/config tests, not the four-profile live fixture coverage above. No claim is made for exhaustive UDP/DNS/IPv6 leaks, live subscription handover, Wi-Fi/mobile transitions, actual OEM Always-on/lockdown behavior, watchdog fault injection, battery usage, 24-hour stability or Tehran latency.

Client recovery cannot remove backend downtime or preserve existing TCP sessions across server replacement. No under-200-ms or uninterrupted-service claim is made.

## Install and check

1. Download the APK above; uninstall the old preview first if signatures differ.
2. Install, open Continuum, tap Connect and accept Android VPN permission.
3. Keep the default automatic project subscription, or import a matching server URI from the connection-profile selector.
4. Test browsing in another app, then tap Disconnect. Verify the Android VPN indicator disappears and does not immediately return.
5. If Android's **Block connections without VPN** is enabled, it can intentionally block Internet after disconnect. Disable lockdown when testing ordinary Internet with the VPN off.
6. Test network changes, screen-off recovery and a long session on your own phone before relying on this preview. Report device/Android version and observed state without publishing private profile credentials.

No PR or main-branch merge was opened. All application work remains on `arena/f056ce38-my-small-project`.
