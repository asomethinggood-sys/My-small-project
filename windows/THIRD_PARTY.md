# Runtime notices

Continuum Windows is an original desktop client, not a fork of v2rayN or v2rayNG.

- **Xray-core v26.10.31** — Mozilla Public License 2.0. Official executable is redistributed unmodified. Its LICENSE is included under engine/LICENSE. Corresponding source: https://github.com/XTLS/Xray-core/tree/v26.10.31 . Build instructions and dependency notices are in that source tree.
- **Wintun** — official architecture-matched library bundled by the pinned Xray release. License is included under engine/LICENSE-Wintun. Source and distribution terms: https://www.wintun.net/ . Build checks the archive digest and the DLL's Authenticode signature.
- **.NET 8 / WPF / Windows Forms** — Microsoft .NET components, predominantly MIT; third-party components have their own notices. Unmodified self-contained runtime accompanies the app. Source: https://github.com/dotnet/runtime and https://github.com/dotnet/wpf . Runtime LICENSE.TXT and THIRD-PARTY-NOTICES.TXT are included with packaged builds.
- **System.Security.Cryptography.ProtectedData 8.0.0** — Microsoft, MIT; Windows DPAPI integration. Source: https://github.com/dotnet/runtime/tree/v8.0.0/src/libraries/System.Security.Cryptography.ProtectedData .

No geosite/geoip databases are required or bundled: this client does not use geographic routing rules. No proprietary server profiles or private keys are included in the package. CI-only fixture credentials are not production credentials.
