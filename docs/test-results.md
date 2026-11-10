# Validation record — 2026-11-07

## Follow-up: no-cost experiment (supersedes initial execution limitations)

The task branch was committed and pushed, then real GitHub-hosted tests ran.
The existing main-branch VPN job, repository variables and public subscription
were **not** modified. No VPS was purchased or deployed.

- [Validation run 42410877108](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42410877108): **passed**. Seven unit tests, shell syntax, pinned
  binary checksums, Xray server/client config validation, Caddy adaptation and
  the local SOCKS -> VLESS/WS -> HTTP integration round trip passed.
- Earlier integration runs failed because Xray v26.10.31 defaults to blocking
  private-address egress on VLESS inbounds. Debug logs identified this precisely.
  The fixture now allows only its own loopback address and ephemeral HTTP port;
  deployed configs retain the upstream protection. The failures were not hidden.
- [Transport run 42410877096](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42410877096): **passed**. Both QUIC and HTTP/2 connectors, with and
  without client WS early data, passed real public TLS/WS/VLESS egress probes.
  Profiles from that smoke run have expired. Android import remains untested.

### Measured: GitHub runner, NOT Tehran

Cold HTTPS requests to `https://example.com/` through each candidate. Five samples
per candidate, taken sequentially on one runner. Runner region was not independently
verified; these timings must not be labelled Tehran RTT or user delay.

| Connector | WS early data | Successes | Median HTTP total ms | p95 ms |
|---|---|---:|---:|---:|
| QUIC | off | 5/5 | 283.8 | 374.1 |
| QUIC | on | 5/5 | 226.2 | 256.6 |
| HTTP/2 | off | 5/5 | 412.0 | 481.2 |
| HTTP/2 | on | 5/5 | 327.6 | 364.3 |

Early data was associated with lower cold-request times in this small run, but
sequential sampling, destination variability and two different tunnel hostnames
prevent a general causal/performance conclusion. An earlier baseline-only run
42410694349 measured ~138 ms medians for both transports, illustrating substantial
run-to-run variability. Do **not** choose a Tehran transport or claim <200 ms from
these numbers. `auto` and early-data-off remain defaults until client testing.

### Final implementation recheck

At commit `4dcafb5`, [validation 42410999696](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42410999696)
and [experiment 42410999663](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42410999663)
both **passed**. All four variants again had 5/5 successful measured requests.
These were again **GitHub-runner cold HTTP totals, not Tehran measurements**:

| Connector | WS early data | Median ms | p95 ms |
|---|---|---:|---:|
| QUIC | off | 89.9 | 93.6 |
| QUIC | on | 70.5 | 133.8 |
| HTTP/2 | off | 83.5 | 92.9 |
| HTTP/2 | on | 77.4 | 88.6 |

Importantly, QUIC early data improved the median in this screening but **worsened
p95**. The tiny sample and large between-run variation do not justify a universal
winner or changing defaults. These observations are a reason to collect Tehran
samples, not to claim the <200 ms goal has been achieved.

A manual dispatch of a 30-minute client test window was attempted but rejected
with `HTTP 403: Resource not accessible by integration`. Push-triggered tests
were permitted; manual dispatch permission was not. No permissions or repository
variables were altered to bypass this. The user can dispatch from Actions with
their own authorized account. All smoke-test profiles are expired.

Full logs/artifacts could not be downloaded into this sandbox because GitHub
redirects them to storage hosts outside its allowlist. Run/job results and the
explicitly labelled timing annotations were retrieved through the GitHub API.
Users can open the runs and download the one-day artifacts normally.

The initial record below is retained for transparency; its 'not pushed / not run'
statements describe only the previous turn, not the current test status.

---

## Initial implementation record

## Observed / executed

- Initial branch: `arena/f056ce38-my-small-project`, clean working tree, based on
  `de39507547b53791eb2632f0d17ba13d8554b028`. Inspected existing README and
  `.github/workflows/vpn.yml` before changes. No branch switch, remote push,
  deployment, release modification, or Actions dispatch performed.
- `python3 -m unittest discover -s tests -v`: **4 tests passed**. Coverage:
  stable UUID/path reuse, hostname mismatch rejection, hostname injection checks,
  URI parameter encoding, base64 subscription round trip, loopback Xray binding,
  restricted identity-file permissions, no premature verified URI, median/p95
  calculation, CSV preservation of mock successes and timeouts. Mock timing is
  **not a network measurement**.
- `for f in scripts/*.sh; do bash -n "$f"; done`: **passed**.
- Both workflow YAML files parsed using PyYAML 6.0.3 BaseLoader; each embedded
  `run` block passed `bash -n` after replacing Actions expressions with a literal.
  This is a syntax check, **not** a GitHub Actions execution or actionlint run.
- `python3 -m compileall -q scripts tests`: **passed**.
- `git diff --check`: **passed**.
- GitHub release API returned Xray `v26.10.31` and Caddy `v2.11.9`; Linux x86_64
  release asset SHA-256 digests are pinned in `scripts/download-binaries.sh`.
  Successful API metadata retrieval is not successful binary validation.

## Attempted but blocked here

`bash scripts/download-binaries.sh` followed the GitHub asset redirect and failed
with curl exit 35 (`SSL_ERROR_SYSCALL`) at
`release-assets.githubusercontent.com`, which is outside this sandbox's network
allowlist. No binary was installed. Consequently the attempted Xray config tests,
Caddy adaptation and local integration test could not execute (missing binaries).
These are **not passing tests**. The new `Validate deployment` workflow runs them
in a normal GitHub runner; it has not been dispatched in this session. Run it and
inspect the result before deployment. The validation job does not host a VPN.

## Not deployed / not measured

- No VPS, DNS record, ACME certificate, public TLS/WS handshake or v2rayNG Android
  import has been tested. `scripts/verify.sh` is the required post-deployment
  functional gate; its success would still not establish Tehran latency.
- No Tehran client is accessible. The reported >350 ms baseline is **user supplied**,
  with test mode/URL/sample count unknown. No new RTT, p95, packet loss or throughput
  numbers can honestly be reported.
- Istanbul/Frankfurt VPS latency, provider account eligibility, direct blocking,
  Cloudflare reachability from Iran and Worker egress are **unverified**.
- No claim of <200 ms is made. Cost ranges are budget estimates, not live quotes.

## Required before accepting the change operationally

1. Push this branch through the normal review process; run `Validate deployment`
   and verify every job passes. Do not enable the legacy loop as a substitute.
2. On a dedicated chosen VPS, follow the README to deploy, obtain a real
   certificate, run `verify.sh`, and retrieve `verified-uri.txt` only on success.
3. Check an actual v2rayNG import from Tehran; perform the baseline/candidate
   sessions in `latency-testing.md`, including peak hours and failures.
4. Reboot the VPS and confirm both systemd services return, the same URI connects,
   and certificate renewal state persists. Test shared load/transfer quotas.
5. Fill in actual measurements and state their exact metric; only claim the
   target for the tested ISP/time/conditions and demonstrated statistics.


## Stable Worker relay implementation (subsequent turn)

- `node --test tests/worker.test.mjs`: **9 passed**, using an in-memory KV mock
  and mocked outbound responses. Covers route validation/lease expiry, update
  authentication, size limits, persistence across requests, exact path gating,
  WebSocket/early-data header forwarding, sensitive-header stripping, redirect
  rejection, backend failure and the Cloudflare entrypoint signature.
- Python suite: **9 passed**, including bounded route-update leases, destination
  validation and consistency of the fixed public identity/Worker path. Workflow YAML and embedded Bash syntax
  checks passed locally. CI now includes the Node unit tests.
- The Worker is **not deployed by the agent**. No Cloudflare deployment permission,
  KV binding or shared update secret has been supplied. No live Worker relay,
  Android import, rotation or Tehran measurement has been performed.
- `RELAY_ENABLED` remains opt-in. No main-branch run or repository settings were
  changed. No PR was opened for the unverified Worker path.
