# Android compatibility contract

## Intended support, not an all-device guarantee

Nyx targets Android 8.0 (API 26) and later. The build now supports ARM64 (`arm64-v8a`), 32-bit ARMv7 (`armeabi-v7a`), Intel/AMD 64-bit (`x86_64`) and 32-bit Intel (`x86`). Android versions below API 26 and other architectures are unsupported. OEM restrictions, work-profile policies and device-specific defects can still prevent installation or VPN operation.

The universal APK contains all four native architectures, including both Rust JNI and Go/Xray. It is a standalone APK, not a split APK requiring an installer bundle. Android selects the appropriate native libraries. The ARM64-only APK remains a smaller alternative for modern phones. A universal, directly loadable package is necessarily much larger than the old approximately 20 MB ARM64 compressed preview. CI records exact sizes and SHA-256 values; do not advertise a guessed download size.

## Validation gates

- ZIP integrity and completeness: both native libraries must exist for every requested ABI.
- ELF architecture and load-segment checks: 16 KB-compatible 64-bit libraries and 4 KB-compatible 32-bit libraries.
- Uncompressed, page-aligned APK native payloads.
- APK signature verification; stable signing is still required for reliable upgrades between independently built releases.
- Normal installation of the exact universal release, without ABI overrides, on API 26/x86 and API 29, 35, 36/x86_64.
- Additional API 35/x86_64 16 KB system-image run verifies the actual device page size.
- Same-signer reinstall without clearing app data, release-mode home-screen startup (including Rust JNI), and actual UI navigation into the non-exported country screen.
- Separate full Android TUN, authenticated country-session, renewal, switching and disconnect tests remain required. Package-manager acceptance is not a substitute for VPN traffic tests.

These are configured gates, not a declaration that every run has passed. Check the workflow result for the exact source SHA. Intel emulator execution is not physical ARM execution. The original POCO/HyperOS installation error remains unconfirmed on hardware.

## Service and release limits

Country discovery lists 30 targets, not 30 working exits. Synthetic German/French labels in bounded test fixtures are not geographic evidence. No approved public country service is deployed. Universal packaging does not solve provider provisioning or runtime permission.

Publication is disabled while these acceptance gates remain incomplete. Candidate credentials and signing keys must never be included in artifacts. An ephemeral release signer can validate a single build and same-build reinstall, but it cannot promise updates from earlier or future builds signed with a different certificate.
