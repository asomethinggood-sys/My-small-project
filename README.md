# VLESS for v2rayNG: route-first latency improvement

**Goal, not a result:** below 200 ms from Tehran when routing permits it.
The existing US GitHub runner reportedly exceeds 350 ms. That is a user report,
not a measurement made by this project. **No Tehran-side measurements or live VPS
deployment have been performed for this change. Temporary runner-side experiments are documented below; no permanent endpoint is supplied.**

## Stable Worker address (setup pending)

The proposed relay for **bih.asomethinggood.workers.dev** is prepared in
[`worker/worker.mjs`](worker/worker.mjs). Follow the
[three setup steps](docs/worker-relay.md) to deploy the code, bind KV and save a
shared update secret. It is **not yet live-tested or enabled**, and no working
stable config is claimed. The existing connection remains unchanged.

## No VPS budget? Start here

Use the [bounded no-cost QUIC vs HTTP/2 experiment](docs/free-experiment.md).
It compares the existing connector paths without changing regions or buying a
server, and provides verified, temporary v2rayNG profiles. No Tehran improvement
is claimed. The VPS option below remains an optional architecture, not a setup
requirement for the experiment.

## Recommendation

Trial a small **direct VPS in Istanbul and/or Frankfurt**, then keep the provider
with the best measured route from your actual Tehran ISP. Budget approximately
**US$5–10/month plus domain registration** (planning estimate, not a provider quote;
IPv4, tax, transfer allowances and availability vary). A 1 vCPU / 1 GB Linux
x86_64 VPS is a reasonable starting point for a few users, not a capacity promise.
Check that the provider permits proxy use and can legally serve your account;
Iran-related signup/payment/service restrictions may apply. Ask for a test IP or
short refundable/hourly trial. Nearby geography alone does not ensure good peering.

```
v2rayNG -> TLS/WS :443 -> Caddy on selected VPS -> Xray on 127.0.0.1:18888 -> destination
```

This removes the Cloudflare-to-US-runner leg while retaining the existing VLESS +
WebSocket + TLS client protocol. Caddy obtains/renews public certificates. A
stable hostname and systemd restarts replace Actions rotation. No six-hour limit
applies to a VPS. Certificate renewal normally does not require client changes.
Direct IPs may be blocked or throttled; test availability before committing money.

See [architecture and limitations](docs/architecture.md) and the
[Tehran measurement protocol](docs/latency-testing.md). If no tested nearby route
meets the target, changing a UUID, WebSocket path, DNS, or MTU will not fix distance
or international routing. A paid VPS is the most practical recommendation here,
not proof that paying is sufficient or mathematically necessary.

## Deploy on a dedicated VPS

These scripts target **Debian 12+/Ubuntu 22.04+, systemd, Linux x86_64**. They do
not provision or purchase a server and do not send SSH credentials to Actions.
Use a dedicated host: scripts install `arena-xray` / `arena-caddy` units and use
ports 80, 443, 18888, and (during verification) 10809. Do not run on a host with
conflicting services without reviewing the scripts.

1. Choose a provider after the Tehran-side route trial. Create a DNS **A** record
   for your hostname pointing directly to the VPS IPv4. Use **DNS-only**, not the
   Cloudflare orange-cloud proxy. Remove stale AAAA records; only add IPv6 after
   verifying the server and client route. You need control of a real domain.
2. Allow inbound **TCP 80 and 443** in provider and host firewalls. Keep SSH open
   to your admin address; do not lock yourself out. Do not expose 18888 or 10809.
   Allow outbound DNS, HTTPS (ACME/downloads), and intended proxy destinations.
3. SSH into the VPS. Install prerequisites:
   ```bash
   sudo apt-get update
   sudo apt-get install -y ca-certificates curl unzip python3 git
   git clone --branch arena/f056ce38-my-small-project https://github.com/asomethinggood-sys/My-small-project.git
   cd My-small-project
   ```
   The branch must first be pushed by its owner; until then copy this working
   tree's `scripts/` directory to the VPS over SSH instead. After merge you can
   use the merged default branch. No remote deployment is initiated by this PR.
4. Replace `vpn.your-domain.tld` below with the real DNS hostname:
   ```bash
   sudo bash scripts/deploy-vps.sh vpn.your-domain.tld
   sudo journalctl -u arena-caddy -u arena-xray -n 100 --no-pager
   ```
   Wait for certificate issuance; DNS propagation can take time. Binary downloads
   are pinned to Xray v26.10.31 and Caddy v2.11.9 with checked SHA-256 hashes.
   Review upstream releases/security fixes before upgrading. The installer keeps
   the UUID/path on reruns; it does not silently rotate clients.
5. Run the functional verification (requires the local SOCKS port 10809 to be free):
   ```bash
   sudo bash scripts/verify.sh /etc/arena-vpn /usr/local/lib/arena-vpn/xray
   ```
   This checks public TLS, then HTTPS through SOCKS -> VLESS/WS -> VPS egress.
   Only on success are `verified-uri.txt` and `verified-subscription.txt` written.
   The test runs **on the VPS**, proves functionality only, and says nothing about
   Tehran availability or RTT. If it fails, inspect `/etc/arena-vpn/client-test.log`
   and the service journal; fix DNS/firewall/certificate/egress before continuing.
6. Retrieve the verified URI over your existing SSH connection:
   ```bash
   ssh ADMIN@VPS 'sudo cat /etc/arena-vpn/verified-uri.txt'
   ```
   In v2rayNG: **+ -> Import from clipboard**, select `Direct-VPS`, connect.
   Leave TLS certificate verification enabled. There is no fabricated URI in this
   README. For a shared subscription, deliberately publish **only**
   `verified-subscription.txt` on HTTPS hosting you control, then add that URL in
   v2rayNG's subscription settings. The existing `vpn-config` release still
   belongs to the legacy tunnel; it does **not** become a VPS subscription.
7. From Tehran run the [test plan](docs/latency-testing.md). Only those results can
   establish whether this setup meets the target.

### State, safety and maintenance

- Server config, UUID and generated client files: `/etc/arena-vpn/` (root-owned).
- Certificate private keys and ACME state: `/var/lib/arena-vpn/`. Never publish or
  copy these into Git. `.runtime/`, measurements, PEM/key files are ignored.
- This remains a potentially **public/shared proxy**, not a hardened private VPN.
  Anyone given the URI can consume bandwidth and cause abuse complaints against
  your VPS. The new installer does not automatically publish it. Set provider
  billing alerts/transfer limits and monitor usage. Public sharing can degrade RTT.
- Logs can contain destination/connection metadata; review retention and access.
  Caddy terminates outer TLS; destination HTTPS remains separate end-to-end TLS.
- `sudo systemctl status arena-xray arena-caddy`; restart with
  `sudo systemctl restart arena-xray arena-caddy`. Reboot survival is enabled.
- Before upgrading, securely back up `/etc/arena-vpn`, `/var/lib/arena-vpn`,
  `/usr/local/lib/arena-vpn`, and `/etc/systemd/system/arena-*.service` outside Git.
  Rerun installer and verifier after changes. Existing sessions can drop on restart.
- To rotate a leaked shared identity: stop services, securely archive
  `/etc/arena-vpn` outside the repository, remove that directory, rerun installation
  and verification, distribute the new URI. Old clients cease working.

## Existing Actions + Quick Tunnel (legacy, disabled by default)

The original US-runner design is retained for controlled experiments/rollback,
**not recommended as ongoing public proxy hosting or as a <200 ms solution**.
GitHub terms restrict Actions usage; see [architecture](docs/architecture.md).
Do not enable it for uses outside those terms.

The job only runs if repository variable `ENABLE_FREE_TUNNEL` is `true`.
If a permitted test requires it, manually dispatch `vpn.yml`. The successor uses
the **same ref**, with ref-scoped concurrency. The default-branch cron remains
`21 */5 * * *` (not a precise five-hour timer at midnight). The job queues its
successor first, serves at most 5h25m, checks processes every 30s, and has a 355m
job timeout. Queue, installation and certificate propagation delays still cause
gaps. It is **not seamless continuity**: hostname and UUID rotate, active sessions
break, and clients must refresh the subscription. Dispatch may fail and scheduled
runs can be delayed. Disabling the workflow and cancelling running/pending runs
is necessary to stop an existing chain; a variable change alone does not stop it.

Only default-branch runs publish the public URI in the run summary and overwrite:
`https://github.com/asomethinggood-sys/My-small-project/releases/download/vpn-config/config.txt`
Refresh the subscription after rotation; automatic refresh depends on v2rayNG
settings. The old `live-config` branch mirror is no longer updated (no branch
force-pushes). Previously published assets/mirrors can be stale. Branch test runs
do not overwrite the shared subscription. This change has not cancelled any
existing main-branch runs or changed remote repository settings.

## Triggering the loop after review and merge

There are **two different tokens** involved. The agent's GitHub App token may
lack permission to call `workflow_dispatch`. The workflow's own `GITHUB_TOKEN`
has `actions: write` and queues its successor independently. An agent-side 403
does not establish that the in-workflow self-chain is broken. Do not repeatedly
retry an agent-side permission denial.

After the changes are reviewed and merged, set repository **Actions variable**
`ENABLE_FREE_TUNNEL=true` for a permitted loop test (Settings -> Secrets and
variables -> Actions -> Variables). Otherwise the job intentionally skips, even
if a dispatch is accepted. Leave `CF_TRANSPORT=auto` and `WS_EARLY_DATA=false`
until your client comparison supports changing them.

From an authorized environment with repository `contents: write` permission:

```bash
gh api -X POST repos/asomethinggood-sys/My-small-project/dispatches -f event_type=vpn-loop
```

A successful request returns **HTTP 204 with no response body**. The workflow
already declares `repository_dispatch: types: [vpn-loop]`. This event runs the
**default-branch** workflow, not this task branch. Before merge it would start
old main-branch code, so it is not a way to validate the proposed changes.
This event is an emergency kick: its concurrency policy cancels an active run
in that workflow's concurrency group and interrupts connected users.

Alternatively, an authorized repository user can open **GitHub -> Actions ->
VPN Loop -> Run workflow**, select the merged default branch, and run it.
Manual workflow dispatch is enabled. The job's successor step continues using
its own `GITHUB_TOKEN` to dispatch the same ref before the six-hour limit.

An accepted API request is **not** evidence of successful deployment. Inspect
Actions: the job must not be skipped, the Xray config validation and full
TLS/WS/VLESS probe must pass, and the publication step must succeed. Only then
retrieve the newly published config. A fresh Tehran-side v2rayNG test is still
required for availability and latency. Do not use expired experiment artifacts.

**PR gate requested by the user:** no PR is opened while the proposed latency
settings remain only experimental. Functional config validation passed, but
there is no verified Tehran result or currently live optimized profile. Keep
that distinction explicit; do not describe the experimental options as a proven
upgrade. No repository dispatch or main-branch change was made for this check.

## Validation

```bash
python3 -m unittest discover -s tests -v
for f in scripts/*.sh; do bash -n "$f"; done
bash scripts/download-binaries.sh
python3 scripts/generate.py --host vpn.example.com
.runtime/bin/xray run -test -c .runtime/xray.json
.runtime/bin/xray run -test -c .runtime/client-test.json
.runtime/bin/caddy adapt --config .runtime/Caddyfile --adapter caddyfile >/dev/null
python3 tests/integration.py
```

`vpn.example.com` is **test data**, not an endpoint. Integration tests exercise a
local SOCKS/VLESS/WS round trip, not TLS/ACME or Tehran routing. `validate.yml`
performs these checks without deploying a tunnel, publishing configs or secrets.
See [test results](docs/test-results.md) for actual execution versus pending tests.

## Rollback

- Before migration, retain the old profile and back up VPS state as above.
- To stop the VPS: `sudo systemctl disable --now arena-caddy arena-xray`.
  Undo its DNS record if no longer needed. Preserve certificates/config for a
  future restart; cancel the VPS billing separately if retiring it.
- To revert an update: stop both units, restore the backed-up binaries, configs,
  certificate state and units (including ownership/modes), run
  `sudo systemctl daemon-reload`, start both units and rerun verification.
- To return to the legacy experiment, only if terms permit, enable the variable
  and dispatch the existing workflow, then retrieve a **fresh** release config.
  An old Quick Tunnel URL will not resurrect. Expect the old latency and gaps.
- Source rollback: revert this change through normal review on the active branch;
  no main-branch reset or force-push is needed. Disable/cancel any legacy runs
  before changing subscription publication to avoid stale overwrites.
