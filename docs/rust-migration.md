# Rust migration: scope, status and signing prerequisite

## Agreed target

Migrate the **app-owned core** to Rust while keeping Android integration and the working Go Xray engine. Not a rewrite of the server workflows, Worker or whole repository. Rust is not itself evidence of lower ping or battery consumption.

## Stage one implemented

- Dependency-free Rust 1.85.1 core, pinned Cargo.lock, real ARM64/x86_64 JNI builds.
- Rust scheduling/health policy, generation-token transitions, HTTP validator eligibility, subscription backoff, network-change comparison, diagnostic classification policy and counters.
- Primitive-only JNI ABI without retained native heap handles or raw Java-object access. R8 keeps JNI names. No silent Java fallback disguises a missing native library.
- Android default-network callback rather than reacting to every available physical network. Rechecks on relevant transitions, without automatically rebuilding healthy sessions.
- HTTPS ETag / Last-Modified / 304 handling scoped to the exact source and redirect resource. Only syntactically valid profiles enter the HTTP body cache. This cache is separate from the last endpoint-verified profile cache.
- Fetch failures back off to 15 minutes. Explicit Connect, Check now and default-network changes bypass that backoff. An in-flight old failure cannot overwrite a newer forced retry. The cache is process-local, bounded to four sources, and cleared with process death.
- Settings exposes a local, user-shared diagnostic snapshot. It allowlists Android version, ABI, TUN/engine flags, heuristic endpoint-check failure class, operation duration, network/check/fetch counts, process CPU time and PSS. It omits endpoint addresses, profiles, credentials, browsing history, raw exceptions and network names.
- Optional securely provisioned release signing; fallback is transparently labelled disposable preview signing.

## Not finished

**This is not a completed Rust migration.** Profile/URI parsing, JSON configuration generation, subscription HTTP transport/cache storage and Android orchestration still have Java implementations. The migration is staged to retain parity and regression coverage.

Next stages:
1. Move profile parsing/validation and canonical identity into Rust behind a bounded, safely marshalled JNI interface. Differential tests must cover all current protocols, Unicode/percent/Base64 edge cases and rejection of insecure options.
2. Move Xray JSON construction and subscription cache/state decisions to Rust. Keep Android HTTPS/certificate/network APIs as platform adapters where appropriate.
3. Move the orchestration state machine and report construction into Rust, retaining Android Activity/VpnService/Binder adapters.
4. Re-run complete native/TUN tests and physical ARM tests at each boundary; retain prior APKs for rollback.

Default-network monitoring is not proof of interruption-free Wi-Fi/mobile handoff. Endpoint-error classification is heuristic, not independent DNS/TLS/transfer-stage diagnosis. CPU/PSS snapshots are not idle rates, battery savings or a controlled A/B benchmark. Physical-device handoff, full diagnostics and performance experiments remain pending.

## Stable signing: administrator action required

The current GitHub integration returned HTTP 403 for Actions-secret access. No private key was generated or stored in the repository. CI confirmed stable signing was not configured.

A repository administrator must provision these **GitHub Actions secrets through trusted private tooling or GitHub Settings**, never through chat or source files:

- CONTINUUM_SIGNING_KEY_B64 — base64 of the private release keystore (base64 is encoding, not encryption).
- CONTINUUM_STORE_PASSWORD
- CONTINUUM_KEY_ALIAS
- CONTINUUM_KEY_PASSWORD

Generate and securely back up the keystore in a trusted environment. Do not lose/rotate it casually: retaining the same signing identity is necessary for in-place updates. Restrict release builds and secret access to trusted code/reviewers; a malicious Gradle/build-script change could read signing secrets during a trusted build.

CI decodes the key only into RUNNER_TEMP with mode 0600, outside the checkout. Partial signing configuration fails closed. APK-SIZE.txt records the actual signing mode and SIGNING-CERTIFICATE.txt exposes only public certificate information. The key and passwords are not release artifacts. Existing preview certificates cannot be retroactively replaced; switching to the stable key may require one final uninstall/settings reset.

## Build

On Linux with Rustup, JDK 21 and Android SDK installed, the normal Gradle preBuild task invokes scripts/build-rust.sh. It runs Rust tests, builds the host JNI library for JVM tests, installs the pinned Android Rust target and cross-compiles with the pinned NDK. Generated target directories and JNI binaries are ignored by Git. Source and licenses accompany successful APK releases.
