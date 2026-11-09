# Nyx: real runner and German-provider results

For the later six-sample comparison and local Psiphon tests, see
`docs/nyx-comparison-and-psiphon.md`. This document records the earlier first-exit
milestone and its follow-up, not the latest provider stability evidence.

## Verified milestone

GitHub Actions run [42656691009](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42656691009), source commit `43aa572`, completed the following **real, bounded VPNBook OpenVPN experiment**:

- Acquired the advertised German UDP/53 configuration through the official website's server/protocol/download controls, without an account or challenge bypass.
- Detected the provider's published rotating credentials without logging or publishing their values.
- Sanitized the configuration, validated its CA and inline client certificate/key pair, and authenticated the OpenVPN connection.
- Kept the encrypted socket on the runner's normal host route while moving its TUN interface into a firewalled payload namespace.
- Completed a UDP DNS request through the tunnel.
- Completed HTTPS IP/geolocation probes through the tunnel, with certificate verification enabled.
- Obtained agreement on the exit IP and **two independent `DE` country results**.
- Stopped the tunnel and observed the post-stop request fail.
- Left the host IPv4/IPv6 main route tables unchanged and removed temporary resources.

The runner annotation was:

```
german_exit_observed; country_verified=true; UDP_DNS=true;
host_routes_unchanged=true; drop_blocked=true;
country_observations=DE,DE; IP_agreement=true
```

This establishes an observed German exit during that experiment, not the physical location of every packet, a latency guarantee, or an indefinitely available service. The test was terminated. No profile was published and no active country pool was added to the working shared backend.

## Follow-up result: not yet dependable enough to publish

Run [42657167660](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42657167660), source `319c17b`, tightened the drop check to repeat both the previously successful UDP query and a previously successful HTTPS endpoint after shutdown. Both blocking checks passed, and host routes again remained unchanged.

However, **country verification did not pass on that repeat**: the IP echo succeeded, but the geolocation services returned an HTTP error, a timeout and a DNS failure. There were not enough independent successful observations to claim Germany for that run. The code correctly kept `country_verified=false`; this was not evidence of a different country. The first successful observation remains valid historical evidence, not a reliability guarantee.

The latest run therefore validates fail-closed behavior and records provider/probe-path instability. No active service has been promoted from these results.

## What actually required debugging

1. **Workspace network restrictions:** replaced repeated local download attempts with a branch-push-triggered Actions workflow. The runner fetched and checksum-verified Xray successfully. Prior manual-dispatch permission failures did not prevent this approach.
2. **Dynamic provider download:** static ZIP-link parsing did not match the current website. Browser automation followed the normal Germany server, UDP/53 and `Download .ovpn File` controls. An overly escaped server selector and an ambiguous download heading were fixed and covered by browser-policy tests.
3. **Configuration compatibility:** the provider uses inline client certificates/keys and ordinary routing hints. The sanitizer now validates the certificate/key pair and discards routing hints. Scripts, plugins, includes, arbitrary file references, compression, TLS downgrade and weak authentication digests remain rejected.
4. **TUN migration:** a local raw-TUN test proved that a host-owned fd can read/write packets after the interface moves into a namespace. The owned OpenVPN process is briefly paused during the move/configure/resume transition. The subsequent public test passed UDP DNS.
5. **HTTPS diagnostics:** reduced payload MTU to 1280, forced IPv4 for this IPv4-only experiment and recorded each HTTPS probe independently. These changes were combined; no controlled test establishes MTU alone as the earlier failure's cause.
6. **Geolocation availability:** `ifconfig.co` returned an HTTP error. An independently fetched fallback from `ipinfo.io`, together with `ipwho.is`, provided two Germany results; `api.ipify.org` also agreed on the exit IP. A failed geolocation endpoint is not silently counted as success.

## Separate evidence categories

The workflow deliberately distinguishes:

- **Advertisements:** VPNBook pages advertise endpoints in Germany, France, the UK, Canada and the US. These are not all connection-tested.
- **Directory discovery:** VPN Gate's live directory was fetched repeatedly. Country/server counts changed between runs. A directory entry is not a successful connection.
- **Local kernel fixtures:** real local WireGuard and OpenVPN encryption, namespace/firewall behavior and cleanup. OpenVPN fixture country metadata is explicitly simulated; it is not a public Germany test.
- **Xray integration:** real local SOCKS -> VLESS/WebSocket -> namespace Xray -> WireGuard traffic, including TCP, UDP, rejected wrong identity, tunnel-down blocking and new-request recovery.
- **Public-provider experiment:** the terminated VPNBook Germany test above.
- **Published service:** still none of the new country pools. Catalog entries remain non-selectable.

## Tests and workflow

Local Python suite at the verified milestone: **73 tests passed**. Browser policy suite: **3 tests passed**. The Actions workflow also passed real OpenVPN and WireGuard kernel fixtures, nftables and legacy firewall tests, the Xray baseline and combined Xray/WireGuard path.

Workflow: `.github/workflows/egress-research.yml`.

It runs on relevant pushes to `arena/f056ce38-my-small-project`, has explicit job timeouts, and does not self-chain, restart the production VPN loop or publish subscription profiles. Public-provider testing waits for the local kernel job to pass. A green workflow means its probes executed successfully; each provider observation still has its own status.

Main new paths:

- `scripts/egress_vpnbook_browser.mjs`: bounded official-page acquisition and optional private probe invocation.
- `scripts/egress_openvpn.py`: conservative configuration reconstruction.
- `scripts/egress_openvpn_probe.py`: isolated, deadline-limited provider connection and exit checks.
- `tests/egress_tun_migration.py`: raw-TUN fd migration proof without Internet access.
- `tests/egress_openvpn_kernel.py`: isolated local OpenVPN fixture with real encryption and UDP DNS.
- `scripts/egress_xray.py`, `tests/egress_xray_fixture.py`: internal per-pool VLESS configuration and combined routing fixture.

## Diagnostic privacy correction

An earlier directive-name extractor could tokenize fragments inside inline blocks. It was replaced with a closed-vocabulary extractor that skips certificate/key block bodies. A regression test verifies that neither inline content nor arbitrary unknown tokens enters metadata. The obsolete browser report artifact `13689783299` was deleted by the narrowly scoped cleanup job in run [42653147338](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42653147338); that one-off elevated-permission job was then removed. No downloaded configuration or complete private key was intentionally published.

## Remaining gates

- Repeatability/health history and bounded provider selection, rather than one successful sample.
- Provider permission for the intended public/shared use. VPNBook's personal-use wording is not changed by a successful technical test.
- Production process supervision, authenticated per-user session API, session revocation, public ingress routing and generation-safe publication.
- Other provider integrations: VPNBook WireGuard, WARP, Psiphon, Proton, Riseup and Tor are not working public country adapters merely because their source pages were fetched.
- Thirty available countries have not been established.
- Tehran/physical-phone latency and stability measurements have not been performed.
- The Nyx app rename/country picker and a new APK remain unfinished; the working app and shared connection were not replaced.

There is no unattended deployment or public tunnel left running after the research jobs finish.
