# Continuum Android 1.0 OPEN BETA — built APK

## Downloads

Final app release: https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-android-1.0-beta-2

- ARM64 (recommended for POCO X7 Pro): https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-android-1.0-beta-2/continuum-1.0.0-open-beta-arm64.apk
  - **41,448,020 bytes** (~41.4 MB)
  - SHA256: `4e27abe0d3b888ad697e517a00a8f3b8ddd27f5a67f3b8e6de0247b29b06d12f`
- Universal (four CPU architectures): https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-android-1.0-beta-2/continuum-1.0.0-open-beta-universal.apk
  - **143,849,320 bytes** (~143.8 MB)
  - SHA256 is included in the release's SHA256SUMS asset.

Corresponding overlaid Android source, dependency binding sources, license notices, manifest report, signing report and screenshots accompany the APK. Intermediate release beta-1 is superseded by beta-2.

## Actual build evidence

APK source: `b5ae1f6`. GitHub Actions **43631449342**: both `candidate` and `publish-apk` successful.

Completed gates:

- Guarded overlay applied in the build checkout, not silently over the original local Android app.
- Rust/JVM tests, including beta schema rejection, preference/best measured choice, unavailable fallback, expiry and fixed labels.
- Debug and release Android lint, ARM64 and universal release compilation.
- Existing real emulator VPN fixture regression suite: DNS over the tunnel, TCP/UDP, byte-checked transfers, public HTTPS and lifecycle tests. These are local controlled peer tests, not ten public beta server tests.
- `BetaUiTest`: all ten exact local labels appear once in the dialog, all ten entries begin as Not checked, check/manual controls exist, no editable configuration/raw backend text appears, and opening the list does not connect.
- Minified release installed/launched on x86_64; exact ARM64 candidate installed with ABI override (not physical ARM execution).
- Release accessibility XML contains Servers; release manifest asserts `app.continuum`, versionCode `100`, versionName `1.0.0-open-beta`.
- APK signatures, uncompressed native libraries, ELF and ZIP alignment (16KB for 64-bit libraries).
- Added a guard against publishing Connected after expiry stops the payload during discovery. This guard compiled and passed the surrounding suite; the exact timing race was not exercised against a live public slot.

Separately, nine local offline staging tests pass. These verify ten independent manual workflow entrypoints, schema publication, one queued successor, failure backoff, explicit stop switch, and **no experiment-wide deadline**, including repeated cycle calculations many years ahead.

## What was and was not activated

The user explicitly authorized build-only CI after local dependency installation was blocked. Java runtime installation succeeded locally, but Google SDK/AGP, Gradle distribution and Rust toolchain hosts were unreachable in this sandbox. The authorized CI build completed the APK.

Only the APK builder was installed in `.github/workflows`. The ten server entrypoints and reusable worker remain staged in `AGENT START HERE/workflows/` and were NOT dispatched. No beta server variables were enabled and no `continuum-beta-01` through `10` connection assets were published by this agent. Main, the old single-server subscription and Windows release remain unchanged.

The next agent can activate the prepared workers following README.md. There is no app implementation/build task left to delegate. Live deployment verification remains necessarily pending until those workers run.

## Rotation semantics

There is no seven-day cutoff or expiry date for the experiment. Each slot queues one successor at the beginning of its workflow, serializes via its slot concurrency group, and continues while `ENABLE_CONTINUUM_BETA=true`. Failed cycles have a five-minute backoff. Setting that variable to false and cancelling beta running/pending jobs explicitly ends it. Per-job time limits and per-address expiry remain to avoid using dead runner addresses.

This is an application loop design, not a guarantee against platform quota, outage, authorization denial or runner unavailability. Existing calls/downloads may reconnect across a server replacement.

## Installation and limits

The app can be installed now, but slots correctly show unavailable until the activation agent starts/publishes the servers. No synthetic latency or fake working servers were included.

Signing is a dedicated candidate certificate; stable signing secrets were not provisioned. An older differently signed Continuum installation may need uninstalling before this APK will install, which loses local settings. The package ID remains app.continuum.

Physical POCO/HyperOS acceptance, the user's network, all API/device combinations, live ten-exit selection/rotation and service-specific call/video reliability have not been verified. Do not confuse the completed app build with a deployed or globally reliability-tested service.
