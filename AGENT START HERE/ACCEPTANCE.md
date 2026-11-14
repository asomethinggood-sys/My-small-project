# Acceptance gates — do not mark these complete without evidence

## Already performed locally

- [x] Nine offline Python tests pass (schema generation/rejection, lease limits, ten distinct manual wrappers, bounded shared worker, build isolation, no fake assets/APKs, overlay base integrity, fixed UI labels).
- [x] All 12 staged YAML files parse: ten slot entries, one reusable worker, one candidate builder.
- [x] Python byte-compilation and `git diff --check` pass.
- [x] No active workflow or production Android file was changed; no workflows dispatched/pushed.

## APK / native acceptance — NOT performed

- [ ] Apply reviewed overlay in a disposable checkout / authorized working tree. Preserve base-hash guard.
- [ ] Java compilation, debug/release lint, all old JVM tests and new `BetaCatalogTest` pass.
- [ ] Existing emulator engine/TUN regressions and `BetaUiTest` pass.
- [ ] Inspect the beta home AND server dialog screenshots at small display size / large font scale. Audit all ten labels, unavailable state, measured state, preferred selection, permission denial and no source/URI text.
- [ ] Exact minified managed release disables legacy import/location activities and ignores old custom source/profiles.
- [ ] Validate release manifest: app.continuum, versionCode 100, versionName 1.0.0-open-beta, stable expected signing certificate. Record actual APK hashes and sizes.
- [ ] Test universal APK install/reinstall on API26,29,35, API35 16KB and API36; physical ARM64/POCO testing is still required, not implied by x86 emulators.
- [ ] Ensure Rust/native probe tasks terminate within their expected native budget. Java cancels futures and caps worker threads/queues; interruption does not forcibly terminate a native call. If the library hangs, repeated scans can become unavailable. Do not create more threads to conceal this; fix or isolate the probe boundary.
- [ ] Test opening/closing the dialog while checking, rotating Activity, duplicate check taps, and process death. No stale callback may connect or update a destroyed screen.

## Server acceptance — NOT performed; needs explicit run authorization

- [ ] Token can read repo variables, publish per-slot assets and dispatch successor. A denied capability fails once; no retry storm.
- [ ] Missing/off kill switch, missing/expired lease, invalid slot, non-US exit, broken connector and failed end-to-end readiness all prevent publication.
- [ ] Slot assets are distinct, schema-valid, freshly issued and expire within six hours. No real credentials appear in build logs, screenshots or source archives.
- [ ] US geography checks pass for actual exits. An unverified or non-US runner stays unavailable; never change its flag to satisfy UI expectations.
- [ ] Confirm ten actual healthy slots with timestamps/run IDs, not just ten workflow files. Record concurrency/quota limitations honestly.
- [ ] One normal self-dispatched successor rotates each slot without overwriting any other slot. No uncontrolled duplicate jobs.
- [ ] Disable variables, cancel actual jobs and verify no successors remain running/pending. Clean up public slot assets if needed.

## Android multi-server acceptance — NOT performed

Use controlled fixture measurements/failures first, then the authorized real ten-slot pool. Do not expose a production override that accepts arbitrary sources merely to make tests easy.

- [ ] Device checks every reachable advertised slot and auto-selects the lowest successful measured result. Slow slot 01 cannot starve already completed results from slots 02–10 (completion-order collection).
- [ ] Expired, future-dated, wrong-slot, malformed, invalid-TLS and foreign-host records are rejected. Missing/bad slot 03 does not prevent slot 04 from connecting.
- [ ] Preferred manual slot is used when available; documented fallback is used when it fails. Switching preference while probes are in flight does not install the old preference.
- [ ] No live server assets: list shows unavailable, connect does not report success, old single-server subscription is not used as a hidden fallback.
- [ ] Changing a healthy slot's generation or discovering a faster peer does not needlessly restart an active call.
- [ ] Shut down the connected slot; measure failure-detection and reconnection time to another. Explicitly record that established calls/downloads can restart and six-hour rotation cannot preserve TCP state.
- [ ] Expiry watchdog stops payload on an expired slot without bypassing VPN routing; new selection restores connectivity when a valid candidate exists.
- [ ] Disconnect during fetch, native probe, install and expiry callback. No late result restarts the tunnel. Test persisted pause / Android always-on behavior.
- [ ] Wi-Fi/mobile transition, captive portal, airplane mode, Doze, DNS fallback, TLS video segments and sustained voice-like UDP. Measure on the user's network where possible; don't substitute CI timings for Tehran claims.
- [ ] Load/battery test ten release downloads per user per roughly 30 seconds before advertising a public open beta.

Only after these gates pass should an authorized agent publish the new APK and mark it accepted. The supplied manual builder emits a candidate artifact, not evidence of ten live servers or service-specific reliability.
