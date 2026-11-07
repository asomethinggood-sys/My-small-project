# My-small-project — VPN Loop (v2rayNG, free Cloudflare tunnel)

A free, always-on VPN/proxy for **v2rayNG** built out of GitHub Actions +
Cloudflare tunnels. No server to rent, no ports to open, unlimited minutes
(public repo) — and the workflow restarts itself before the 6-hour job cap.

## Latency honesty (read first)

This runs Xray on a **GitHub-hosted runner in a US Azure region**:

```
v2rayNG (Tehran) ──TLS/WS──► Cloudflare edge (trycloudflare.com)
                                   │ cloudflared quick tunnel (outbound only)
                                   ▼
                          GitHub Actions runner (US)
                          └── xray-core : VLESS + WebSocket, port 18888
```

GitHub-hosted runners cannot be placed outside the US, so Tehran → US RTT
alone is typically **150–250+ ms**. A **sub-200 ms proxy RTT from Tehran is
not plausible on this path**, no matter how the config is tuned. I have **not**
run a Tehran-side test, and I am not promising the target.

This is the free zero-cost option. If you need <200 ms, you would need egress
closer to Tehran (e.g. a low-cost VPS in Istanbul or Frankfurt) — that is not
what this repo deploys.

## How it works

1. Run starts → **first step queues the next run** (it sits *pending* thanks
   to the `vpn-loop` concurrency group).
2. Xray (VLESS + WebSocket) + a Cloudflare quick tunnel spin up. The run
   prints a ready-to-paste `vless://` URI.
3. After **5h25m** the run exits → the pending run starts immediately and
   hands over. Repeat forever.
4. A `cron` safety net (every 5h) revives the loop if a dispatch ever fails.

## Quick start (v2rayNG)

1. **Actions** tab → *VPN Loop* → **Run workflow** (first time; afterwards it
   feeds itself).
2. Open the running workflow → the summary shows the config. Pick one:
   - **Option A — clipboard:** copy the `vless://…` line → v2rayNG →
     `+` → *Import from clipboard* → select the profile → connect.
   - **Option B — subscription (recommended):** v2rayNG → `+` →
     *Subscription setting* → paste
     `https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt`
     → *Update*. The tunnel URL rotates every ~5.5h; the subscription is
     rewritten each cycle, so a manual refresh keeps you connected forever.
3. Stop it any time: **Actions** → *VPN Loop* → `…` → *Disable workflow*.

### Kick / restart now

To cancel whatever is running and start a fresh tunnel immediately (new URL):

```bash
gh api -X POST repos/asomethinggood-sys/My-small-project/dispatches -f event_type=vpn-loop
```

## Repo requirements

- **Public repo** (that's what makes Actions minutes unlimited).
- Actions enabled (repo → *Actions* → enable if prompted).

## Files

| File | Purpose |
|---|---|
| `.github/workflows/vpn.yml` | The self-chaining tunnel loop |

The plain-text `vless://` URI of the **current** tunnel is also force-pushed to
the [`live-config` branch](https://github.com/asomethinggood-sys/My-small-project/blob/live-config/config.txt)
every cycle (single commit, always current):
`https://raw.githubusercontent.com/asomethinggood-sys/My-small-project/live-config/config.txt`

## Notes

- The hostname is a random `*.trycloudflare.com` quick-tunnel URL and it
  **changes every cycle** (~5h25m). That's why Option B exists. If you want a
  permanently stable URL, run `cloudflared tunnel` as a *named* tunnel with
  your own Cloudflare domain and set the `host`/`sni` in the URI accordingly.
- Exit IP is GitHub's runner IP. Traffic is plain internet from there.
- The config/UUID is published to this public repo's release page — anyone who
  finds the repo can use the tunnel. That's the trade-off of this setup.
- You are responsible for complying with GitHub's and Cloudflare's terms of
  service and with the law where you live.
