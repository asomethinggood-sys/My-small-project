# Continuum — Android VPN, Rust migration stage one

Original native Android UI and real Xray TUN engine, not a v2rayNG fork. Android 8+.

## Download

[Full 0.4 ARM64 APK — 19.23 MB](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-0.4.0-preview-17/continuum-0.4.0-arm64.apk)

[Exact size/hash, tests and phone setup](../docs/android-results.md) · [Rust migration status and signing prerequisites](../docs/rust-migration.md)

**Not a completed Rust rewrite.** Scheduling/session/backoff/validator/diagnostic policies are Rust through real JNI. Java profile/config parsing and Android orchestration remain. Xray remains Go by the selected migration scope. Source and native/runtime notices accompany the APK.

## Features

- Existing public VLESS/WS/TLS subscription unchanged; imported VLESS/VMess/Trojan TCP+TLS or WS+TLS and supported Shadowsocks AEAD profiles.
- Proxied cached DoH, IPv4-answer compatibility default, optional dual stack, hostname recovery and matched MTU controls.
- Explicit isolated-process Disconnect, generation-safe async results, saved manual pause and native-stop watchdog.
- Default-network monitoring, conditional HTTPS subscription fetching, exact-resource validator scoping and failure backoff that Check now/network changes can override.
- Active-engine health checks, reduced screen-off work, no per-second Binder polling or unchanged notification refreshes.
- Explicitly shared redacted diagnostics with heuristic failure classes, local counters and CPU/PSS snapshots—not analytics or measured battery savings.

## Build

Linux, Rustup, JDK 21, Gradle 8.11.1, AGP 8.9.2, Android SDK 35. The preBuild task installs/builds Rust 1.85.1 targets with NDK 27.2.12479018. The dependency-free Rust crate has a checked-in lockfile; host JNI is used by JVM tests, Android JNI by the app.

```sh
cd android
bash scripts/fetch-core.sh
gradle -PtargetAbi=x86_64 :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
gradle -PtargetAbi=arm64-v8a :app:assembleRelease :app:lintRelease
```

CI additionally runs a separate-UID probe app through the actual TUN for DNS, HTTPS, hostname recovery, large transfers and UDP across four protocols, plus lifecycle/redaction/JNI tests. The probe is not shipped with Continuum. Successful task-branch builds publish full APK prereleases without modifying vpn-config.

## Signing

Stable signing support is implemented but **not provisioned**. Current APKs use disposable preview certificates, so updates may require uninstall/settings loss. An administrator must provision the four private Actions secrets described in the migration document. Never commit/paste private keys or passwords. CI keeps keys in runner temp; release artifacts include only public certificate information.

## Limits

The app UID bypasses TUN to avoid recursion. IPv6 routes stay in the VPN even in IPv4-answer mode; custom browser/app secure DNS can bypass that answer policy. A/AAAA are handled by Xray DNS; other record types default to empty replies. No full leak-test or certified kill-switch claim is made.

The migration and standalone diagnostics are staged. Physical ARM runtime, real mobile handoffs, power/CPU A/B measurements, full DNS/TLS/transfer fault isolation, production rotation and long-duration reliability remain pending. No under-200-ms or battery-saving claim is justified by the runner tests. Backend outages and established TCP sessions cannot be fixed by language migration.

Licensing/relinking: [THIRD_PARTY.md](THIRD_PARTY.md). Rollback: disconnect, disable Android Always-on/lockdown if enabled, then uninstall. Existing server workflows and the v2rayNG subscription are unchanged.
