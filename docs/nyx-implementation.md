# Nyx VPN: implementation status and server contract

## Current: real German exit observed on the runner

See `docs/nyx-live-provider-results.md`. Run **42656691009** acquired a German
VPNBook OpenVPN config through the official UI, authenticated it in a bounded
isolated experiment, passed UDP DNS and HTTPS, and received matching exit IPs and
two independent `DE` geolocation results. Host routes remained unchanged and the
test tunnel was stopped. Xray/WireGuard and local OpenVPN integration also pass on
GitHub Actions. **73 Python tests and 3 browser-policy tests pass.** Repeat run
**42657167660** passed the stronger UDP/HTTPS drop checks, but geolocation HTTP,
timeout and DNS failures prevented a new country confirmation. The pool remains
unpublished and non-selectable; one successful country observation is not reliability.

This supersedes earlier statements below that runner-side downloads/public-provider
connections were blocked or untested. There is still no new published country
service, no established 30-country availability, and no new Nyx APK. Public sharing
permission and production/app integration remain gates.

## Earlier: reusable WireGuard pool lifecycle

See `docs/nyx-pool-manager-results.md`. **53 unit tests pass**, and the reusable
manager passed real local encrypted TCP/UDP/DNS tests, including the system
resolver and full resource cleanup. Session health probes now require one-use
tickets to reject stale results. The pinned Xray download failed at its release
asset redirect, so Xray integration and the Nyx APK remain unfinished. All provider
connections/country claims remain unverified; the working backend is unchanged.

## Earlier executed work: real local encrypted isolation

See `docs/nyx-kernel-results.md` for the current results and remaining blockers.
The full local suite now passes **43 tests**. Real two-pool WireGuard kernel
handshakes and TCP/UDP/DNS isolation tests passed with the legacy firewall,
including tunnel-removal, independent-pool survival and an IPv6 positive control.
OpenVPN config sanitization is implemented but not provider-tested. nftables is
unsupported in this sandbox and remains unverified. This supersedes earlier
statements below that all routing tests were only simulated; it does not supersede
the lack of public provider tests, production integration or a Nyx app build.

## Second increment: multi-provider contract and isolation boundaries

- Added `config/egress-adapters.json`: eight distinct provider/type entries, including VPNBook OpenVPN, VPNBook WireGuard, WARP and Psiphon. These are capability/status records, not eight working adapters. The catalog now lists all entries under each country's `exits`, without inventing discovered or verified counts.
- Added `scripts/egress_config.py`: strict WireGuard input parser producing `wg` configuration separately from addresses/DNS/MTU. Rejects shell hooks, unknown/duplicate directives, private or unresolved endpoints, partial default routes and invalid keys. It does not execute wg-quick or change networking. Returned private configuration must never be logged/artifacted.
- Added `scripts/egress_sessions.py`: thread-safe bounded in-process country pool/session controller. Requires trusted fresh probe evidence, enforces UDP requirements, and revokes only the affected pool's sessions on failure. No wrong-country/default fallback. This is not a network API or kernel firewall, and evidence is synthetic in unit tests.
- Added 11 boundary/session tests. Full local Python suite: **32 tests passed**. Generated the offline catalog successfully. Research workflow now includes both test suites.
- Inspected the official Psiphon tunnel-core repository. Source availability alone does not establish unattended public-network provisioning, supported country availability, arbitrary UDP support or permission to re-share the provider network. Those remain unverified: https://github.com/Psiphon-Labs/psiphon-tunnel-core

Still not implemented: OpenVPN sanitization, VPNBook/WARP/Psiphon provisioning, kernel namespace/firewall lifecycle, authenticated remote session API, live multi-country tunnel tests, phone measurements or Nyx app integration. No live discovery, upstream connection, production change, workflow execution or APK build occurred in this increment. Do not describe control-model tests as real routing isolation tests.

## First increment

- `config/egress.json`: 30 target countries and six explicitly gated provider entries.
- `scripts/egress_catalog.py`: bounded official VPN Gate CSV metadata discovery, deduplication, country counts, provider counts, expiry and atomic output. No external dependencies.
- `tests/test_egress_catalog.py`: 12 tests including malformed data, private addresses, conflicting country labels, size limits, failed refresh and no discovery-to-verification promotion.
- `.github/workflows/egress-research.yml`: manually dispatched, five-minute maximum research workflow. One directory fetch, no tunnel connections, no self-chain, no production publication. Artifacts contain sanitized metadata only.

Local validation: 21 Python tests passed, including all 12 new tests. No live provider fetch or tunnel test has been performed. The current workspace only permits outbound access to specified code/package hosts, not the VPN directory. Existing workflow-dispatch permission failures must not be repeatedly retried. The new workflow has not been dispatched or pushed in this increment.

Run the offline catalog:

```
python3 scripts/egress_catalog.py
```

In an authorized network environment, a single live directory fetch is available:

```
python3 scripts/egress_catalog.py --live
```

Both write `.runtime/egress/catalog.json`. This is research metadata, not a connectable subscription or an app API. A fresh failed fetch replaces prior observations with an empty failed result and returns nonzero. A process terminated externally can leave an earlier file on disk: consumers must enforce expiry and refresh success, never use artifact presence as readiness proof.

## Meaning of counts

- `discovered_servers`: distinct provider/server IPs from a fetched directory, not verified endpoints. Addresses and configuration bodies are discarded from the output.
- `discovered_providers`: providers represented among those discovered servers, not the number of entries in our registry.
- `verified_servers` / `verified_providers`: zero until an actual isolated tunnel and its checks pass.
- `selectable`: always false in this increment.
- Country labels describe directory claims, not verified geography.
- Missing countries remain visible as unavailable; neither a static advertised hostname nor a configured provider inflates the counts.

## Per-user routing architecture to implement next

The user's requested behavior is not a global country switch. Keep the existing default ingress and route untouched. A future authenticated session request selects a verified country pool and receives a short-lived route identity bound server-side to that pool. Other users retain their own choices or the existing default.

Proposed structure:

```
existing default connection -> existing direct route (unchanged)
country session A -> restricted ingress A -> isolated Germany upstream
country session B -> restricted ingress B -> isolated Japan upstream
```

A country pool can share a validated upstream across permitted sessions; it need not spawn a new VPN process for every person. Separate sessions still require unguessable scoped credentials, bounded lifetime, quotas and server-side country binding. Never trust a caller-provided namespace, port, provider command or outbound tag. A country label alone is not authentication.

Pool lifecycle: unavailable -> discovered -> policy-approved -> connecting -> testing -> ready -> draining/failed. Only ready pools may issue routes. Tunnel loss rejects affected new sessions and blocks plaintext egress. Default sessions must remain unaffected. Changing an exit may break established connections; the UI must not promise TCP migration.

Thirty catalog targets do not imply thirty concurrent namespaces. Add active-pool limits, idle eviction, startup timeouts, connection limits and per-provider budgets before enabling on-demand creation. Never launch arbitrary commands directly from an app request.

## Remaining gates, in order

1. Resolve provider permission and logging disclosure for the intended shared service. Only VPN Gate metadata discovery is currently implemented; the other registry entries are not working adapters.
2. Add safe configuration retrieval/allowlist parsing, endpoint validation and secret-isolated temporary storage.
3. Implement isolated WireGuard/OpenVPN pool lifecycle, explicit DNS, IPv6 and UDP policies, firewall kill switch, cleanup and recovery.
4. Bounded live tunnel test with independent exit checks, forced-failure leak checks and default-route/control-plane survival checks.
5. Add scoped session routing and bounded authenticated control API; test two different country sessions concurrently with an unchanged default session.
6. Add publication generation checks, component-specific health/recovery and controlled connector transport comparisons.
7. Integrate the catalog/session API into the renamed Nyx VPN app; unavailable or stale countries are disabled, and logging limitations disclosed. Preserve the currently working APK until a replacement passes tests.
8. Measure phone-side Tehran performance and physical Android reconnection behavior; server measurements alone cannot prove these.

No production server edits, app rename/build, routing deployment, workflow execution, PR or connection-profile publication occurred in this increment. GitHub-hosted tests must stay bounded and project-related; the architecture is not permission for an indefinite public hosted-runner VPN.
