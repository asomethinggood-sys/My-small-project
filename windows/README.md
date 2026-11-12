# Continuum for Windows 10 / 11

Native WPF desktop client for **normal Continuum**, separate from Nyx. It uses the existing authoritative subscription unchanged. No country pools, new server workflow, Worker account or domain setup.

## Version 0.2: DNS and stability correction

The 0.1 port explicitly dropped non-A/AAAA DNS questions. In particular, HTTPS/SVCB queries could time out rather than receive the immediate empty answer used by Android. This version removes that drop policy and adopts Android's two cached, certificate-verified DoH upstreams with four-second per-resolver budgets and an explicit proxy route. Both DoH addresses are IP literals (Cloudflare 1.1.1.1 and Google 8.8.8.8), so the fallback does not need the failed primary to resolve its own hostname. HTTPS certificate verification remains enabled. DNS does not fall back to your ISP.

Health checks now try two destinations once per minute; an unreachable health site no longer kills a live tunnel. Label-only subscription changes and TUN-only address notifications do not cause reconnects. The app displays **tunnel DNS response time separately from HTTPS request duration**. HTTPS duration includes connection/TLS/server work and is not an ICMP ping; a 200 ms result is not guaranteed.

Server-side settings in the working branch add cached IPv4-first origin DNS, optional available BBR/FQ and QUIC buffer headroom, PMTU recovery, and readiness-gated WS early data. These do not relocate the runner. They do not change an already-running default-branch server merely because you install this app.

## Install and use

1. Download the Windows **x64** ZIP (Intel/AMD) or **ARM64** ZIP (Windows on ARM).
2. Extract the **entire folder** to a location you control. Do not run inside the ZIP or move only the EXE.
3. Open `Continuum.exe` and accept the administrator prompt. Wintun requires elevation.
4. Leave **Automatic subscription** selected and click **Connect**. Or paste one supported connection link and select **Imported connection link**.
5. **Disconnect** stops the engine and pauses automatic reconnect. Closing the window disconnects and exits. **Minimize to tray** keeps the tunnel alive; the tray menu includes Disconnect and Exit.

Windows 10 1809+ and Windows 11 are the target OS versions. .NET 8 is bundled; no separate runtime installation is required. ARM64 is a separate package, not the Intel/AMD build. Preview executables are not Authenticode-signed: Windows may show an unknown-publisher warning. Do not disable antivirus or system security controls to install them. Confirm the release source and checksums.

## Included

- Xray v26.10.31 and architecture-matched, signature-checked Wintun from SHA256-pinned official archives.
- Device-wide IPv4/IPv6 TUN routes, TCP and UDP, proxied DoH for ordinary DNS, IPv4 DNS answers for compatibility, explicit physical-interface binding for Xray sockets.
- Xray's dynamic Windows Filtering Platform DNS/missing-route guards while the engine runs.
- Original automatic single-profile subscription, HTTPS-only redirects, bounded response sizes, exact-resource ETag cache, five-minute refresh, manual Check now and network-change notification.
- VLESS / VMess / Trojan TCP+TLS or WS+TLS; Shadowsocks AES-GCM / ChaCha20-Poly1305. Unsupported extensions are rejected, not silently ignored. No Reality, gRPC, plugins or subscription-list selection claim.
- TLS certificate checks remain enabled. A successful proxied HTTPS response is required before showing Connected.
- Manual cancellation, capped exponential retry, a Windows job object to stop the owned engine if the app exits, and an attempt at graceful console shutdown before forced termination.
- Settings encrypted with Windows DPAPI for the current Windows account. Runtime configuration goes to the engine through stdin, not a persistent plaintext profile file. Raw engine errors and credentials are not logged. No analytics.

## Important limits

This is **not an always-on kill switch**. Dynamic guards end when the engine exits; normal Internet routing can resume during disconnect, crash recovery or a profile replacement. A profile rotation interrupts existing TCP sessions. More-specific LAN routes may remain outside the tunnel. Custom application DNS protocols and captive portals require separate validation. Do not stack this with another VPN or Mobile Hotspot without testing.

A failed health URL does not prove all Internet traffic is broken; the app retains a running engine even after repeated failed checks, rather than interrupting existing sessions. An unavailable subscription does not destroy an otherwise healthy cached connection. The built-in subscription points to the existing service and does not guarantee that the backend is currently up. No 24/7 hosting, low-ping guarantee or measured Tehran latency improvement is provided by this client port.

If a forced process termination leaves networking impaired, exit Continuum and reconnect your physical network adapter or reboot. Do not delete unrelated adapters or reset all firewall rules. Xray normally removes its owned routes and dynamic filters; physical-interface changes cannot be guaranteed restored after every forced termination.

## Build / verification

On Windows with .NET 8 SDK and PowerShell 7:

```powershell
dotnet run --project windows/Tests/Tests.csproj -c Release
dotnet publish windows/Continuum/Continuum.csproj -c Release -r win-x64 --self-contained true -o package-x64
./windows/scripts/fetch-engine.ps1 -Architecture x64 -Destination package-x64/engine
./windows/scripts/smoke.ps1 -AppDirectory package-x64
```

CI validates profile/config/security boundaries, subscription redirect/cache policy, engine configuration, owned process lifecycle, actual Windows TUN HTTP and UDP through a local Shadowsocks fixture, scoped route removal, and the packaged desktop's startup/close. The TUN fixture deliberately captures only a reserved test range, not runner control traffic; it is not a full public-Internet leak audit. Full production routing config is separately validated by Xray. Windows Server runner results are not physical Windows 10/11 or ARM hardware tests. ARM64 is cross-published and requires device acceptance.

Dependencies and licensing: [THIRD_PARTY.md](THIRD_PARTY.md). Build artifacts and downloaded engines stay outside Git.
