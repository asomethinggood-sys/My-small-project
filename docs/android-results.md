# Continuum 0.4 — tested Rust migration stage one

## Complete APK

[Download continuum-0.4.0-arm64.apk](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-0.4.0-preview-17/continuum-0.4.0-arm64.apk)

- Android 8+, ARM64 only; direct APK, not a ZIP.
- **19,226,015 bytes — 19.23 MB / 18.34 MiB**. Installed storage is larger.
- SHA256: `b89ab5d178ebbd7b108b414ee2987b2e447e2d878690f5641149bc7e80d59325`.
- Actual signing mode: **disposable preview key; stable signing not configured**. If Android rejects the update signature, uninstall the old preview first; this deletes settings.
- [Source, licenses, public signing certificate and network report](https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-0.4.0-preview-17).

## Implemented

- A real Rust native library, built for ARM64 and x86_64, owns scheduling/health policy, cancellation-token transitions, subscription backoff, validator eligibility, network-change comparison, diagnostic classification policy and counters. There is no silent Java fallback.
- Android default-network callbacks avoid reacting to unrelated available Wi-Fi/cellular networks. Actual changes force a health check rather than automatically destroying a working engine.
- HTTPS conditional requests use ETag or Last-Modified where supported. HTTP 304 reuses only a syntactically validated body for the exact source/redirect resource. A bounded in-memory cache avoids cross-resource validators. Failed fetches back off up to fifteen minutes; explicit Connect, Check now and network changes bypass backoff. An old in-flight failure cannot undo a newer forced retry.
- Settings → View / share redacted diagnostics exposes an explicitly shared local snapshot. It includes heuristic endpoint-check failure class, operation duration, Android/API/ABI, TUN/core flags, network/check/fetch counters and VPN-process CPU/PSS snapshots. It does not export profiles, credentials, endpoint addresses, raw errors, network names or browsing history.
- Build support for private stable signing is prepared. It remains inactive until an administrator configures the private Actions secrets. No signing key was committed or uploaded.

The 0.3 website fixes remain: proxied cached DoH, IPv4-answer mode by default, HTTP Host/TLS SNI recovery, matched 1280/1400/1500 MTUs (1400 default), reduced screen-off checks and no forced restart merely because an endpoint check failed.

## Migration is not complete

The agreed target is the **app-owned core**, retaining Xray and Android integration. This is stage one, not an all-Rust app. Profile/URI parsing, JSON configuration generation, HTTP transport/cache storage and orchestration still have Java implementations. Xray remains Go by design. See [migration status and signing setup](rust-migration.md) for remaining stages and prerequisites.

## Verified

Passing workflow: [42610656133](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42610656133), source commit `b2f6b67`.

- **13 Rust tests**: policy, backoff bounds, generation transitions/wrap, validator scoping, diagnostic categories and invalid metric indices.
- **41 JVM tests**, including real host JNI loading, 64-bit token preservation, simulated conditional HTTP/redirect/304 behavior, cache integrity, manual retry races, cancellation and previous profile/config tests.
- **Four API 35 x86_64 Android instrumentation tests**: the two existing VPN/lifecycle suites plus diagnostic redaction and packaged Rust JNI checks.
- Real traffic from a separate app UID passed ten checks for each of Shadowsocks aes-128-gcm and VLESS/VMess/Trojan WS+TLS: proxy-only marker, UDP/TCP DNS with server port 53 blocked, repeated A lookup, IPv4-mode AAAA behavior, HTTP hostname recovery, byte-verified 512 KiB download, byte-verified 64 KiB upload, 1200-byte UDP echo and certificate-verified public HTTPS.
- Explicit Check now, bound-service Disconnect, persisted manual pause, stalled-fetch cancellation/reconnect and stale-work rejection passed.
- Diagnostic privacy tests deliberately supplied secret-looking endpoint/error data and verified it did not enter the exported report.
- Debug/release lint, ARM64 native packaging and APK signature verification passed. The package contains the real Rust .so alongside the existing Xray library.

These results are not physical ARM testing, real cellular/Wi-Fi handoff, server-specific conditional HTTP evidence, a complete standalone DNS/TLS/transfer diagnostic, or battery/ping improvements. Error classification is heuristic. CPU/PSS snapshots are not idle-rate or battery A/B measurements. Rust itself does not guarantee speed improvements.

## Install / test

1. Install the APK above; uninstall the previous preview only if signatures conflict.
2. Use the existing automatic subscription. Start with IPv4 answers and MTU 1400; try 1280 if transfers stall.
3. Connect and use Check now. Open Settings → View / share redacted diagnostics. Reopen the snapshot after a check completes to see updated values; sharing is user-triggered.
4. Test Wi-Fi/mobile handoff and screen-off recovery on your phone. For remaining website failures, report domain, Android version, network type, error type and custom browser/Android secure-DNS settings—not private profile credentials.

Known limits: custom app DoH/DoT can bypass the app DNS policy; IPv6 literals/ECH/cached destinations may not provide a usable hostname. Xray DNS outbound handles A/AAAA and returns empty responses for other types by default. Android lockdown may intentionally block Internet while disconnected. No certified kill-switch, full leak-test, long-duration stability, Tehran latency or zero-downtime claim is made.

Production subscription/server workflows remain unchanged. No PR or main merge was opened. The earlier working [0.3 release](https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-0.3.0-preview-15) remains available for rollback.
