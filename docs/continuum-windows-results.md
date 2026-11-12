# Continuum Windows desktop

Normal Continuum is now available as a standalone Windows desktop client, without Nyx country pools. Windows 10 1809+ and Windows 11 are the targets.

## Downloads

Current all-green build: [release 0.1.0-6](https://github.com/asomethinggood-sys/My-small-project/releases/tag/continuum-windows-0.1.0-6).

- [Intel/AMD x64 ZIP](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-windows-0.1.0-6/Continuum-0.1.0-windows-x64.zip): **86,040,440 bytes**.
- [Windows ARM64 ZIP](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-windows-0.1.0-6/Continuum-0.1.0-windows-arm64.zip): **79,745,819 bytes**.
- [SHA256SUMS.txt](https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-windows-0.1.0-6/SHA256SUMS.txt) accompanies the release. The app is unsigned; Wintun's signature and the engine archive SHA256 are checked during packaging.

Extract the entire ZIP, open `Continuum.exe`, accept the administrator prompt, then click **Connect**. The normal Continuum subscription is prefilled. No separate .NET installation is needed. Closing the window disconnects; Minimize to tray keeps the tunnel running.

## What passed

Workflow [43222579152](https://github.com/asomethinggood-sys/My-small-project/actions/runs/43222579152), source `dbd3b0d`, passed:

- Ten executable test groups: VLESS/VMess/Trojan/Shadowsocks parsing, TLS/extension rejection, single-profile subscriptions, IPv4/IPv6 TUN and WFP guard generation, no direct fallback outbound/external listener, HTTPS redirect/ETag scoping, HTTPS downgrade rejection.
- Self-contained x64 and ARM64 publication with architecture-matched Xray v26.10.31 and Wintun.
- Full production TUN configuration accepted by the pinned Xray engine.
- App-owned engine start, proxied request and shutdown; cancelled startup leaves no owned process running.
- Real Windows TUN HTTP marker and UDP echo through a local Shadowsocks peer. The fixture routes only a reserved test range; the local peer permits only its owned echo port.
- Removal of that scoped tunnel route on engine exit.
- Packaged WPF desktop startup and clean close. Screenshot retained in the Windows-validation workflow artifact.

The previous all-green build was workflow 43222011106, source 8d871a8, release 0.1.0-5. Build 6 adds shutdown-race hardening and cancelled-start coverage.

## What is not established

Tests ran on Windows Server 2022 CI, not physical Windows 10/11 PCs. ARM64 was cross-published, not hardware-executed. The scoped fixture does not prove production-wide leak freedom, physical Wi-Fi handoffs, latency improvements, or reliable upstream availability. The existing public subscription/backend is unchanged and can be unavailable independently of the client.

The Windows UI/controller is .NET/WPF; this is not a claim that the Android Rust/JNI layer was ported. Xray remains the actual tunnel engine. No country provider or server trial is started by installing the app. This is not an always-on kill switch: ordinary routing may resume when the engine stops, including during retries or profile replacement.

See [Windows guide](../windows/README.md) for supported profiles, privacy, recovery and build instructions.
