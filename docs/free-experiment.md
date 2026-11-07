# No-cost route experiment

No VPS purchase is required for this path. We cannot select an EU region on the
standard `ubuntu-latest` runner label. Do not confuse changing Ubuntu versions,
forcing Cloudflare IPv4, selecting a DNS resolver, or a European-looking edge
hostname with relocating VLESS egress. Paid/custom/self-hosted infrastructure is
outside this experiment's budget. The Actions/Cloudflare restrictions described
in `architecture.md` still apply; experimental use is not a blanket exemption.

## What changed

- **WebSocket early data** is offered as an additional opt-in profile on each
  working connector (`-early-data`). It puts initial VLESS bytes in the WS
  upgrade request using Xray's `?ed=2048` path option. This can remove a wait for
  the WebSocket handshake on cold connections; it cannot reduce physical RTT
  or guarantee faster downloads. This is **not TLS 0-RTT**. It is tested through
  the actual Quick Tunnel before export, but Android import behavior must still
  be checked on your v2rayNG version. Do not manually change the server WS path.

- A bounded `Tunnel transport experiment` workflow tests **QUIC vs HTTP/2** from
  the **same runner**, using the same Xray origin, UUID and WS path. This isolates
  connector transport better than comparing two different random runner regions.
  The two random tunnel hostnames can still take different edge routes; repeat
  trials before attributing a result solely to the transport.
- QUIC is UDP between cloudflared and Cloudflare; HTTP/2 is TCP on that leg.
  HTTP/2 may avoid poor/blocked UDP; QUIC may avoid connection-wide TCP loss
  blocking. Neither changes the phone's VLESS/WS/TLS transport or the US origin.
  **Neither is assumed faster**. The default remains cloudflared `auto`.
- Both candidates must pass real TLS/WS/VLESS -> HTTPS egress checks before an
  importable URI is exported. The existing loop now has the same readiness gate
  rather than publishing immediately when a tunnel hostname appears.
- Configs and diagnostics are kept as one-day workflow artifacts. No existing
  public subscription is overwritten by the experiment. Only validated profiles
  appear, so a failed transport produces no fake working config.
- Five cold HTTPS timing samples per working candidate are collected **from the
  runner**, not Tehran. These test function and gross connector regressions;
  they cannot establish the user's latency or pick the best client-facing route.
- The normal loop keeps its 5h25m serve period, successor queue and cron fallback.
  Set repo variable `CF_TRANSPORT` to `auto`, `quic` or `http2` only after client
  comparison. This does not mutate already-running processes. Leave `auto` if
  there is no repeatable improvement. Set `WS_EARLY_DATA=true` only if the
  early-data profile works and improves your Tehran measurements; default is
  `false`. The loop probes the selected variant before publishing. Revert to
  `CF_TRANSPORT=auto` and `WS_EARLY_DATA=false` to roll back. Versions of both
  Xray and cloudflared are now pinned and checksummed in the loop as well.

## Running the tests / retrieving a profile

Push this working branch; `Validate deployment` runs config/integration tests.
Changes to experiment code also trigger a smoke comparison with **zero hold time**.
Those smoke-test profiles expire immediately after the test; do not import them
as a live service.

For a live client comparison, manually dispatch **Tunnel transport experiment**
on `arena/f056ce38-my-small-project`, selecting 15 or 30 minutes:

```bash
gh workflow run experiment.yml --ref arena/f056ce38-my-small-project -f minutes=30
gh run list --workflow experiment.yml --branch arena/f056ce38-my-small-project --limit 5
```

Open the new run. Wait for the preparation/verification step to pass. During the
bounded test window, copy the `VERIFIED FROM RUNNER ONLY` URI lines in that step's
log, or download the `experiment-RUN_ID` artifact as soon as its upload completes:

```bash
gh run download RUN_ID -n experiment-RUN_ID -D .runtime/downloaded-experiment
cat .runtime/downloaded-experiment/verified-uri.txt
```

Import each URI into v2rayNG. Baselines are labelled `Experiment-quic` and
`Experiment-http2`, with optional `-early-data` variants on the same hostnames. The artifact also contains a base64 subscription file,
connector logs and runner timing CSVs. These public/shared credentials are valid
only until that job ends; logs/artifacts are not persistent hosting. A step
summary is also written, though the UI may not display it until the job ends.
This workflow never self-chains. Cancel it to stop early. Do not run two copies
locally on the same ports.

From **Tehran**, compare the existing US profile and both candidates with the
same real-delay URL/mode, 30 samples each, alternating order. Compare early-data
versus baseline **on the same connector hostname** first, then connector transport. Follow
`latency-testing.md` for failures, peak hours and the acceptance criterion.
Send the per-profile results (not secret keys) to assess whether either connector
setting helps. An unavailable transport is a result, not a reason to hide failures.
A runner-only winning time is **not** enough to select a setting for Tehran.

No speculative BBR/sysctl, TLS verification bypass or multiplexing changes are
applied. Early data remains opt-in, not a new default. Those would change more variables without
proof of benefit; they cannot shorten the Tehran–US route. If both profiles remain
above 200 ms, there is no demonstrated free tuning fix for this infrastructure.

### Compatibility

The pinned Xray version warns that WebSocket is deprecated upstream. It remains
functional in these tests and matches the project's existing v2rayNG protocol.
The client JSON generator uses the current `wsSettings.host` field. A future
migration to XHTTP should be a separately measured compatibility change, not an
unverified claim that changing protocols shortens the US route.
