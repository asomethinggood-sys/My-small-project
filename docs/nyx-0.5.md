# Nyx VPN 0.5 preview

## Download and verification

[**Full Nyx 0.5 ARM64 APK**](https://github.com/asomethinggood-sys/My-small-project/releases/download/nyx-0.5.0-preview-21/nyx-0.5.0-arm64.apk)

- Android 8+ ARM64; package `app.nyx.vpn`.
- **19,233,987 bytes** (19.23 MB / 18.34 MiB).
- SHA-256: `01b94c200b371e6763dd3b9a3100f6770708f6b71dccc4b7304678eae5954895`.
- Source: `b57b1fa3bbca540e96194a9cc25fd9632144590e`.
- [Successful Android run 42666469586](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42666469586): **20 Rust, 47 JVM and 7 Android instrumentation tests**, debug/release lint, ARM64 build, and **40 real TUN network checks** across four protocol fixtures.
- Backend: **99 Python tests and 4 browser-policy tests**, plus real local encrypted fixtures; see runner 42665056596.
- **Disposable preview signing certificate.** Stable signing secrets are not configured. A future preview may require uninstalling this preview; Continuum remains a separate app. No credentials need to be provided in chat.

[Home screenshot](https://github.com/asomethinggood-sys/My-small-project/releases/download/nyx-0.5.0-preview-21/nyx-home.png) · [Locations screenshot](https://github.com/asomethinggood-sys/My-small-project/releases/download/nyx-0.5.0-preview-21/nyx-locations.png)

Visual review caught an unrelated Pixel Launcher ANR obscuring the initial emulator captures. Those two screenshots were removed from build 20. Build 21 stops only that emulator launcher and requires Nyx window focus before capture; its clean screenshots were reviewed. Application errors are not globally hidden or suppressed.

The release includes corresponding source, native/runtime licenses, signing information and exact validation totals. These tests do not establish physical ARM, Tehran latency or long-duration availability.

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

Eleven new controller unit tests cover these behaviors. `scripts/egress_ingress.py` now provides a concrete private TCP transport adapter: loopback-only per-lease listeners, operator-provisioned namespace destinations, bounded connection counts and buffers, EOF/half-close forwarding, independent lease deadlines, and immediate closure of existing sockets on revocation. Six real-socket tests pass, including a 150 KB payload, half-close, expiry without a controller sweep, and isolation from another user's pool.

The kernel fixture additionally exercises this controller/transport in front of Xray/WireGuard with TCP and framed UDP probes followed by revocation. It **passed** in [runner 42665056596](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42665056596), commit `279c246`. Its geography is explicitly synthetic, not public German exit evidence. The Python suite now contains **99 passing tests**, including the real-socket tests.

This is still **not** a deployed HTTP API or a complete production supervisor. A trusted authenticated TLS frontend must own the private loopback endpoints; the app must not be given those endpoints directly. The owning supervisor must reconcile pool health and call the session expiry sweep periodically even though the transport independently closes expired flows. The transport deadline is checked at 100 ms polling intervals; it is not a hard real-time guarantee. No component changes the shared default route.

## Gates not waived by building an APK

- No public shared-use provider pool has been approved or provisioned.
- VPNBook's personal-use restriction is still unresolved for shared deployment.
- VPNBook WireGuard provisioning/expiry, public Psiphon country/UDP, and WARP arbitrary-country routing remain unresolved.
- An authenticated public session API, production transport revocation/health supervisor, and application country-connect flow remain unfinished.
- 30 targets are not 30 working countries.
- Hosted CI runners are used for bounded development tests, not indefinite public VPN hosting.
- Physical ARM, Tehran latency, mobile handoff, battery and long-duration testing remain outstanding.

The release is intentionally labeled **preview**. It must not be described as completion of the original multi-provider country-routing project.
