# Continuum 0.3 — website compatibility and connection optimization

## Full APK

[Download continuum-0.3.0-arm64.apk](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-0.3.0-preview-15/continuum-0.3.0-arm64.apk)

- Android 8+; ARM64 only. Direct installer, not an artifact ZIP.
- **19,059,871 bytes — 19.06 MB / 18.18 MiB.** Installed storage is larger.
- SHA256: `db9a09202faf459131a3517ede1c50ece630bf8ac3f341be39e4a14cef5070b9`.
- Non-debuggable, shrunk/compressed release APK; preview signer. Uninstall the previous preview if signatures differ, which deletes its settings.
- [Release, exact application source, native source references and licenses](https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-0.3.0-preview-15).

## What changed

### Website compatibility

Previously the TUN handed ordinary UDP DNS to public resolvers through the server. That path depends on working server-side UDP/53. It also returned IPv6 destinations even when the remote server might have no IPv6 connectivity, and did not recover hostnames from application traffic.

The new Android-side configuration:

- Intercepts TUN TCP/UDP port 53 into Xray's DNS outbound. A/AAAA resolution uses cached, certificate-verified **DNS-over-HTTPS through the selected proxy**, with Cloudflare and Google upstreams. No direct/freedom DNS fallback is configured.
- Defaults to IPv4 DNS answers for compatibility with IPv4-only servers. Settings can enable dual-stack answers. IPv6 routes stay inside the VPN in either mode; this is not an IPv6 bypass.
- Enables HTTP Host/TLS SNI destination recovery. A stale/poisoned destination IP can be replaced by the hostname for remote resolution; TLS content is not decrypted.
- Uses matched Android/native TUN MTUs, default **1400**, with **1280/1400/1500** selectable. These are compatibility options, not guaranteed speed improvements.

Important limits: apps using their own DoH/DoT may bypass this DNS-answer policy. ECH, IP literals, cached IPv6 records and non-HTTP/TLS traffic may not have a usable hostname to recover. Xray's DNS outbound handles A/AAAA; its default response to other record types is empty. No specific user-reported domain was supplied, so that exact failure is not yet reproduced or declared fixed.

### Connection and idle work

- Cold start opens the real core/TUN before its reachability check, rather than constructing a disposable preflight core first. Replacing an existing endpoint still verifies the candidate before replacement.
- Health checks use the running core, retaining its DNS cache and existing sessions.
- A failed health-check website no longer causes automatic destruction of an otherwise-running engine. A second check endpoint is tried if the first fails. These remain HTTP checks, not ping or proof that every destination is reachable.
- Check now and physical-network changes invalidate the health cache immediately.
- Normal manual profiles schedule checks at **300 seconds screen-on / 900 seconds screen-off**, instead of waking every minute just to skip a health probe.
- Automatic subscription polling preserves the selected 30/60/120-second interval while interactive, with a minimum 120 seconds when screen-off. Health checks are five minutes interactive, fifteen minutes screen-off. Failed checks have separate retry backoff. No-network state avoids outbound probes and waits for callbacks, with a 120-second fallback check.
- UI status uses Binder pushes rather than per-second Binder polling. Settings/profile parsing is no longer repeated for every visible countdown tick. Unchanged notifications and status-ring redraws are suppressed. UI timers stop when the screen is not visible.
- No wake locks, exact alarms, speculative multiplexing or unmeasured socket tuning were added.

These are reductions in scheduled work, not a measured battery percentage. Longer screen-off subscription intervals can delay endpoint discovery. No latency improvement versus 0.2 is claimed without a controlled A/B measurement.

## Verification

Passing run: [42605622200](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42605622200).
Built application source: `357c0051150d0d8156c3acf791504dc5881ebb76`.

- **27 JVM tests**, debug/release lint and ARM64 release packaging passed.
- Two API 35 x86_64 instrumentation tests passed. A separate app UID exercised ten checks for each of four live fixture profiles (Shadowsocks aes-128-gcm; VLESS, VMess and Trojan over WS+TLS):
  1. Proxy-only TCP marker.
  2. UDP DNS A query, with the server explicitly blocking port 53.
  3. TCP DNS A query.
  4. Repeated cached A query.
  5. Empty AAAA response in IPv4-answer mode.
  6. HTTP Host recovery from an unusable destination IP.
  7. Exactly validated 524,288-byte download.
  8. Exactly validated 65,536-byte upload/echo.
  9. Exactly validated 1,200-byte UDP echo.
  10. Real `https://example.com/` with normal certificate validation.
- MTUs 1280, 1400 and 1500 were exercised across these fixtures.
- Explicit Check now, bound-service Disconnect, saved pause after a simulated system start, cancelled-fetch reconnect and stale-work rejection passed.
- [Full runner network report](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-0.3.0-preview-15/network-report.txt).

Runner Connected times were 770/1840/1209/838 ms for the four fixtures. These are one run on a hosted emulator, not Tehran, not physical ARM, not raw ping, not an A/B speed comparison and not a promise for the production subscription. Per-operation timings include emulator scheduling; a repeated DNS query was not always faster.

The initial expanded run passed DNS/Host/large-download checks but failed its HTTP upload with an unexpected EOF against the simple HTTP/1.0 fixture. The fixture now uses explicit HTTP/1.1 framing and self-tests its upload echo before Android starts; all four upload cases then passed. This does not establish universal HTTP/1.0 compatibility or identify the user's unnamed failing websites.

## Phone test

1. Install the new APK; uninstall the old preview only if Android rejects its signature. Accept VPN permission and keep the existing automatic subscription.
2. Start with **IPv4 answers + MTU 1400**. Reopen affected browser tabs after reconnecting so stale DNS/connections are not reused.
3. If page transfers still stall, try MTU 1280. Settings changes rebuild the engine and interrupt existing sessions.
4. If a browser or Android uses custom secure DNS, record that setting when reporting failures; it may bypass the app's DNS policy. Do not assume all website failures are DNS failures.
5. Report affected domains, phone/Android version, Wi-Fi versus mobile, which other client works with the same profile, and whether failure is DNS error, TLS error or timeout. Do not publish private profile credentials.

Still unverified: the user's exact sites, physical ARM release runtime, real ISP/Tehran latency, battery/CPU A/B measurements, long-duration stability, full IPv6/leak matrix, real OEM lockdown/Always-on behavior, and production rotation/handoff. Client changes cannot eliminate backend outages or migrate established TCP sessions between servers.

Production subscription/server workflows were not changed. No PR or main-branch merge was opened. Work remains on `arena/f056ce38-my-small-project`.
