# Validation record — 2026-11-07

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
