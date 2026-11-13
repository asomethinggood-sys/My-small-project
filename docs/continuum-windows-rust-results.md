# Continuum Windows 0.3 — managed native desktop

Final release: https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-windows-0.3.0-14

Complete x64 download: https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-windows-0.3.0-14/Continuum-0.3.0-windows-x64.zip

**13,332,455 bytes (13.33 decimal MB)** for the complete ZIP, including the app, protocol engine, Wintun and license notices. This is the download size, not a claim that extracted files occupy less than 20 MB. No .NET, WebView or Visual C++ redistributable download is needed. MSVC runtime is statically linked and the PE dependency audit rejects those external runtime imports. Only x64 is produced; no ARM64 build.

Source commit: ddd5655. Final Windows CI: 43494795805, all steps successful. No changes to main and no PR.

## Architecture / UI

New executable is built from windows/native, not the legacy WPF project. First-party desktop code (Win32 UI, subscription validation, config generation, session policy and engine ownership) is Rust. Xray packet/protocol implementation remains Go, rebuilt from pinned upstream commit a4a3dff5b20c2faae567b742c172c7b95e75c083 with a reduced registration set. This is not an all-Rust VPN stack or a claim that most binary bytes are Rust. Old WPF sources remain for history/tests but are not packaged.

UI contains no repository/source URL, endpoint, protocol, provider, profile import or custom-source control. UI audit enumerates native controls and rejects technical terms or editable configuration. Old saved custom sources are not read. Network errors are mapped to fixed consumer messages; engine logs are discarded rather than shown. The fixed subscription identity is unchanged. Required licenses and corresponding source remain distribution assets. UI cleanup does not conceal implementation from APK/EXE inspection or network analysis.

## Routing / session changes

- Old desktop could restart whenever a new authoritative profile appeared on a five-minute update. New policy pins a healthy active session, including across changed publications. An exited engine can restart; a different peer is selected only after three failed dual-site checks. A health failure alone never recycles the same live peer. No guarantee that an externally terminated server can keep a call alive.
- TUN sniffing no longer overwrites a destination IP with the sniffed hostname. This avoids re-resolving a CDN-selected address behind the application's back.
- UDP destination port 443 is suppressed to encourage browser TCP/HTTPS fallback; other UDP remains tunneled. This is a compatibility choice, not a guarantee that all QUIC-only applications work.
- MTU 1280, explicit 600-second connection-idle policy, 30-second half-close budgets and transport TCP keepalive settings. These do not override server-side disconnections.
- Cached parallel DoH retained, including prompt empty HTTPS/SVCB replies instead of DNS timeouts. No direct traffic bypass added.

These changes address identified client behavior and plausible transport failure modes. The user's actual Discord session and YouTube video/CDN failure were not reproduced from the user's network. Do not describe the fixture tests as proof that all service-specific failures are fixed. Server exit restrictions and availability remain outside a desktop-only change; main/live server configuration was not changed.

## Final evidence

Actual Windows Server 2022 runner:

- Rust parser / routing / session-policy tests passed.
- Native window, consumer UI audit, close, static-runtime PE dependency audit passed.
- Rust-owned engine start, proxied request, stop and listener cleanup passed.
- Production-generated scoped Windows TUN configuration routed TCP, UDP, DNS and byte-verified downloads/uploads through a local test peer.
- A single UDP socket on destination port 50000 survived **360 seconds**, with **3,554 exact echoed packets**, concurrent with **80 byte-exact HTTP 206 media segments**.
- UDP/443 blocked while TCP/443 to the same peer succeeded.
- HTTPS/SVCB DNS: 0.93 / 0.41 ms. Cold/cached A: 107.51 / 0.48 ms. Forced failed primary resolver: cold 65.0 ms, cached 0.62 ms. Runner fixtures, not user latency.
- Scoped tunnel routes removed after engine termination; actual certificate-verified public HTTPS through test peer passed.
- Hard publication gate rejects any complete ZIP >= 20,000,000 bytes.

Earlier build exposed a native window-title initialization mistake; DefWindowProc now receives WM_NCCREATE, and both window launch gates passed. Final static-CRT build repeats the complete network suite; intermediate release 13 is superseded by 14.

## Install / limits

Exit the old app (including its tray icon), extract the complete new ZIP into a fresh folder, run Continuum.exe and accept the administrator prompt. Do not copy only the executable. Closing this app disconnects; minimizing leaves it running. App is unsigned and Windows may show unknown-publisher warnings. Not an always-on kill switch. Physical Windows 10/11, Discord service and YouTube CDN acceptance from the user's network remain unverified.

Release contains SHA256SUMS.txt, matching Cargo.lock, and corresponding-source archive with the modified Go registration file and build instructions. Build dependencies are not runtime downloads. No private credentials were published.
