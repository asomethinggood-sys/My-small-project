# Continuum — standalone Android VPN preview

Original native Android UI with real AndroidLibXrayLite/Xray TUN, not a v2rayNG fork or WebView prototype. Android 8+.

## Download

[Complete 0.3 ARM64 APK — 19.06 MB](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-0.3.0-preview-15/continuum-0.3.0-arm64.apk)

[Results, checksum, connection changes and phone test instructions](../docs/android-results.md).

Non-debuggable release build with code/resource shrinking and compressed single-ABI JNI. Preview signing keys differ between runners: uninstall the old preview if signatures conflict, deleting its settings. A privately retained signing identity is required for production updates. Never commit signing keys.

## Implemented

- Native status UI, real HTTP-check timing (not ping), endpoint, session duration, activity history and imported server profiles.
- VLESS/VMess AEAD/Trojan over TCP+TLS or WS+TLS; Shadowsocks SIP002 AEAD methods. Changing protocols requires a matching remote server, not a cosmetic toggle.
- Existing automatic VLESS/WS/TLS public subscription remains the default. No Worker/domain/VPS setup is required for it.
- Isolated VPN process, explicit Disconnect teardown, generation-safe async work, persistent manual pause and a bounded native-stop watchdog.
- Proxied cached DoH for TUN DNS, IPv4-answer compatibility default with optional dual-stack answers, HTTP Host/TLS SNI recovery, and matched 1280/1400/1500 MTUs (default 1400).
- Immediate real-core startup rather than duplicate preflight cores on cold connect; candidate verification remains for replacing an active profile. Health checks use the active engine and two possible endpoints, and no longer restart a running engine just because a check endpoint failed.
- Network changes and Check now force health checks. Screen-off scheduling reduces ordinary health checks to once per fifteen minutes and subscription polling to no faster than every 120 seconds. Manual profiles have no subscription fetches. Failed/offline states have separate retry policies.
- Push-based UI status; no per-second Binder request, settings parse or unchanged notification refresh. No wake locks or exact alarms.

The app UID bypasses its own TUN to avoid recursion. Other apps are routed through the VPN, including IPv6 routes even in IPv4-answer mode. Custom app/browser secure DNS can bypass the DNS policy. Xray DNS outbound handles A/AAAA and returns empty answers for other record types by default. Hostname recovery cannot recover every encrypted/absent hostname. This preview is not a certified kill switch or an exhaustive compatibility guarantee.

## Build

JDK 21, Gradle 8.11.1, AGP 8.9.2, SDK 35; Java 17 bytecode.

```sh
cd android
bash scripts/fetch-core.sh
gradle :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
gradle -PtargetAbi=arm64-v8a :app:assembleRelease :app:lintRelease
# Separate test ABI / test-only second UID:
gradle -PtargetAbi=x86_64 :app:assembleDebug :probe:assembleDebug
```

CI tests JVM logic/lint and real Android TUN traffic on API 35 x86_64: blocked-server-DNS compatibility, IPv4 answer policy, hostname recovery, HTTPS, uploads, downloads and UDP across four protocols, plus bound-service Disconnect and cancelled-fetch reconnect. The `:probe` app is test-only and never ships with Continuum. Successful task-branch builds publish full APKs as separate prereleases; `vpn-config` is untouched.

[THIRD_PARTY.md](THIRD_PARTY.md) contains native source, license and relinking references. The native AAR is pinned by version/SHA256. Installed storage exceeds compressed APK size.

## Limits

These changes reduce scheduled work; they are not measured battery or ping improvements. The default 1400 MTU is a compatibility choice, not a throughput claim. Longer screen-off polling can delay discovery. Native endpoint checks use gstatic generate_204 with a Cloudflare fallback and do not prove the complete TUN path on the phone.

Physical ARM release testing, the user's exact failing sites, Tehran latency, real network handoffs, OEM lockdown, exhaustive IPv6/leak tests and long-duration stability remain pending. No client can remove server outages or migrate established TCP connections across replacement backends. The default proxy is public/shared.

For rollback, disconnect, disable Android Always-on/lockdown if enabled, then uninstall. Existing server workflows and the v2rayNG subscription remain unchanged.
