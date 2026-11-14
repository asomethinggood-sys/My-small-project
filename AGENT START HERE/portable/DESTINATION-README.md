# Continuum 1.0 OPEN BETA — ready-to-run repository

This is the prepared portable export, not the untouched source repository.

## Operator actions

1. Import this tree into your own **public** repository's default branch. Keep your destination `.git` directory; this export contains no Git history or credentials. GitHub Actions must be enabled and permitted to write releases and dispatch workflows.
2. Open **Actions → Start beta → Run workflow**, on the default branch.
3. Wait for the app build, tests and APK publication. The workflow then dispatches all ten prepared server workers automatically. Download the APK from **this repository's Releases**.
4. To end the experiment, run **Actions → Stop beta**.

No source edits, manually created variables, PATs, server profiles, domain purchases or VPS setup are required. Optional existing stable Android signing secrets are used if provisioned; otherwise the build generates a candidate certificate. GitHub account/organization permissions, concurrency and billing limits cannot be bypassed by a workflow.

**Do not use the old APK from the source repository.** Its discovery URLs point there. The automatic build embeds this destination's `GITHUB_REPOSITORY` into the new APK and tests that identity. Repository URLs are not exposed in the app UI. A private repository cannot serve the unauthenticated discovery downloads, so Start beta rejects private destinations.

## Startup and shutdown behavior

Start beta checks registration of all ten worker workflows, creates a non-secret control release, builds/tests the destination-specific APK, publishes it, then enables and dispatches the ten workers. If the build fails, it does not activate servers. This is automatic, but it is not instantaneous: a build and each server's readiness checks take time.

Each slot independently publishes `slot.json` to its own release tag `continuum-beta-01` through `10`. The Android app fetches them, checks real HTTPS latency, and selects a usable server. US labels require the worker's geography/readiness checks. No fake endpoints or timings are included.

There is no experiment deadline. Each worker queues its successor at job start and rotates below the runner time limit. Queued successors are serialized by slot. Failed cycles back off five minutes. Platform outages, exhausted quota or rejected dispatch can still stop a chain; this is not a guarantee of perpetual hosting or uninterrupted TCP sessions.

Stop beta writes a disabled control state FIRST and cancels beta worker runs. Running workers also read that state periodically. A stop during an app build invalidates the pending start generation, so completing the older build cannot reactivate the servers. Control-update jobs are serialized. Cancelling a server job by itself is not the stop mechanism; its queued successor may start while the control state is still enabled.

To restart after stopping, run Start beta again. Do not start twice while already active; Start beta rejects that rather than replacing running servers. Partial activation errors are reported, not presented as ten healthy servers. Run Stop beta before retrying a failed/partial activation.

## Limits and privacy

The release credentials are shared public beta access, just as in the original design. Do not put private keys or personal server credentials in those assets. Hiding infrastructure in the UI does not prevent binary/network inspection. Licenses and corresponding-source notices must remain with redistributed APKs.

Ten simultaneous runners consume roughly 14,400 runner-minutes/day, plus app builds. Verify your support authorization, concurrency and billing settings. Unknown-publisher/install-signature issues, mobile battery management, country-lookup outages and service-specific restrictions remain possible. Tests are not Tehran/physical-POCO measurements.

The imported repository has ONLY the prepared beta/build/start/stop workflows. Legacy scheduled VPN, research and desktop workflows were deliberately excluded so importing it does not accidentally start unrelated jobs. All entrypoints are manual or reusable, not push/schedule triggered.

## Development notes

`PORTABLE-MANIFEST.json` records export file hashes. `portable/control.py` implements the non-secret operator state, using only the destination workflow token. The Android source is already patched; there is no overlay-application task for the operator. The build is reproducible from the checked-in source and pinned existing build scripts. Local builds must set `GITHUB_REPOSITORY=OWNER/REPO` explicitly; CI supplies it automatically.
