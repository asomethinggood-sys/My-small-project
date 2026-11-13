# Distribution notices (not an in-app screen)

Continuum's desktop UI, subscription validation, route configuration and connection lifecycle are now implemented in Rust using native Win32 controls. There is no .NET, WebView or browser runtime in this package. The packet/protocol engine is still upstream Go; this is not an all-Rust VPN stack.

Xray-core v26.10.31, commit a4a3dff5b20c2faae567b742c172c7b95e75c083, MPL-2.0. This distribution replaces main/distro/all/all.go with windows/native/engine-imports.go to omit unused protocol/transport registration. The matching corresponding-source release archive includes that change, upstream sources and build instructions. Source upstream: https://github.com/XTLS/Xray-core/tree/v26.10.31 . engine/LICENSE contains the license. Dependency versions and checksums are in go.mod/go.sum. Build: copy engine-imports.go to main/distro/all/all.go, then `CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o xray.exe ./main` using the Go version in go.mod.

Wintun is the unmodified, signed amd64 DLL from the checksum-verified upstream Xray Windows archive. engine/LICENSE-Wintun contains its license. https://www.wintun.net/

Rust library license texts and dependency inventory accompany this distribution in notices/. Rust standard library: MIT OR Apache-2.0, https://github.com/rust-lang/rust . The matching source archive includes Cargo.lock and the application source. Build with stable Rust for x86_64-pc-windows-msvc, then embed the administrator manifest with the Windows SDK mt.exe as documented in the workflow. Windows system libraries (including Schannel) are supplied by Windows, not downloaded on launch.

No geosite/geoip databases, private credentials, telemetry or advertising SDK are included. Mandatory license and source notices are retained in the distribution; removing implementation details from product UI is not secrecy against binary or network inspection.
