# My-small-project — VPN Loop (v2rayNG, latency-aware)

A self-restarting Xray **VLESS + WebSocket + TLS** proxy for **v2rayNG**, built
on GitHub Actions + Cloudflare tunnels.

## Goal

**Under 200 ms latency from Tehran, Iran**, if the network route and
available infrastructure make that feasible. This target is **not promised** —
it must be measured from a client actually in Tehran (see
"Latency testing from Tehran" below). I have **not** run a Tehran-side test;
estimates in this README are labeled as estimates.

## The problem with the old design

The old design ran Xray on a **GitHub-hosted runner in a US Azure region**.
GitHub-hosted runners cannot be placed in another region, so every packet from
Tehran crossed the Atlantic twice:

```
v2rayNG (Tehran) -> Cloudflare edge -> US GitHub runner -> internet
```

Tehran -> US RTT alone is typically **150-250+ ms**, so the observed
350+ ms ping was unsurprising. No protocol tweak inside the runner can fix a
transatlantic round trip.

## Chosen design: Xray on a VPS near Tehran

Move the proxy egress to a **low-cost VPS in Istanbul or Frankfurt** — the
nearest practical regions to Tehran with widely available hosting:

```
v2rayNG (Tehran) ---TLS/WS---> Xray on VPS (Istanbul/Frankfurt) ---> internet
                                  ^ SSH deploy from GitHub Actions (control plane only)
```

GitHub Actions now only runs the control plane: every ~5h25m it generates a
fresh Xray config (new UUID + WebSocket path + self-signed TLS cert), pushes it
to the VPS over SSH using secrets that **never touch this repo**, and restarts
the Xray systemd service. The data plane no longer touches the US runner.

Estimated RTT (to be verified from Tehran — these are **not** Tehran
measurements):

| Leg | Estimate |
|---|---|
| Tehran -> Istanbul | ~20-60 ms |
| Tehran -> Frankfurt | ~60-100 ms |
| Xray + TLS handshake | ~1-5 ms |
| Tehran -> US East (old path) | ~150-250+ ms |

With Istanbul/Frankfurt egress, **<200 ms total is plausibly achievable**;
with the US runner it is not. Whether your specific Iranian ISP route can
actually deliver it must be measured (see test plan below).

## Options considered

| Option | Viable for <200 ms from Tehran? | Cost | Notes |
|---|---|---|---|
| **Xray on VPS (Istanbul/Frankfurt)** — **chosen** | Plausible, must verify | ~$3-6/mo (Oracle Free Tier Frankfurt: free) | Direct IP, no Cloudflare hop. Chosen design. |
| Existing Cloudflare quick tunnel on US runner | No | Free | Tehran -> US RTT alone exceeds the budget. Kept as fallback (see below). |
| Cloudflare Worker | No | Free/paid | Workers cannot terminate arbitrary VLESS/WebSocket/TLS egress streams, Worker routing from Iran is uncertain, and this use case strains the Workers ToS. Not pursued. |
| Cloudflare Tunnel from the VPS | Possible, higher latency | Free tier | Adds an extra Cloudflare hop; keep as a fallback if the VPS IP is blocked/throttled. See "Rollback / fallbacks". |

## Prerequisites

1. A Linux VPS (Ubuntu/Debian) in **Istanbul** or **Frankfurt**, e.g.
   Hetzner (Falkenstein/Nuremberg near Frankfurt), DigitalOcean (Frankfurt), or
   Oracle Cloud Free Tier (Frankfurt — always-free AMD instance, credit card
   required for identity verification). 1 vCPU / 1-2 GB RAM is enough.
2. Firewall open on the VPS: **TCP 22** (SSH) and **TCP 443** (Xray).
   Example (ufw): `ufw allow 22/tcp && ufw allow 443/tcp && ufw enable`.
3. An SSH key pair. Add the **private key** to GitHub Actions secrets (below);
   the private key never goes into the repo.

## One-time setup

1. Create the VPS and note its public IP (`VPS_HOST`).
2. In GitHub: **Settings → Secrets and variables → Actions → New repository
   secret**, add:
   - `VPS_SSH_KEY` — the VPS SSH private key (root login recommended, since
     Xray binds port 443).
   - `VPS_HOST` — the VPS public IP or hostname.
   - `VPS_USER` — SSH user (default `root` if omitted).
3. On this repo's **Actions → VPN Loop** tab, enable the workflow and run it
   manually ("Run workflow"). The first run installs Xray on the VPS, writes
   `/etc/xray-vpn/{config.json,cert.pem,key.pem}` plus a systemd service unit,
   and starts the `xray-vpn` systemd service.
4. The run summary shows the `vless://` URI — import it into v2rayNG
   (clipboard) or use the subscription URL (Option B).

No private keys or secrets are stored in this repository.

## Quick start (v2rayNG)

1. Run the **VPN Loop** workflow (Actions tab → VPN Loop → Run workflow).
   Afterwards it feeds itself: every run queues the next one, and runs hand
   over every ~5h25m.
2. Open the running workflow → summary shows the config:
   - **Option A — clipboard:** copy the `vless://…` line → v2rayNG → `+` →
     *Import from clipboard* → select profile → connect.
   - **Option B — subscription (recommended):** v2rayNG → `+` →
     *Subscription setting* → paste
     `https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt`
     → *Update*. The URL rotates every ~5.5h; the subscription is rewritten
     each cycle, so a manual refresh keeps you connected.
   - **TLS note:** the VPS uses a self-signed certificate. In v2rayNG enable
     **Allow Insecure** for the profile (or tap the profile's TLS settings).
3. Stop any time: Actions → VPN Loop → `…` → Disable workflow.

### Kick / restart now (new URL, new UUID)

```bash
gh api -X POST repos/asomethinggood-sys/My-small-project/dispatches -f event_type=vpn-loop
```

## Latency testing from Tehran (required before claiming <200 ms)

The target is **proxy RTT under 200 ms measured from Tehran**. Proxy RTT is
not website/download speed: a fast download can still have high RTT, and vice
versa. Test both.

**Prerequisite:** v2rayNG connected via the published config, device physically
in Tehran. Test on both mobile data and WiFi (ISPs route differently).

### 1. Baseline (no proxy) — what the network can possibly deliver

From a Terminal in Tehran (or any ping tool on the device):

```bash
ping -c 10 <VPS_HOST>
```

This is the absolute floor: proxy RTT cannot be below this. If it is already
near or above 200 ms, the target is not reachable on this route regardless of
the proxy.

### 2. Proxy RTT

In v2rayNG: connect the imported profile, then use the built-in latency test
(long-press profile → Latency test / ping icon) against a target such as
`1.1.1.1` or `www.google.com`, and also note the RTT reported to the VPS
endpoint itself if available. Repeat 5-10 times over a few minutes.

### 3. Download speed through the proxy

Run a speed test (e.g. fast.com or Speedtest) with v2rayNG connected, to
distinguish RTT from throughput.

### 4. Pass/fail

| Metric | Target | Result (fill in after testing) |
|---|---|---|
| Direct ping Tehran → VPS IP (baseline) | well under 200 ms | _ms_ |
| v2rayNG proxy latency test | **< 200 ms** | _ms_ |
| Download via proxy | usable | _Mbps_ |

**Claim the goal only if the proxy RTT test from Tehran is under 200 ms.**
Report the numbers; estimates are not results.

## Measured results

**Not yet measured from Tehran.** This branch was written from a sandbox that
is not in Tehran; its RTTs are not representative and are intentionally not
reported here as baseline.

Once you run the test plan above, fill in the table and update this section.
If the target is not met, see "Rollback / fallbacks" below.

## Costs and tradeoffs

- **VPS:** ~$3-6/month (or free via Oracle Cloud Free Tier Frankfurt). The
  old trycloudflare path remains available at zero cost as a fallback but
  cannot plausibly meet <200 ms from Tehran.
- **Stability:** Xray runs as a systemd service on the VPS; the workflow only
  briefly restarts it every ~5h25m to rotate UUID/path. Between runs the old
  config keeps serving.
- **Security:** public repo, shared config (anyone who finds the repo can use
  the tunnel), self-signed certificate with Allow Insecure. Not a
  security-hardened VPN — matches the project's stated threat model.
- **Blocking risk:** a bare VPS IP may be throttled or blocked by Iranian ISPs
  where TLS to Cloudflare-fronted addresses is not. If that happens, see
  fallbacks below.

## Files

| File | Purpose |
|---|---|
| `.github/workflows/vpn.yml` | Self-chaining loop: VPS deploy (default) or Cloudflare free fallback |
| `README.md` | This document |

The plain-text `vless://` URI of the current tunnel is force-pushed to the
[`live-config` branch](https://github.com/asomethinggood-sys/My-small-project/blob/live-config/config.txt)
every cycle:
`https://raw.githubusercontent.com/asomethinggood-sys/My-small-project/live-config/config.txt`

## Rollback / fallbacks

- **Immediate rollback:** disable the workflow (Actions → VPN Loop → Disable).
  The VPS keeps running the last-deployed config until you destroy the VPS.
- **Back to the free path:** remove the `VPS_*` secrets from GitHub Actions
  settings. The workflow automatically falls back to the original Cloudflare
  quick tunnel on a US GitHub runner (zero cost, but expected >350 ms from
  Tehran — the <200 ms goal will not be met).
- **If the VPS IP is blocked:** keep the VPS but put Cloudflare in front
  (Cloudflare Tunnel or a Cloudflare domain + origin cert on the VPS), or move
  the VPS to a different city/provider. Update `VPS_HOST` secret and re-run.

## Responsibility

You are responsible for complying with GitHub's and Cloudflare's terms of
service, your VPS provider's terms, and the law where you live.
