# Nyx VPN 0.5 preview

## What this build is

A standalone `app.nyx.vpn` Android application built from the working Continuum Android integration. It installs alongside Continuum and does not migrate or overwrite its private settings. Android still permits only one active VPN at a time. The default project subscription URL remains unchanged.

The interface uses a deep blue-black surface, pale mineral-green accent, a custom crescent drawing, restrained typography, a finite connection transition and a rotating arc only while connecting. Animations stop off-screen and respect the system animator-disable setting. No image-generation assets or large animation frameworks are bundled.

The Rust library now also owns catalog freshness/eligibility policy, resource-aware connection presentation and bounded motion interpolation, alongside existing scheduling, cancellation generations, backoff and diagnostics policy. Android views, networking adapters and profile parsing remain Java; the Xray engine remains Go. **This is not an all-Rust VPN engine.**

## Locations and live discovery

The new Locations screen supports searching all 30 target countries and inspecting provider/protocol breakdowns. A manual refresh retrieves the latest sanitized runner metadata from the separate `nyx-research-catalog` release. It never fetches connection credentials or changes the current connection.

- Distinguishes discovered servers, advertising endpoints, provider counts and actual availability.
- VPN Gate, VPNBook OpenVPN/WireGuard, Cloudflare WARP, Psiphon, Proton, Riseup and Tor remain distinct adapters.
- UDP is displayed as a capability, never a provider. Public service UDP remains unverified except explicitly unsupported Tor.
- Catalogs have at most 15 minutes of validity. Future timestamps and expired snapshots are not current availability.
- Unknown providers/protocols, oversized responses, invalid counts and duplicate countries are rejected.
- HTTPS redirects are limited to GitHub's download hosts; plaintext, credentials in URLs and arbitrary hosts are rejected.
- Background requests are cancelled when leaving the screen; generation checks prevent stale callbacks from updating a later view.
- Remote `selectable` and `verified_servers` fields cannot authorize a connection. The screen deliberately has no country-connect action yet.

**There are currently zero selectable country exits.** The default subscription and supported manual profiles still function. A discovered server is not an available shared-service exit, and the DE220 two-sample result is historical research evidence rather than a running pool.

Metadata publication runs with bounded discovery tests, not a continuously running hosted VPN or a promised real-time monitoring service. Refreshing in the app downloads the latest snapshot; it does not launch a GitHub workflow. Stale data stays visibly stale.

## Backend increment

`scripts/egress_control.py` adds a bounded authenticated control component over the existing pool/session model:

- distinct provisioned credentials and per-user ownership;
- per-user session quota and request budget;
- generation-bound leases;
- no default fallback for unavailable countries;
- transport revocation on expiry and pool failure;
- rollback after partial installation;
- fail-closed latch after transport revocation failure;
- disconnect bypasses rate limiting;
- shutdown closes the data plane before deleting bookkeeping.

Eleven new unit tests cover these behaviors. This component is **not** a deployed HTTP API or a production supervisor. Its data-plane adapter must genuinely terminate existing flows; the unit tests use a test adapter. The owning supervisor must call the expiry sweep periodically, and a deployed transport must independently enforce deadlines. The existing kernel fixtures exercise isolated networking but do not prove this component's end-to-end production integration.

## Gates not waived by building an APK

- No public shared-use provider pool has been approved or provisioned.
- VPNBook's personal-use restriction is still unresolved for shared deployment.
- VPNBook WireGuard provisioning/expiry, public Psiphon country/UDP, and WARP arbitrary-country routing remain unresolved.
- An authenticated public session API, production transport revocation/health supervisor, and application country-connect flow remain unfinished.
- 30 targets are not 30 working countries.
- Hosted CI runners are used for bounded development tests, not indefinite public VPN hosting.
- Physical ARM, Tehran latency, mobile handoff, battery and long-duration testing remain outstanding.

The release is intentionally labeled **preview**. It must not be described as completion of the original multi-provider country-routing project.
