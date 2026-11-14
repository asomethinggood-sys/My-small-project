# START HERE — Continuum 1.0 OPEN BETA handoff

## Status: dormant source candidate, NOT a built or deployed beta

The latest instruction was **do not start workflows**. It was followed:

- No workflows were dispatched, no servers started, no release assets published, no repository variables changed, and no push was made.
- All new work is staged inside this folder. Existing `.github/workflows`, Android production files, main, and Windows release are unchanged.
- **No new APK exists.** This workspace has no Java, Gradle or Android SDK. Building through CI would start a workflow, which was explicitly prohibited. Do not rename or present the previous 0.7 APK as 1.0.
- Local offline checks: 9 Python tests passed, YAML parsed, Python compiled, and the Android overlay base-hash check passed. **Java compilation, Android lint, instrumentation and real ten-server/failover tests have not run.** Fix any issues those checks find before calling this finished.

Base: `9ec2af0`, branch `arena/f056ce38-my-small-project`. Stay on the branch Arena currently assigns; never silently switch branches. This folder is persisted workspace work, not a pushed deployment.

## Files

| Path | Purpose |
|---|---|
| `workflows/continuum-beta-01.yml` … `10.yml` | Ten independent, manual-start entry workflows |
| `workflows/continuum-beta-slot.yml` | Shared implementation with per-slot concurrency, timeout and off switch |
| `server/run_slot.py` | Start existing Xray/Quick Tunnel path, verify readiness and geography, publish one slot, queue its successor |
| `overlay/android/…` | Full replacement/addition source files for the new Android app |
| `overlay-base.json` | Original-file hashes to prevent overwriting later work |
| `apply_overlay.py` | Dry-run by default; `--apply` installs Android files only, never workflows |
| `workflows/continuum-beta-build.yml` | Manual APK candidate build, with NO server-start or release-publishing permissions |
| `tests/test_staging.py` | Offline handoff safety/schema tests |
| `ACCEPTANCE.md` | Required build, device and failover acceptance checklist |
| `NEXT_AGENT_PROMPT.txt` | Copyable prompt for the next agent |

No script in this folder executes anything merely by being opened or imported. Workflow YAML outside `.github/workflows/` is not registered with Actions.

## Architecture — same discovery mechanism, ten independent slots

There is no new directory server or paid VPS. The existing project release-download mechanism is used. Each slot has its own release tag, so ten publishers cannot overwrite a shared aggregate file:

```
continuum-beta-01 / slot.json
continuum-beta-02 / slot.json
...
continuum-beta-10 / slot.json
```

Each asset has schema version, slot number, generation, issued/expiry times, verified `US` country and the generated TLS/WebSocket VLESS URI. Hostnames and credentials are generated at runtime; none are fabricated or prefilled. An app can ship the ten **discovery URLs**, not ten forever-valid Quick Tunnel addresses.

The app's fixed discovery URLs use the existing repository identity. It renders only locally generated labels **US🇺🇸_01 … US🇺🇸_10**. It does not display the repository, URIs, hostnames, protocol details or custom import controls. Required distribution licenses/source remain intact. Binary inspection can still reveal implementation details.

### Android behavior

- Version `1.0.0-open-beta`, versionCode 100, managed `app.continuum` release. Existing debug fixture package remains isolated.
- Auto-connect fetches the ten slots and measures full HTTPS requests through candidate profiles, with three worker threads and a bounded scan wait. Picks the fastest successful unexpired result; stable slot-number tie-break.
- The Servers dialog lists all ten slots numerically. `Check all servers` performs real checks; `Connect` saves a preferred slot and goes through normal Android VPN permission. Initially entries are **Not checked**, not fabricated ping values.
- Preferred slot wins when reachable. If unavailable, the best measured alternative is used. Preference is not a hard geographic lock; all advertised slots must be US-verified.
- “Latency” is an HTTPS request, **not ICMP ping**. There is no claim of sub-200 ms or Tehran performance.
- While connected, discovery refresh is scheduled about 30 seconds **after the previous check completes**. Slow network calls, Android power management, or a bounded scan can make the real interval longer. Ten asset reads per refresh per user has a real bandwidth/rate cost; load-test before public promotion.
- A healthy active connection is retained even when another slot becomes faster or a replacement URI appears. Three failed checks trigger reselection; explicit selection/compatibility changes can switch immediately. An expiring active slot is reselected, with an expiry watchdog that stops payload while retaining TUN if needed.
- Disconnect invalidates the session token, cancels retries and uses the existing service stop watchdog. Delayed probes must not reinstall a disconnected tunnel.
- Empty/expired/unreachable pools show unavailable and retry; they do not silently fall back to the old single-server subscription or fabricate a connection.

### Server rotation and limits

Uses the existing pinned download scripts, `scripts/continuum_server.py`, tuning script, and full TLS/WS/VLESS readiness test. A hostname appearing in a connector log is not enough to publish.

Slot lifetimes are staggered, roughly 246–300 minutes, below the job's 340-minute ceiling. A healthy serving slot queues ONE successor near its end, behind its own concurrency lock. The other nine slots can carry new connections during that slot's gap. There is no seamless migration of established TCP/UDP application sessions; calls and downloads may reconnect.

This is **not an unlimited unattended loop**. Rotation is gated by an explicit renewable experiment lease of at most seven days, a global off switch, and a separate rechain switch. Renew the lease deliberately if continuing the experiment. No schedule or watchdog silently resurrects disabled slots. Early startup failures, process death, US-geography-check failure, exhausted quota or denied dispatch stop that slot and require operator attention. This fail-closed behavior is intentional; do not add an unbounded 403 retry storm.

The user reports GitHub support approved the experiment and US hosting. Do not repeat the already answered “where will it run?” question. Nonetheless, runner labels alone do not attest an actual exit country: each worker requires two independent country checks to agree on US before publishing. Those external checks may fail/rate-limit; never relabel a foreign/unverified exit US to make a test green.

## Safe next steps (READ before running)

### 1. Offline review — no workflows needed

```sh
python3 'AGENT START HERE/apply_overlay.py'
python3 -m venv .venv
.venv/bin/pip install PyYAML==6.0.3
.venv/bin/python -m unittest discover -s 'AGENT START HERE/tests' -v
```

Review all source changes, especially lifecycle races, native probe cancellation, the generation/expiry boundary and release settings. The UI and service each have their own bounded process-local probe pool; do not expand concurrency casually.

### 2. Build an APK only after build permission / in an equipped local environment

Applying the overlay changes Android sources, not workflows:

```sh
python3 'AGENT START HERE/apply_overlay.py' --apply
```

Local requirements: JDK 21, Gradle 8.11.1, Android API/build-tools 35, NDK 27.2.12479018, pinned Rust toolchain supplied by the existing build scripts, and the checksum-verified native AAR. Existing build scripts download missing dependencies. Then, from repo root:

```sh
bash android/scripts/fetch-core.sh
cd android
ORG_GRADLE_PROJECT_continuumManaged=true gradle --no-daemon -PtargetAbi=x86_64 :app:testDebugUnitTest :app:lintDebug
ORG_GRADLE_PROJECT_continuumManaged=true gradle --no-daemon -PtargetAbi=arm64-v8a :app:assembleRelease :app:lintRelease
# Copy/hash ARM64 output before the next build overwrites it.
ORG_GRADLE_PROJECT_continuumManaged=true gradle --no-daemon -PtargetAbi=universal :app:assembleRelease
```

Provision the existing stable signing secrets privately; never paste keys/tokens into chat. A new candidate signer can require uninstalling the old app and losing settings. Do not present candidate signing as a reliable upgrade path.

Alternatively, AFTER permission to run an APK build, install **only** `workflows/continuum-beta-build.yml` into `.github/workflows/`. Commit/push ONLY the current session branch when authorized. That workflow applies the overlay itself, builds/tests candidates, and uploads artifacts. It cannot start the ten servers or publish a public beta release. Upload is labelled **NOT YET ACCEPTED** until the checklist passes.

New `workflow_dispatch` files often need registration on the default branch before GitHub will dispatch them by filename, even with `--ref`. Do not circumvent the standing main/no-PR restriction or guess that a branch push is sufficient. If registration is required, explain the blocker and obtain explicit authorization for the appropriate PR/default-branch change in a future authorized session. Do not repeatedly retry a 403/404.

### 3. Deploy the ten workers only after explicit activation authorization

Do not do this under the current no-start instruction. Once authorized:

1. Confirm support/billing scope, repository public/private behavior, available job concurrency and action-minute budget. Ten concurrent workers consume roughly **14,400 runner-minutes per day** before build time. Quotas and platform availability can prevent ten simultaneous slots.
2. Install the ten wrapper YAML files plus `continuum-beta-slot.yml` into `.github/workflows/`. Keep `ENABLE_CONTINUUM_BETA=false` during installation. Never replace the old `vpn.yml` or its `vpn-config/config.txt` asset.
3. Configure repository variables (not secret values in chat):
   - `ENABLE_CONTINUUM_BETA=true` only when ready to start.
   - `CONTINUUM_BETA_RECHAIN=false` for initial one-cycle acceptance; set `true` only after rotation tests pass.
   - `CONTINUUM_BETA_EXPIRES_AT=<UTC Unix seconds>`: explicit deadline 10 minutes to seven days ahead; use a short initial trial. Normal four-to-five-hour rotation needs a deadline long enough to test it.
4. Confirm the job token can read the kill-switch variables, upload release assets, and dispatch its successor. Workflow token uses only `contents:write` and `actions:write`; access restrictions may still block these operations. The worker fails closed on missing capability.
5. Start a single slot first, inspect only safe status, confirm its published schema/expiry and real Android connection. Then start the other nine once that works. Do not claim ten live servers from ten YAML files.
6. To dispatch a specific reviewed file after authorization: `gh workflow run continuum-beta-01.yml --ref <CURRENT_SESSION_BRANCH>`. Repeat with 02…10 only after acceptance. Read the actual current branch with `git branch --show-current`; do not invent a branch/ref or switch branches.
7. Test intentional shutdown and normal successor replacement before enabling rechain. Ten quick tunnels provide redundancy, not a 24/7 SLA, load balancing across established calls, or preservation of an old TCP session.

### Stop / rollback

First set `ENABLE_CONTINUUM_BETA=false` and `CONTINUUM_BETA_RECHAIN=false`; running workers check the off switch about once per minute. List the ten workflows' actual run IDs and cancel only their running/pending jobs. Do not cancel the unrelated legacy VPN or desktop/mobile build runs. If needed, remove/expire the ten beta slot assets. Worker cleanup attempts retirement; forced cancellation may leave an asset until its hard expiry, so clients still probe and reject stale entries.

Leave `vpn-config/config.txt` untouched. Reverting the Android overlay or reinstalling the original app is separate from shutting down workers. Both versions use the same managed package ID; signing and versionCode affect rollback installation.

## Publication / privacy warning

Like the original public subscription, these release assets expose a **shared beta access credential**. UI hiding does not make it private or prevent extraction/sharing. Do not put personal/private server keys in these records, logs or artifacts. Public open-beta abuse/rate controls are not implemented by this staged experiment; assess them before wide promotion. Preserve legal attribution assets even though technical information is absent from product screens.
