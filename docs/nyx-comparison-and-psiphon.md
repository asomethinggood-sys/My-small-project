# Nyx: bounded candidate comparison and local Psiphon results

## Real provider comparison

Run [42659139801](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42659139801), commit `b1ccf68`, performed six sequential private experiments on one GitHub runner: two rounds of three German VPNBook/OpenVPN candidates. All samples, including failures, were retained in `comparison.json`.

| Candidate | Full checks passed | Consecutive successes at end | Research gate |
|---|---:|---:|---|
| DE20 / UDP 53 | 1 / 2 | 0 | Not stable |
| DE20 / UDP 25000 | 0 / 2 | 0 | Not stable |
| **DE220 / UDP 53** | **2 / 2** | **2** | **Passed bounded gate** |

“Full checks” requires authenticated connection, UDP DNS, HTTPS, matching exit-IP observations, two independent Germany geolocation results, successful tunnel-drop blocking, unchanged host routes, and correct binding to the selected server/port. The three incomplete samples did not obtain the full country-verification evidence; they are not proof of a different exit country or a completely dead transport. **All six samples passed UDP DNS and post-stop blocking.**

Two consecutive samples are a small smoke-test threshold, not a long-term availability guarantee or Tehran latency measurement. Every pool was stopped after its sample. All result rows retain `selectable=false` and `shared_use_approved=false`. This does not authorize public redistribution through a personal-use provider.

### Result recovery

The detailed per-probe notices exhausted the useful annotation budget in the original step, hiding its final comparison notices. The complete artifact was retrieved and summarized in a separate job in [42660895660](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42660895660). No provider tests were repeated to recover those results. The one-off recovery job was then removed so future workflows do not depend on an expiring artifact.

Future comparison runs have a dedicated summary step with at most nine notices: three candidate summaries and six sample outcomes, plus a Markdown job summary.

## Implemented comparison controls

- `config/egress-experiment.json`: explicit three-candidate/two-round plan.
- `scripts/egress_batch.py`: sequential execution on one runner, sample timeouts, overall 15-minute budget, atomic intermediate reports and retention of all failures.
- A timeout stops further connection attempts; incomplete rounds cannot pass the gate.
- Candidate identity is checked at the browser selection, downloaded remote/port, probe result and summary layers.
- Strict boolean safety checks, fresh samples, distinct round numbers and two consecutive successes are required. Duplicate samples, wrong endpoint metadata, stale records and truthy strings cannot create a pass.
- Live comparisons now require an intentional `[provider-test]` push commit or the workflow's `live_provider_test` input. Ordinary code changes still run local integration tests without automatically contacting public VPN servers.
- The browser uses the normal official download UI and does not solve or bypass verification challenges.

## Real local Psiphon transport test

The official Psiphon source documents both local-proxy and packet-tunnel modes. The console client also exposes packet-tunnel flags. That is not proof that an arbitrary public server supports our desired UDP/country policy.

This increment tested **local OSSH transport** using the upstream release-candidate binary repository pinned to commit:

`0f968b4dd6981b75aad9c72b51e39edfefec52ff`

Both Git blob identities and measured SHA-256 hashes are checked before execution:

- Client: `d83dcaa632b265536852e2d97c45eb4831960f8dbcb2d8638293d5958483705b`
- Server: `073769485c5b5817e042f7f0e9a51a1b09cd1050ccb61d667f62038874d7db43`

The upstream repository labels these **release candidates**, not production releases. The fixture generates its own temporary server identity and keys, disables remote server-list fetching/tactics, and runs entirely inside a namespace with loopback only and no Internet route.

Passed locally and in run **42660895660**:

1. Local Psiphon client establishes an OSSH tunnel to the local fixture server.
2. HTTP travels through the client's SOCKS proxy and that tunnel to the local origin.
3. A second client with a changed expected SSH server key cannot reach the origin.
4. The original correctly configured client remains usable.
5. Processes, namespaces and temporary identities are cleaned up; host main routes remain unchanged.

The HTTP fixture uses a public-looking address assigned only to the isolated loopback. Psiphon's bogon protections were retained rather than disabled to allow loopback forwarding. An initial fixture failure exposed a missing data directory; it was created explicitly before client startup.

**Not tested:** public Psiphon network acquisition, country selection, packet-tunnel UDP, public sharing permissions or production suitability of the RC tools. No Psiphon countries or providers were added to the available-exit counts.

Relevant files:

- `scripts/egress-psiphon-tools.sh`
- `tests/egress_psiphon_kernel.py`
- `.github/workflows/egress-research.yml` (`psiphon-local` job)

Primary upstream documentation:
- https://github.com/Psiphon-Labs/psiphon-tunnel-core
- https://github.com/Psiphon-Labs/psiphon-tunnel-core/tree/master/ConsoleClient
- https://github.com/Psiphon-Labs/psiphon-tunnel-core-binaries

## Validation and remaining work

**82 Python tests and 4 browser-policy tests pass.** Real local OpenVPN, WireGuard, Xray/WireGuard and Psiphon fixtures pass on the runner. The observed DE220 result is historical, bounded research evidence, not a currently running service.

Still unfinished: public multi-provider provisioning, sustained health/recovery and authorization, authenticated app-facing session control, production country routing/publication, 30-country availability, Tehran measurements, and the Nyx APK. The existing shared connection and working app were not modified. No PR or production profile was published.
