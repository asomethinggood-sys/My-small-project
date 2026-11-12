# Continuum Windows 0.2 — DNS and connection stability correction

Normal Continuum desktop, without Nyx country pools. Targets Windows 10 1809+ and Windows 11.

## Current downloads

[Release 0.2.0-10](https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-windows-0.2.0-10):

- [Intel/AMD x64 ZIP](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-windows-0.2.0-10/Continuum-0.2.0-windows-x64.zip): **86,044,392 bytes**.
- [Windows ARM64 ZIP](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-windows-0.2.0-10/Continuum-0.2.0-windows-arm64.zip): **79,749,772 bytes**.
- [SHA256SUMS.txt](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-windows-0.2.0-10/SHA256SUMS.txt).

Exit the old app (including its tray process), extract the entire new ZIP to a fresh folder and open `Continuum.exe`. Accept the administrator prompt and Connect. Existing DPAPI-protected settings remain in the same per-user location. .NET is bundled. App binaries remain unsigned; Wintun signature and pinned engine archive hashes are verified during packaging.

## Why this update

The user reported that Windows barely loaded pages although Android was responsive. Comparing the actual configurations found a Windows-specific `nonIPQuery=drop` setting. Android did not use it. Dropping HTTPS/SVCB DNS questions can make modern browsers wait for timeouts; the corrected policy returns an immediate empty answer without bypassing the proxy.

Windows now uses two independent IP-literal, certificate-verified DoH resolvers with caching and bounded parallel queries. Testing caught two additional traps before final delivery: a hostname-based secondary could depend on the failed primary for bootstrap; serial fallback could impose four seconds on every lookup, including a secondary-cache hit. Both are removed. No ISP DNS fallback is added to the Windows client.

The app also:

- Keeps live tunnels running when external health destinations fail, rather than destroying sessions after three failures.
- Checks two health destinations once per minute, with bounded per-request cancellation.
- Ignores label-only profile updates and TUN-only address events for reconnection decisions.
- Shows actual tunnel DNS response time separately from HTTPS request duration. HTTPS duration is not ICMP ping.

## Verified Windows results

[Workflow 43232334029](https://github.com/asomethinggood-sys/My-small-project/actions/runs/43232334029), source **4ebd32e**, passed all build and runtime checks:

- Twelve profile, security, DNS-policy, subscription and recovery-policy test groups.
- Self-contained x64 and ARM64 publication.
- Full production configuration validated by pinned Xray v26.10.31.
- Owned engine startup, proxied HTTP request, shutdown and cancelled-start cleanup.
- Actual scoped Windows TUN HTTP/UDP, UDP/TCP DNS, byte-verified 512 KiB download and 64 KiB upload, certificate-verified public HTTPS via the test proxy, route cleanup and WPF launch/close.

Measurements below are **Windows Server CI fixture measurements, not the user's PC or Tehran latency**:

| Check | Result |
| --- | --- |
| Reproduced old HTTPS DNS record policy | No response before the 1,500 ms test deadline |
| Corrected HTTPS / SVCB DNS reply | 0.80 / 0.29 ms |
| Cold / cached A lookup | 112.74 / 0.40 ms |
| TCP DNS | 0.44 ms |
| Verified 512 KiB download / 64 KiB upload over local test peer | 7.59 / 20.18 ms |
| Primary DoH deliberately unreachable: cold / cached secondary answer | 90.26 / 0.38 ms |

An intermediate serial-fallback build (43231763159) succeeded functionally but measured approximately 4,053 ms cold and 4,001 ms cached with a failed primary. Final build 10 races the equivalent resolvers and adds regression limits to prevent that four-second stall from returning. Prefer build 10 over intermediate build 9.

## Server workflow changes and deployment boundary

The working branch's `.github/workflows/vpn.yml` now uses a validated normal-Continuum WS origin generator with genuinely cached, independent server-side DoH and IPv4-first hostname resolution. `localhost` was not used as a pretend cached resolver: Xray's localhost implementation bypasses its DNS cache. Server-side `https+local` resolves directly at the exit and is not present in the Windows client.

An ephemeral runtime script adds QUIC UDP-buffer headroom without shrinking existing buffers, TCP PMTU-blackhole recovery, and BBR/FQ where the kernel supports them. It does not change firewall rules, routes or persistent sysctl files. BBR affects TCP, not QUIC's userspace congestion control. Connector transport remains `auto`.

Bounded same-origin baseline/WS-early-data checks passed in **43230736124**, **43231172404**, and final server source **2467878** in [43232538109](https://github.com/asomethinggood-sys/My-small-project/actions/runs/43232538109). Three samples per mode on one runner do not establish a user latency improvement. Early-data results varied between runs, so it remains an explicit optional, readiness-gated choice rather than a forced default.

**These server changes are committed on `arena/f056ce38-my-small-project`; they have not replaced the running default-branch server, changed `main`, or overwritten the shared subscription.** Only short private acceptance connectors were started and cleaned up. Installing the Windows update does not deploy the server workflow changes.

## Limits and prior version

No 200 ms guarantee is established. Windows Server 2022 CI is not physical Windows 10/11 testing; ARM64 remains cross-published rather than hardware-tested. The TUN fixture captures a reserved test range, not all runner control traffic, so this is not a complete public-Internet leak audit. The existing upstream can still be unavailable independently of the app. Dynamic guards end when the engine stops: this is not an always-on kill switch. Profile replacements interrupt established TCP sessions.

The UI/controller is .NET/WPF and the tunnel engine is Xray; no Android Rust/JNI port is claimed. See [Windows guide](../windows/README.md).

Previous 0.1 all-green release: [0.1.0-6](https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-windows-0.1.0-6), workflow 43222579152, source dbd3b0d. Its original limited tests did not cover browser HTTPS/SVCB DNS questions or failed-resolver latency; those omissions are addressed in 0.2.
