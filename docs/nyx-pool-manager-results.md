# Nyx reusable pool manager: executed results and remaining work

## Implemented

` scripts/egress_wireguard.py ` now supplies a reusable, root-only-in-practice
WireGuard resource lifecycle rather than constructing all networking directly in
a test. The class does not elevate privileges itself and does not run as a service.

- Requires an explicit provider-use approval and a trusted absolute wg binary path.
- Sanitizes configuration and requires supported IPv4 addresses and explicit IPv4 DNS.
- Checks the selected ingress subnet against host routes before allocation.
- Serializes pool allocations within the owning process. **One owning supervisor
  process is required**; multi-process allocation coordination is not implemented.
- Installs deny-by-default rules before creating traffic interfaces.
- Creates the encrypted UDP socket on the host route and moves the plaintext
  WireGuard interface into its own namespace.
- Creates a narrow host-to-pool ingress link without altering the host default route.
- Provides a private namespace-specific resolver file under `/etc/netns/<pool>`.
- Uses stdin for sensitive wg configuration and strips inherited application tokens
  from networking subprocess environments. Error messages omit command output/config.
- Returns `configured_unverified`, never `ready` or a claimed country.
- Rolls back in dependency order; cleanup failures remain explicit and retryable.
- Close can be called repeatedly after successful cleanup.

This is network resource management, not a complete production supervisor. It does
not launch Xray, authorize end users, verify an external country, monitor a tunnel,
publish subscriptions, or manage unexpected child processes. The future supervisor
must own workload processes and stop them before closing a pool. There is no
cross-process capacity manager or authenticated remote control endpoint yet.

## Executed validation

Full Python suite: **53 tests passed**.

Seven lifecycle tests cover:
- configure-versus-ready distinction and secret-free returned metadata;
- firewall-before-interface ordering and unchanged host default route;
- injected failure at every startup command, followed by rollback;
- route conflicts;
- unsafe/unsupported config and DNS rejection before network changes;
- permission/slot checks;
- explicit cleanup failure and retry.

The real privileged integration `tests/egress_pool_kernel.py` then:
1. Created a disposable control namespace with no Internet route and a local peer.
2. Used the reusable manager to establish an actual kernel WireGuard tunnel.
3. Passed real TCP, UDP and DNS fixture probes.
4. Verified the namespace-specific `/etc/resolv.conf` was bound by `ip netns exec`.
5. Passed `socket.gethostbyname('test.invalid')` through the tunnel to the local DNS
   fixture, receiving its deliberately synthetic `198.51.100.1` answer.
6. Verified a nonzero WireGuard handshake timestamp.
7. Closed twice, confirming removal of the pool's tunnel, host veth, namespace and
   resolver directory.
8. Confirmed the real host main route table remained unchanged.

The two-independent-pool encrypted firewall regression also passed again. All
fixture namespaces and resolver directories were removed. Fixture endpoint
addresses exist only in disposable networks; there was no public-provider traffic.

## Failure found and corrected

The first manager integration used nested `ip netns exec` for the disposable
control namespace. That unshared mount state, hiding newly created namespace
handles from the next invocation. The fixture was corrected to use `nsenter`
with only `--net`, and the test passed. This was a real integration defect in the
fixture, not a provider outage. Production use runs the manager in the owning host
namespace, not through the fixture wrapper.

## Stale-result protection

`Sessions.begin_probe()` now issues a one-use probe ticket; `mark_ready()` requires
that ticket. New probes supersede old probes. Failure invalidates pending tickets.
Removing and recreating a pool does not preserve its old tickets. Regression tests
confirm late successes cannot revive a failed/replaced pool, and late failures
cannot revoke a newer successful result. Tickets protect trusted supervisor result
ordering; they are not an app-authentication or external geolocation mechanism.

## Reproduce

```
python3 -m unittest discover -s tests -v
bash scripts/build-wireguard-tools.sh
sudo python3 tests/egress_pool_kernel.py .runtime/tool-src/wireguard-tools/src/wg
sudo python3 tests/egress_kernel.py --firewall legacy \
  --wireguard .runtime/tool-src/wireguard-tools/src/wg
```

The research workflow now includes the reusable-manager integration test, but the
updated workflow has not been executed. Local sanitized reports remain in the
ignored `.runtime/egress/` directory.

## Concrete blockers and unfinished work

The pinned Xray download was attempted with the repository's existing downloader.
Its GitHub release URL redirected to `release-assets.githubusercontent.com`, outside
this workspace's outbound allowlist, and curl failed with exit 35. No binary was
extracted and no Xray end-to-end result is claimed. No checksum or TLS check was
weakened to work around this restriction.

Provider sites remain outside the workspace network allowlist. Previously denied
workflow dispatch was not retried. Provider provisioning/permission remains unresolved
for several advertised options. Registry entries are not working adapters.

Still unfinished: public VPNBook/WARP/Psiphon/etc. provisioning, OpenVPN runtime
supervision, provider refresh scheduling, independent exit-country checks, Xray
session ingress integration, authenticated app API, production recovery/publication
rollout, and Nyx app integration/build. No production backend or app was changed;
no PR, commit, push, release or background deployment was started in this turn.
