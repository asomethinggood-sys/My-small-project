# Nyx: executed local kernel results

## Scope

This run advanced from catalog/control-model unit tests to actual Linux namespace,
firewall and encrypted WireGuard integration tests. It did **not** connect to any
public VPN provider, measure Tehran latency, deploy the server, or build an app.

## Executed results

- Full Python suite: **43 tests passed**.
- Pinned upstream WireGuard tools built successfully from commit
  `a998407747005ea7e4e0258d96f105c97241e1d3`, reported version `v1.0.20260223`.
- Two simultaneous local kernel WireGuard tunnels established handshakes.
- Real TCP and UDP socket probes succeeded through each tunnel.
- DNS query/response fixtures succeeded through each tunnel; direct underlay DNS
  probes were blocked. These are explicit resolver probes, not proof that a future
  Xray/system-resolver integration uses the correct DNS configuration.
- The permitted ingress listener and replies worked; a second unapproved listener
  was blocked.
- Direct underlay TCP was blocked.
- IPv6 positive control succeeded with a narrowly scoped temporary allow rule;
  after removal, IPv6 connection attempts were blocked. The fixture's WireGuard
  peers permitted IPv6, so the block was not merely absent cryptokey routing.
- Removing one tunnel interface blocked its TCP, UDP and DNS attempts, including
  direct-underlay attempts despite a deliberately configured fallback route.
- The second pool continued to pass TCP/UDP probes, and ingress remained reachable.
- Host main routes were identical before/after; all temporary namespaces and
  fixture processes were removed.
- Three consecutive encrypted runs passed before the IPv6 positive-control
  enhancement; the enhanced encrypted run and enhanced veth run also passed.

## Failure found and debugged

The sandbox has sufficient sudo privileges and kernel WireGuard support, but the
nftables inet table creation failed with `Operation not supported`. The test failed
and cleaned its namespaces. An explicit legacy-iptables implementation of the
same restricted policy was added and tested. No silent firewall-free fallback
exists. **nftables remains unverified here**, not passed by assumption.

The research workflow includes both nftables and legacy tests for a capable
GitHub runner. That updated workflow has not been executed in this turn.

## New implementation files

- `scripts/egress_firewall.py`: namespace-only IPv4 payload rules with scoped
  ingress replies, denied private/metadata ranges and blocked non-loopback IPv6.
  Both nftables and legacy-iptables rule generation are available.
- `scripts/egress_openvpn.py`: conservative allowlist parser with inline CA
  validation; rejects script/plugin/include/file paths, TLS downgrades, unknown
  directives and unsafe endpoint forms. Produces sensitive configuration data,
  never executes it. Its strict profile can reject otherwise valid provider
  configurations; compatibility has not been established.
- `scripts/build-wireguard-tools.sh`: reproducible pinned upstream tooling build;
  does not install wg-quick or modify network settings.
- `tests/egress_kernel.py`: self-cleaning privileged local integration fixture,
  supporting veth stand-ins or real WireGuard peers.
- `tests/test_egress_openvpn.py`: parser/firewall regression tests.
- Session controller now rejects truthy strings in permission/evidence fields and
  non-boolean UDP requirement values.

## Reproduce

```
python3 -m unittest discover -s tests -v
bash scripts/build-wireguard-tools.sh
sudo python3 tests/egress_kernel.py --firewall legacy \
  --wireguard .runtime/tool-src/wireguard-tools/src/wg
```

On a kernel supporting nftables, replace `legacy` with `nft`. The script must run
as root, changes only its disposable namespaces, and never contacts providers.
The local generated reports are under `.runtime/egress/`, ignored by Git. Keys are
generated in memory for the fixture and are not written to reports or profiles.

## Important limits

This is a tested isolation building block, **not a production pool supervisor**.
There is no authenticated app-facing session API, production Xray country routing,
OpenVPN tunnel process supervisor, provider credential acquisition, periodic
provider refresh, production publication/recovery rollout or Nyx APK yet. The
fixture does not prove large-transfer performance, TLS reachability, global country
availability, privacy against a hostile co-tenant, survival of existing TCP sessions,
or endpoint/DNS rebinding behavior.

The firewall design assumes WireGuard's outer socket is in a separate namespace.
It cannot simply be reused for OpenVPN running its own outer socket inside the
payload namespace. The OpenVPN supervisor needs a separately tested, narrow
underlay endpoint allowance.

Public-provider blockers remain real: this workspace's outbound allowlist excludes
the provider sites; GitHub workflow dispatch previously failed with insufficient
integration permissions and was not retried; several providers require credentials,
verification or sharing permission. No verification challenge or usage restriction
was bypassed. WARP has no established arbitrary-country selector, and Psiphon
provisioning/country/UDP behavior is still unverified in this project.

The existing working connection and app were left unchanged. No PR, commit, push,
production workflow dispatch or APK release was performed in this run. There is no
continuing background test or deployment after this response.
