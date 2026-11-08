# Continuum — standalone Android VPN preview

Original native Android UI, real AndroidLibXrayLite/Xray TUN engine; not a v2rayNG fork, WebView prototype or companion launcher. Android 8+.

## Download

[Complete ARM64 APK — 19.06 MB](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-0.2.0-preview-13/continuum-0.2.0-arm64.apk)

[Measured results, checksums, installation and test limitations](../docs/android-results.md).

The release is non-debuggable and compressed, but signed with a preview certificate. Updates between runners may require uninstalling the old preview, deleting its settings. A privately retained signing identity is needed for a production update channel; no signing keys belong in this repository.

## Implemented

- Native off-white/green UI, measured HTTP delay (not ping), endpoint, activity history, import and selection of real server profiles.
- VLESS, VMess AEAD and Trojan over TCP+TLS or WebSocket+TLS. Shadowsocks SIP002 using aes-128-gcm, aes-256-gcm or chacha20-ietf-poly1305 over TCP/UDP.
- Protocol, transport and encryption are different layers. Importing a different protocol requires a compatible server; no fake transport switches reconfigure the remote endpoint.
- Existing public rotating VLESS/WS/TLS subscription remains the default. No Worker/domain/VPS setup is required for that connection.
- Strict unsupported-option rejection, certificate verification, HTTPS-only subscription requests, bounded payloads and timeouts, candidate preflight and verified-profile caching.
- Subscription polls at 30/60/120 seconds; healthy unchanged profiles get an endpoint check every five minutes. Failed checks retry with bounded backoff.
- Dedicated `:vpn` process, Binder UI status, explicit Disconnect resource teardown, cancelled-generation rejection and a native-stop watchdog that cannot kill the UI process.
- Manual pause persists across sticky/system start actions; only explicit Connect clears it. Android lockdown may still block ordinary Internet after disconnect.

The app UID bypasses its own TUN so the core transport and subscription requests cannot recurse through it. Other apps use the VPN. This is not a certified kill switch: validate DNS, IPv6, lockdown and OEM behavior before using a preview for sensitive traffic.

## Build

JDK 21, Gradle 8.11.1, AGP 8.9.2, Android SDK 35; Java 17 bytecode.

```sh
cd android
bash scripts/fetch-core.sh
# Default is ARM64, not a four-ABI universal APK.
gradle :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
gradle -PtargetAbi=arm64-v8a :app:assembleRelease :app:lintRelease
# Emulator instrumentation uses a separate x86_64 build.
gradle -PtargetAbi=x86_64 :app:assembleDebug :probe:assembleDebug
```

`Android client` CI builds both ABIs, tests JVM logic/lint, and runs actual Android TUN traffic through temporary protocol fixtures. A tiny separate-UID `:probe` APK proves the VPN path; it is test-only and is not shipped with Continuum. CI tests real disconnect while bound, saved pause and reconnect after a stalled fetch. Only successful task-branch builds publish a full APK as a separate prerelease asset; the production `vpn-config` release is untouched.

Source/license/relinking information: [THIRD_PARTY.md](THIRD_PARTY.md). The native AAR is pinned by version and SHA256. APK size is measured during CI; installed storage includes extracted native code and will be larger.

## Limits and phone acceptance

API 35 x86_64 emulator tests are not physical ARM64 testing, Tehran measurements, exhaustive leak tests or 24-hour stability evidence. TCP+TLS imports and all supported Shadowsocks methods have configuration tests; live fixture traffic covers VLESS/VMess/Trojan WS+TLS and Shadowsocks aes-128-gcm. Test Wi-Fi/mobile handoff, Doze, process death, real Always-on/lockdown and a full rotation on the actual phone.

No client can remove backend outages, guarantee a latency target or migrate existing TCP sessions to a replacement server. HTTP checks use `https://www.gstatic.com/generate_204`, not raw RTT or throughput. Settings/configs are private to the app and backups are disabled, but the default proxy remains publicly shared.

To roll back, disconnect, disable Android Always-on/lockdown if enabled, then uninstall. The existing v2rayNG subscription and server workflows are unchanged.
