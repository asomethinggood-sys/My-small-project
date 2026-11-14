# Build evidence vs activation checks

See BUILD-RESULTS.md for the exact final APK/run. The next agent's job is activation and verification, not completing app source.

## Completed

- [x] Nine offline Python tests: ten unique manual wrappers, bounded per-run lifetime with NO experiment cutoff (tested across years), stop switch, schema/rejection, build isolation, base integrity and fixed labels.
- [x] Staged YAML parsing, Python byte-compilation and base-hash guarded Android overlay validation.
- [x] Java compilation, Rust/JVM tests including BetaCatalogTest, debug and release lint in authorized build-only CI.
- [x] Android emulator engine/TUN regressions (DNS, UDP, exact transfers, HTTPS).
- [x] Beta UI instrumentation and minified release launch.
- [x] ARM64 and universal APK builds, signature verification and ELF/ZIP 16KB alignment checks.
- [x] No ten-slot server workflows activated. No server assets or variables published/configured by this agent.

## App limits to report honestly

- Candidate signing is not a stable-key upgrade promise. Differently signed historical installs may require uninstall/reinstall.
- Emulator checks are not physical POCO/HyperOS or all-device proof. Further API/device coverage is useful, not a reason to ask the activation agent to rebuild the app without a defect.
- Native probe calls have a bounded Java wait and bounded thread pool; Java interruption cannot forcibly stop a stuck native call. No public-pool stress/Doze/battery acceptance is claimed.
- The UI has fixed product labels, but an APK/network analyst can still discover its implementation. Distribution licenses/source are retained.

## Activation verification — intentionally not run yet

- [ ] Token can read ENABLE_CONTINUUM_BETA, publish per-slot assets and dispatch its queued successor. A denied operation is not endlessly retried.
- [ ] All ten installed workflows are dispatchable on the approved branch. Resolve default-branch registration only with appropriate authorization.
- [ ] Off switch prevents serving and queued successors. No experiment date/deadline exists; each new cycle gets its own fresh endpoint lifetime.
- [ ] Actual US geography checks, TLS/WS/VLESS readiness and valid slot records before advertisement.
- [ ] Ten real healthy slots (record actual run IDs/times); no duplicate publishers per slot. No fictional availability/latency.
- [ ] Real Android selection against activated slots; preferred selection and automatic measured choice match reachable candidates.
- [ ] Normal queued successor runs after its predecessor releases the slot concurrency group. Ordinary failed cycles back off before releasing the queued replacement.
- [ ] Deliberate connected-slot failure leads to alternative selection. Measure actual recovery time and report interruption of existing sessions honestly.
- [ ] Explicit stop: disable the variable first, cancel only beta running/pending jobs, verify no replacements serve afterward. Leave the old single-server VPN untouched.

The APK can be downloaded before activation, but it will not invent working exits. Publishing the app is not evidence that ten public servers were started or that live call continuity was proven.
