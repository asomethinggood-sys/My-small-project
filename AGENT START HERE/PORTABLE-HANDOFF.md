# Copy into another repository; then run Start beta

This supersedes the original-repository activation instructions when the destination is a different repository.

## What is prepared

`continuum-portable.zip` is a ready-to-import source tree. It contains the already-patched Android app, shared server scripts and exactly 14 manual/reusable workflows:

- **Start beta** — preflight → automatic destination-bound APK build/tests/publication → dispatch ten workers.
- **Stop beta** — publish disabled control state → cancel beta workers.
- **Build destination Android APK** — reusable builder called by Start beta; may also be run by itself without servers.
- Ten slot entrypoints plus one reusable worker.

No original legacy scheduled VPN/research/desktop workflows are included. Importing or pushing the export does not start any workflow: all entrypoints are manual or reusable, never scheduled/push triggered.

No beta repository variables or PAT are required. A non-secret `continuum-beta-control/control.json` release asset is created automatically. Only destination `GITHUB_TOKEN` permissions are used. Workers check its public download, rather than consuming the GitHub API rate budget on every heartbeat. Start/Stop writes and generation fencing use the authenticated API.

## Why a new APK is automatically built

The APK already published in the source repository has that repository's discovery addresses compiled into it. Copying server workflows elsewhere cannot redirect that existing APK.

The export makes the Android build consume `GITHUB_REPOSITORY`, and its test verifies the resulting discovery address. Thus Start beta builds the correct APK automatically in the new repository; the next agent does not edit application code or type server URLs. Download that destination-specific APK, not the old source APK.

## Import procedure for the next agent

1. Clone/read the source branch in a separate temporary directory:
   `git clone --single-branch --branch arena/f056ce38-my-small-project https://github.com/asomethinggood-sys/My-small-project.git <TEMP_SOURCE>`
2. Extract `AGENT START HERE/continuum-portable.zip` into a new scratch directory. Alternatively run the included exporter with `--output <NEW_DIRECTORY>`; it refuses existing destinations to avoid overwriting user work.
3. Copy the prepared tree into a dedicated public destination repository, preserving its `.git` directory and the branch assigned by Arena. Commit/push there only when authorized. The exported workflow files must be on that destination's default branch for GitHub dispatch/successor registration. If that conflicts with session restrictions, get authorization for the appropriate repository/default-branch change; never silently switch branches or overwrite unrelated files.
4. GitHub Actions must be enabled, and organization/account policy must allow release writes and workflow dispatch. A workflow cannot grant itself permissions denied by the owner. Forks may require Actions to be explicitly enabled. A fresh public import avoids private-release authentication requirements for Android.
5. Run **Start beta** once. Do not run ten individual workflow buttons or configure source URLs. Wait for the build and each worker's readiness gate.
6. Download the APK from the destination Releases and report actual run status. To end the experiment, run **Stop beta**.

The code is predesigned; a workflow still needs build time, a runner, allowed permissions and successful readiness checks. “Automatic” does not mean instantaneous or guaranteed availability. If a build fails, Start beta does not dispatch servers. A partial dispatch failure writes the off state rather than presenting a partially started pool as enabled. Stop beta remains the explicit cancellation/cleanup action.

## Until explicitly stopped

There is no experiment deadline. Each worker queues one successor behind its per-slot concurrency lock; individual jobs stop before the runner limit, and successor jobs replace them. Failed cycles back off. A stopped control generation prevents queued jobs from continuing the chain. Stop during a build invalidates that pending activation; a completed old build cannot undo the stop.

Existing calls/downloads may reconnect during a server replacement. Platform quota, outage and denied-dispatch failures can interrupt a chain. Ten simultaneous runners use roughly 14,400 runner-minutes/day before app builds; verify the owner's support/billing/concurrency scope.

## Scope and verification

- Export/control tests run offline with mocked GH calls; they never start servers.
- A read-only build check compiles the exported Android app using the deliberately different identity `portable-fixture/example`, with unit tests and lint. That fixture APK is never published to users.
- No destination repository was created or altered by this agent, and no Start beta or server workflow was run here.
- A real cross-repository activation still needs the destination to exist and an authorized agent to run Start beta. Do not mistake preparation/build tests for a live deployment.

See `PORTABLE-RESULTS.md` for the final validation run and archive checksum. The copyable prompt is `NEXT_AGENT_PROMPT.txt`.
