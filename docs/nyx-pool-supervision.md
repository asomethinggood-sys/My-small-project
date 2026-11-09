# Country pool health supervision

`scripts/egress_supervisor.py` schedules trusted health adapters for pools that an operator has already approved and provisioned. It does not acquire accounts, approve shared use, deploy TLS, or infer availability from discovery metadata.

## Guarantees and boundaries

- Exactly one probe worker per pool, at most 32 pools; no replacement worker is created while an old callback is stuck.
- Finite probe deadline, explicit cancellation event, and rejection of late results. Adapters must independently bound network/subprocess operations and honor cancellation; Python cannot forcibly stop an arbitrary callback thread.
- Health results must be `Evidence` with matching country, complete safety flags and fresh monotonic expiry. Per-probe tickets prevent invalidated/old evidence from reviving a failed pool.
- One pool's failed probe revokes that pool's leases and existing transport without globally switching another user's/default route.
- Maintenance sweeps run even while probes hang. The existing ingress independently enforces transport expiry, so maintenance isn't the only expiry barrier.
- Shutdown cancels pending probes and closes the controller/data plane. Unexpected maintenance failures fail closed instead of leaving a nominally healthy API.
- Callback exceptions are never logged: upstream errors can contain private credentials or endpoints.
- `run(stop, max_seconds=900)` is bounded, with an upper bound of six hours; this is not an indefinite GitHub-hosted VPN service.

The owning runtime must call `tick()` at least once per second, or use the finite `run()` loop. The gateway must stay behind a trusted HTTPS frontend. Neither public HTTP clients nor catalog snapshots may provide `Evidence`.

## Validation

Unit tests cover independent pool failure, expiry during blocked probes, cancellation, no worker multiplication, rejection of late/wrong-country/expired evidence, shutdown and finite owner-loop cleanup. Existing socket tests separately prove transport teardown and per-user isolation.

The Android integration fixture uses this scheduler with explicitly synthetic local probes. This proves scheduling/control integration, not independent German/French geography. A production adapter must gather real full-path evidence from its provisioned pool. The existing bounded VPNBook research probe tears its tunnel down after measurement and must **not** be repurposed as proof that a persistent service pool is still alive.

## Still not provisioned

No live provider pool, runtime host, public gateway, stable release signing identity or production health adapter is created by this module. Those remain release/deployment gates, not booleans to flip to make the UI display countries.
