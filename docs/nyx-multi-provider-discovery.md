# Multi-provider discovery: current status

Nyx does **not** yet provide 30 selectable countries or 1,000 usable VPN servers. The 30 country codes in policy are targets, not available routes. This change adds discovery, not a production VPN service. It does not create accounts, collect credentials, start tunnels, alter host routing, issue phone sessions, or replace an active session.

## What was observed

[Bounded provider run 42854890554](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42854890554) fetched one page per provider. The strict VPN Jantit parser recognized 60 distinct listed hosts in 23 target countries, including DE 8, FR 5, GB 3 and NL 3. All 60 rows explicitly claimed TCP and UDP; neither transport was tested. The VPN Gate snapshot had 74 distinct ingress IPs in six target countries; these counts did not inspect transports. Together the snapshots covered 25 target countries and 134 provider-qualified endpoints, but shared hosts across providers are not cross-deduplicated. All counts are momentary advertisements, not tested connections or proof of exit geography. The Jantit parser requires a matching account link, download link and listed hostname; it may omit other cards. Each identity is a provider-qualified hash. An attempted unauthenticated Proton directory request returned an HTTP error; that attempt is not repeated automatically. Its parser is experimental and no successful real response has validated its schema. Proton's free tier has restrictions on country selection and its large advertised inventory is not a grant of usable, selectable free servers.

VPN Jantit advertises TCP and UDP, but advertisements do not prove transport or tunneled UDP works. Personal accounts expire and are subject to provider limits; provisioning, shared-use permission and geographic verification are not implemented. The Psiphon service license restricts access to clients created by Psiphon; the local OSSH fixture in backend tests is not an integration with Psiphon's public service. There is no verified official-app handoff or country selector in Nyx. VPNBook has also been investigated separately; previously observed German endpoints had conflicting geography and are not verified country exits. See `docs/nyx-country-route-followup.md` for the narrowly scoped and now-closed VPN Gate route diagnostic.

## Running a fresh metadata snapshot

From the repository root, on a host with HTTPS access to the two providers:

```sh
python3 -m scripts.egress_catalog --live --vpnjantit-live --output .runtime/egress/catalog.json
```

Each source is fetched independently once. Even when a source fails, the command atomically writes a fresh partial snapshot with a failure status and exits nonzero; it never fills gaps with old observations. The JSON expires after the configured 15-minute TTL. It contains hashed provider identities, not profiles or credentials, and marks every country unselectable and every verified count zero. `advertised_tcp_and_udp_servers` counts only explicit same-row provider claims, not successful TCP/UDP tests; the count is not a list of usable servers.

This is a one-shot command that an operator can schedule on infrastructure they control in accordance with provider policies. **There is currently no deployed scheduler, continuously refreshed public feed, or Android publishing path for these snapshots.** The bounded GitHub workflow is a manual/branch-change diagnostic, not a permanent server or live refresh mechanism; it does not modify the shared release. A scheduler would need operational hosting and a secure publication/reachability design, source-specific rate limits, monitoring, and permission for the intended usage. Running this metadata command periodically alone would not produce a VPN pool.

## Remaining requirements

Authorized provisioned accounts and private credential storage; provider permissions; isolated per-user pool routing; authenticated issued-route exact-IP country checks; independently tested transport and UDP forwarding; leak and tunnel-drop enforcement, health/expiry and disconnect; reliable long-lived hosting and distribution; stable Android signing, release build sizing, and physical POCO/HyperOS tests remain necessary. No service or APK is represented as complete by these findings.
