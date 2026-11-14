# AGENT START HERE — Continuum 1.0 OPEN BETA

## Importing into another repository (latest requested mode)

**Read `PORTABLE-HANDOFF.md` and use `continuum-portable.zip`.** The ready export installs all workflows and binds the app to the destination automatically. After import the operator runs **Start beta**, and later **Stop beta**. No code edits or beta variables are needed. The old source APK cannot read a different repository; Start beta automatically builds the destination APK before starting servers.

`NEXT_AGENT_PROMPT.txt` now describes this portable flow. The sections below document the older, original-repository activation mode only; do not mix its variable-based controls with the portable export's Start/Stop control release.

## Current scope

**The Android APK is built. The next agent's job is server activation, not writing the app.**

See `BUILD-RESULTS.md` for the final APK links, exact build evidence, signing information and remaining live-server checks. The user authorized APK-build CI and build-fix reruns, but **did not authorize this agent to start any of the ten VPN servers**.

There is **no seven-day limit, experiment end date, lease renewal or rechain flag**. After activation, each worker queues its successor and keeps rotating until `ENABLE_CONTINUUM_BETA` is explicitly set to `false`. Per-run timeouts and per-address expiration remain: these keep an individual job below the runner limit and prevent Android from using stale addresses. They do NOT end the experiment.

All ten server workflow templates remain in this folder, outside the active workflow directory. Only the APK builder was installed under `.github/workflows/continuum-beta-build.yml`. No server variables or slot assets were created/changed. Main and the existing single-server `vpn.yml` / `vpn-config/config.txt` remain untouched.

## Delivered files

- `workflows/continuum-beta-01.yml` through `10.yml`: ten distinct manual-start workflows.
- `workflows/continuum-beta-slot.yml`: common worker, one concurrency group per slot, automatic successor queue, stop switch and failure backoff.
- `server/run_slot.py`: existing Xray + Cloudflare Quick Tunnel mechanism, readiness, US checks and isolated release publication.
- `overlay/android/…`: complete reviewed Android replacement/addition files used to build the APK. Existing production source is not silently overwritten in the checkout.
- `apply_overlay.py`, `overlay-base.json`: guarded source application for reproducible builds; no server-start side effects.
- `workflows/continuum-beta-build.yml`: optional manual build-only template; the installed builder already produced the APK.
- `ACCEPTANCE.md`, `BUILD-RESULTS.md`: honest separation between completed app tests and not-yet-run live-server checks.
- `NEXT_AGENT_PROMPT.txt`: activation-only handoff prompt.

Stay on Arena's current branch. The working branch for this session is `arena/f056ce38-my-small-project`; do not switch branches, touch main, or open a PR without permission.

## How the ten slots work

No new directory server or VPS is required. The app uses the original repository-release download approach, now with one independent tag/asset per slot:

```
continuum-beta-01 / slot.json
continuum-beta-02 / slot.json
...
continuum-beta-10 / slot.json
```

Each asset contains schema, slot, generation, issue/expiry times, US country and the generated VLESS/TLS/WebSocket URI. Runtime hostnames and shared beta credentials are created by the worker; no fictional working records are bundled. The app bundles discovery URLs, not permanent Quick Tunnel addresses.

Ten publishers do not race over a shared aggregate manifest. Release-asset replacement can briefly produce a 404, so Android can retain an unexpired previous record, but still probes before selection.

## Android behavior

- Managed `app.continuum`, versionCode **100**, versionName **1.0.0-open-beta**.
- Auto-connect fetches the ten records and measures HTTPS through candidate profiles, with three worker threads and a bounded scan wait. It selects the fastest successful unexpired result, with stable slot-number tie-breaks.
- The Servers dialog lists **US🇺🇸_01 … US🇺🇸_10**, numerically. `Check all servers` performs real checks. `Connect` saves a preferred slot and uses normal Android VPN permission. Initially entries say **Not checked**, not fake ping values.
- A preferred slot is used when reachable. If it fails, the best measured alternative may be used.
- Latency is an **HTTPS request, not ICMP ping**. No Tehran or sub-200 ms guarantee.
- While connected, discovery refresh is scheduled around 30 seconds after the previous check completes. Slow requests, native probes and Android power management can make that longer.
- A healthy active connection is not restarted merely because another peer becomes faster or a new URI is published. Three failed checks trigger reselection. Explicit preference changes, compatibility changes and upcoming expiration can switch sooner.
- Disconnect invalidates the session token and cancels recovery. The expiry watchdog stops expired payload while preserving TUN routing until an alternative is available.
- No repository, URL, endpoint, protocol, custom-import control or raw error is rendered in product UI. Licenses and source notices accompany the APK. Binary/network inspection can still reveal implementation details.
- Until the servers are activated, the app will correctly report unavailable slots; it does not secretly use the old single-server subscription.

## Rotation until the user stops

Each slot queues **one successor at job startup**, before binary installation and serving, like the original loop. Its concurrency group prevents that successor from serving until the current slot finishes. Thus ordinary startup/serving failures also have a queued replacement. Failed cycles wait five minutes before releasing the group, rather than retrying rapidly.

Serving lifetimes are staggered: approximately 246–300 minutes. Each job has a 340-minute ceiling. There is **no experiment-wide expiration**. Setting `ENABLE_CONTINUUM_BETA=false` prevents queued jobs from serving; running workers observe the switch around once per minute. Do not use a calendar variable to shut the experiment off.

A rejected successor dispatch, unavailable runner, exhausted quota or platform suspension can still break a chain. There is no way to promise perpetual platform availability or preserve established TCP sessions across a server's disappearance. Do not repeatedly retry an authorization-denied dispatch or silently introduce another credential.

The user reports support approval and US hosting. Do not repeat the already answered hosting question. Actual US egress is still checked independently by two country services before publication; unverified/foreign slots are not advertised as US. External checks can themselves fail/rate-limit.

## Next agent: activation only

Do not rebuild/redesign the completed APK just to start the servers. Follow these steps **when the user authorizes you to activate them**:

1. Read `BUILD-RESULTS.md` and the activation portions of `ACCEPTANCE.md`.
2. Confirm the current branch and available concurrency/billing budget. Ten simultaneous workers use roughly **14,400 runner-minutes/day**, excluding builds. Do not buy infrastructure or override account controls.
3. Keep `ENABLE_CONTINUUM_BETA=false` while installing the ten wrapper templates and `continuum-beta-slot.yml` into `.github/workflows/`. Do not install another APK builder or overwrite the legacy `vpn.yml`. Retain this folder and the existing shared scripts, which the worker calls.
4. Commit/push only the current branch when authorized. New workflow-dispatch files may need default-branch registration before GitHub will run them by filename. If blocked, explain that specific registration issue and obtain permission for the appropriate default-branch/PR action; do not bypass the standing main/no-PR restriction or repeatedly retry a 403/404.
5. Confirm the workflow token can read the stop-switch variable, upload release assets and dispatch a successor. Permissions are `contents:write` and `actions:write`; platform/account restrictions can still deny access. Never request credentials in chat.
6. Set **only** `ENABLE_CONTINUUM_BETA=true`. There is no expiry or rechain variable to set.
7. Start slot 01 on the actual current branch: `gh workflow run continuum-beta-01.yml --ref <CURRENT_BRANCH>`. Verify its real readiness/publication, then start 02…10. Do not claim ten live exits merely because ten YAML files exist.
8. Check each actual run and slot asset, and verify the built app can select/connect. Observe one rotation and an intentional failure to establish live failover evidence. This is deployment verification, not a request to rewrite the app. Never report seamless calls/downloads across replacement.

If GitHub rejects dispatch because of registration/permissions, do not invent successful server status. That platform blocker must be resolved before activation can be completed.

### Explicit stop

Set `ENABLE_CONTINUUM_BETA=false` **first**, then list and cancel only the actual ten workers' running/pending run IDs. Merely cancelling one job while the switch remains true can let its already-queued successor start. Leave the legacy VPN and unrelated app builds alone.

Normal worker shutdown retires its asset. Forced termination can leave a published address until its hard per-run expiry; Android's probes/expiry checks reject stale connectivity. Remove/expire beta slot assets if needed. None of this changes `vpn-config/config.txt`.

## Rebuild reference (not required for activation)

The installed build-only workflow applies the overlay in CI, builds ARM64 and universal APKs, runs tests, audits packaging and publishes app assets only. It has no server-dispatch permission. The original local attempt installed Java, but this sandbox blocked downloads from Google/Gradle/Rust hosts, so the user explicitly approved build-only CI.

Offline checks:

```sh
python3 'AGENT START HERE/apply_overlay.py'
python3 -m venv .venv
.venv/bin/pip install PyYAML==6.0.3
.venv/bin/python -m unittest discover -s 'AGENT START HERE/tests' -v
```

`apply_overlay.py` is dry-run by default; `--apply` writes only base-hash-checked Android files. It never installs workflows or starts servers.

## Shared beta access and signing

Public slot assets intentionally expose a shared access credential, like the original subscription. UI hiding does not make it private or stop redistribution. Do not put personal/private keys in these records or log the URIs. Assess abuse/rate controls before wide promotion.

Current APK signing is a dedicated candidate certificate, not a provisioned stable release key. Installing over an older differently signed Continuum may require uninstalling first and loses local settings. Preserve distribution source/license notices.
