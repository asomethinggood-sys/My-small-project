# Continuum mobile 0.7

Release: https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-mobile-0.7.0-3

Source: d0387f9 on arena/f056ce38-my-small-project. Main is unchanged; no PR created.

## Delivered

- Consumer Continuum home: warm paper/green palette, editorial typography, one connect/disconnect control, session time and explicitly labelled web-request timing (not ping).
- No repository URLs, provider/endpoint/protocol details, raw errors/history, location picker, custom configuration import or editable subscription source on consumer screens.
- Allowlisted notification copy; Android VPN session is named Continuum.
- Managed release settings are rebuilt from an allowlist on reads and writes, clearing legacy custom profiles, source, country selection and credentials. Uses the original built-in subscription.
- Native settings for update interval, compatibility and IPv6, plus honest VPN/privacy explanations. License and source notices remain accompanying distribution assets.
- Release package is app.continuum, not app.nyx.vpn. Build using `ORG_GRADLE_PROJECT_continuumManaged=true` (or `-PcontinuumManaged=true`). Existing Nyx/debug fixtures remain isolated; developer activities are disabled and nonexported in the delivered release. Debug fixture configuration cannot be used in managed release builds.

## Evidence

GitHub Actions run 43437494509: build, compatibility API26 x86, compatibility API35 x86_64 16KB, and publication all passed.

Build gates include Rust/JVM policy tests, debug/release lint, real Android VPN fixture instrumentation, consumer UI privacy assertions with hostile status strings, minified release launch and home-tree assertions, disabled technical-activity checks, APK signatures, ELF/ZIP page alignment, normal universal-APK installation and same-signer reinstall on compatibility emulators. Reviewed actual home screenshot. An earlier API35 compatibility attempt failed without sufficient logging; diagnostics were added, and the complete subsequent run passed. Do not represent this as physical-device testing or exhaustive compatibility proof.

- ARM64 APK: 41,448,009 bytes (~41.4 MB), SHA256 `3335fc782ff7276ef9440a964f6ddc4ece0b1abcd289b5362134958ddbf77786`.
- Universal APK: 143,849,299 bytes (~143.8 MB), four CPU architectures. SHA256 in release SHA256SUMS.
- Source archive, dependency/license references, signing report, network report, screenshots and checksum manifest accompany the release.

## Important limits

A dedicated candidate certificate was generated; stable signing is not provisioned. An older Continuum installation with another signer cannot be updated in place. Uninstall/reinstall may be necessary and clears local app settings. Nyx installs separately. Same-signer reinstall within this build was verified, not upgrade from every historical APK.

No physical POCO/HyperOS test or Tehran network measurement was available. The UI cleanup does not hide backend implementation from APK inspection or traffic analysis, and does not change backend availability. Timing shown in the app is a web-request check, not ICMP ping. Universal distribution is larger than ARM64-only; neither is described as 20 MB.
