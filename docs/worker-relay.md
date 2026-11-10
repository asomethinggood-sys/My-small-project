# Stable address: bih.asomethinggood.workers.dev

**Status: implemented and locally unit-tested, NOT deployed or end-to-end verified
on Cloudflare. No stable v2rayNG config is being claimed as working yet.**
The current main-branch Quick Tunnel remains unchanged. No PR or merge is performed
while this new relay remains experimental.

## One-time setup (no purchased domain)

### 1. Paste the Worker code

Open Cloudflare dashboard -> Workers & Pages -> **bih** -> **Edit code**.
Replace the Hello World source with the entire contents of
[`worker/worker.mjs`](../worker/worker.mjs), then **Deploy**. It is an ES module;
do not wrap it in an HTML page or change the WebSocket path constant.

### 2. Add a small persistent route store

Cloudflare -> Storage & databases -> **Workers KV** -> Create namespace.
Name it `vpn-route` (dashboard labels can vary).

Return to Worker **bih** -> **Bindings** -> Add -> **KV namespace**:

- Variable/binding name: **`ROUTES`** (exact uppercase spelling)
- Namespace: select **`vpn-route`**

Save/deploy. No manual KV key or value needs to be entered: the workflow writes it.
The route is stored outside any individual Worker instance so that instance
restarts do not forget the active tunnel. KV is eventually consistent: other
locations can see the old route for 60 seconds or more after a change.

### 3. Save the SAME update secret in two places

Generate one random secret **locally**, for example:

```bash
openssl rand -hex 32
```

Alternatively use your password manager's random generator (at least 32 random
characters; a 64-character hex value is recommended). Do not use a tunnel ID,
UUID, account password, example value or memorable phrase. **Never paste it into
chat, source code, screenshots, a public config, or an Actions variable.**

- Cloudflare Worker **bih** -> Settings -> Variables and Secrets -> Add:
  - Type: **Secret**
  - Name: **`UPDATE_TOKEN`**
  - Value: your generated secret
  - Save/deploy.
- GitHub repo -> Settings -> Secrets and variables -> Actions -> **Secrets** ->
  New repository secret:
  - Name: **`RELAY_UPDATE_TOKEN`**
  - Value: the **same** secret.

This is a narrowly scoped shared password for updating the relay route, **not**
a Cloudflare API token. No Cloudflare account credentials are needed by the
workflow. Tell the agent only that these steps are done.

**Do not turn on `RELAY_ENABLED` yet.** The Worker-to-Quick-Tunnel path must be
live-tested first. Until a backend is registered, `/healthz` returns 503; this is
expected. Visiting the Worker home page returns 404, also expected. Even a 200
health response only means a route is stored, not that VLESS works.

## Activation gate / workflow behavior

After the Worker is configured, run a bounded live test on the task branch before
opening/merging a deployment PR. Local mocks do not prove the Cloudflare network
path works. A genuine test must start the fixed-identity Xray origin and a Quick
Tunnel, verify that tunnel, POST its address via `scripts/update-relay.py`, then
use `scripts/check-tunnel.py` against **bih.asomethinggood.workers.dev**, with the
UUID/path from `worker/profile.json`. TLS verification must remain enabled. It
must receive HTTP 200 from an independent HTTPS destination through the complete
SOCKS -> VLESS -> Worker -> Quick Tunnel -> Xray path. Then test Android import
and availability from Tehran. Any Cloudflare routing rejection is a failed test,
not a reason to publish a placeholder or disable certificate verification.

The updated `vpn.yml` supports opt-in repository variable `RELAY_ENABLED=true`
after validation/review/merge. `ENABLE_FREE_TUNNEL=true` is also required for that
workflow to run. Only default-branch jobs update this shared Worker route and
publish the config; branch experiments must not silently overwrite it. Keep
`WS_EARLY_DATA=false` initially; changing it changes the imported URI.

When enabled, each run:

1. Reads the fixed **public/shared** UUID, path and hostname from
   `worker/profile.json`. These are intentionally not a private credential set.
2. Starts a new random Quick Tunnel and verifies direct VLESS connectivity.
3. Sends an authenticated HTTPS POST to the Worker's `/__route`, storing only the
   new backend hostname and a lease expiry. No secret appears in the URI.
4. Verifies the complete VLESS path through the Worker (with retries for KV
   propagation). On failure the job fails **before publishing** a new config.
5. Publishes a URI with the **same Worker hostname, UUID and WS path** each run.
   Retrieve it from the existing `vpn-config` release/summary only after success.

Neither this setup nor a 200 route-update response proves <200 ms from Tehran.
The Worker is a WebSocket relay, not a new nearby VLESS egress: traffic still exits
from the runner. This can add latency and does not choose a European runner.

## Limits and continuity

Workers and KV have their **own free-plan quotas**. Requests, KV reads/writes,
CPU, service availability and provider terms apply; inspect your dashboard's
usage and current plan limits before sharing widely. Each attempted WebSocket
connection goes through the Worker and reads KV. Updates should be only a few
per day, but connection attempts/reconnect storms can consume much more quota.
This is not unlimited free public proxy hosting. No paid plan is required by this
code, and no paid feature should be enabled automatically.

The relay uses HTTP WebSocket forwarding, **not** `cloudflare:sockets` or a custom
VLESS parser. General Workers outbound-TCP socket restrictions are not a substitute
for testing this distinct HTTP forwarding path. Cloudflare can still reject or
restrict it. The admin endpoint permits only `*.trycloudflare.com` destinations,
rejects expired/overlong leases, and never follows redirects. It is not an
arbitrary URL proxy. Failed upgrades return 502; missing/expired routes return 503.

A stable config is **not seamless continuity**. The loop still ends the old runner
before the queued runner is ready. Existing WebSockets and downloads break, and
clients reconnect to the same address when the new backend and KV mapping become
available. KV propagation can lengthen the gap. A five-hour-55-minute lease avoids
using a stale mapping indefinitely; after a stalled loop the service fails closed.
A Worker deploy can also disconnect sessions. Public sharing may exhaust quotas.

## Rollback

Set repository variable `RELAY_ENABLED=false` before the next run; it returns to
publishing the direct rotating Quick Tunnel config. Import/refresh that config;
the stable Worker URI will not automatically switch itself to a direct profile.
Changing a variable does not modify an already-running job. Do not delete a shared
Worker while users rely on it without notifying them.

To disable the Worker immediately, remove its public route/disable it in Cloudflare.
To invalidate the route mapping, delete KV key `active-route` (propagation still
applies). Rotate `UPDATE_TOKEN` and `RELAY_UPDATE_TOKEN` together if leaked. Never
publish the admin token even though the VLESS profile is deliberately shared.
