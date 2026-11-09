# Live phone acceptance: findings and corrective work

The user confirmed the private workflow-hosted phone connection works. They also reported that selecting Germany produced French exits and that latency was high. This establishes phone connectivity, **not correct country selection**. The country discrepancy remains an acceptance defect until the actual phone-visible exit and the reporting source are compared.

## Why the earlier evidence was insufficient

The private trial checked HTTPS geography and UDP directly inside the upstream namespace. It did not independently inspect the issued HTTPS/VLESS/WebSocket route used by the phone. The earlier namespace check could also skip the third geography source after two sources returned country fields. Two databases agreeing on Germany does not establish that every database agrees, nor does it prove that the phone followed the measured path.

## Corrective changes

- Query all configured geography sources rather than skipping the third one. Any observed country conflict rejects the requested country; differing observed IPs also reject the gate.
- Include the observed exit IPv4 and verified country in sanitized evidence, so the phone's reported exit can be compared. This is an upstream public exit address, not the phone's residential address or the service's credential-bearing route.
- Before handing out phone settings, acquire an actual authenticated lease over HTTPS, construct the exact issued TLS/WS profile, and run UDP DNS plus independent HTTPS geography checks through a temporary local SOCKS client using that profile. There is no freedom/direct outbound or proxy bypass in that client.
- After startup, use that issued-route check for periodic pool health. Country disagreement invalidates the pool and revokes its sessions; do not silently relabel Germany as France or fall back to the default connection.
- Give internal health leases a separate credential/quota so they do not consume the phone's two renewal slots. Diagnostic credentials are not delivered or logged.
- Do not cancel an ongoing private test merely because a non-launch validation commit touches its scripts.

The full-route verifier is runner-originated. It tests the same issued route, but phone-side routing, third-party proxy settings, browser location behavior and database disagreement still require the phone's observed IP/source to diagnose conclusively. Printed HTTPS timings are runner measurements, not Tehran/phone ping.

## Routing overhead

The gateway previously relayed a WebSocket stream into a per-lease loopback listener, which then relayed again into the isolated pool. It now opens a tracked stream directly into the pool: one fewer local TCP hop and one fewer forwarding worker per connection. Both paths share flow quotas, lease generation checks, expiry enforcement and socket revocation. The default route is unchanged.

This removes redundant local forwarding. It does **not** justify claiming a specific latency reduction: the phone-to-edge, connector-to-runner, runner-to-upstream and destination RTTs can dominate. TLS, authentication, isolation and the country upstream are not removed to improve a benchmark.

## Scope remains bounded

The phone trial is personal, finite and manually launched. There is no automatic perpetual runner rotation, no 30-country availability claim, and no grant to redistribute providers to other users. Permanent availability and additional real country pools are separate acceptance/deployment work.
