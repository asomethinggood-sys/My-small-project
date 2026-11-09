# Source and licensing

Continuum's original Java application and Rust core are GPL-3.0 (LICENSE). The app is not a rebranded v2rayNG build.

## Xray engine (unchanged Go dependency)

AndroidLibXrayLite **v26.10.31**, LGPL-3.0:
- Source/build instructions: https://github.com/2dust/AndroidLibXrayLite/tree/v26.10.31
- Binary: https://github.com/2dust/AndroidLibXrayLite/releases/tag/v26.10.31
- License: LICENSE.libv2ray.
- Go dependency versions/source locations: upstream go.mod/go.sum at that tag, including XTLS/Xray-core (MPL-2.0): https://github.com/XTLS/Xray-core

The unmodified AAR is SHA256-checked. The release's Java binding sources JAR is **not** the complete Go source. Complete native source/dependency/build references are above. Rebuild/replace app/libs/libv2ray.aar and rebuild the open app to relink modifications; no anti-tampering restriction is imposed. Downstream distributors must preserve/provide corresponding sources and dependencies required by each license, not merely the Java binding JAR.

## Rust stage-one core

Owned source: rust-core/. This crate currently has no third-party Cargo dependencies; Cargo.lock is checked in. Toolchain/runtime: Rust **1.85.1**, principally MIT OR Apache-2.0, with exceptions/third-party components described by upstream COPYRIGHT.

- Runtime/source/notices: https://github.com/rust-lang/rust/tree/1.85.1
- Exact build script: scripts/build-rust.sh; Android NDK 27.2.12479018.
- The build copies upstream LICENSE-MIT, LICENSE-APACHE and full COPYRIGHT into release assets as LICENSE.rust-* files.
- Xray is still Go; shipping a Rust .so does not make this an all-Rust application.

Build tools include Android SDK/AGP, Gradle, desugar_jdk_libs and Rust/NDK. Test-only dependencies include JUnit and org.json. No ads, analytics or tracking SDK is embedded. Upstream v2rayNG/AndroidLibXrayLite examples informed native initialization and Android TUN integration, not an application/UI fork.
