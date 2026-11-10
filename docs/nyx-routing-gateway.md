# Country-routing gateway and installation audit

## Release status

The user reported that Nyx preview 21 is rejected as an invalid package. **That installation issue is not resolved.** Do not describe the previous CI build as proof that this exact ARM64 package installs on the user's phone.

Automatic preview releases have been disabled, including the former `[publish-nyx]` marker path. No replacement APK has been published during this investigation. The newer universal candidate passed Android 8/10/15/16 and actual 16 KB emulator installation/startup checks; see [the exact compatibility evidence](nyx-android-compatibility.md). This does not establish the cause of the earlier physical-phone rejection.

### Exact artifact audit

The audit downloads the actual release asset, not a locally rebuilt debug variant. Its expected SHA-256 is `01b94c200b371e6763dd3b9a3100f6770708f6b71dccc4b7304678eae5954895`.

Run [42668592456](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42668592456), with detailed results recovered in [42669309251](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42669309251), establishes:

- Published bytes match the expected hash.
- ZIP CRCs, ARM64 ELF headers, signature verification and ZIP alignment passed.
- Manifest package is `app.nyx.vpn`, minimum API 26, target API 35, ARM64 only.
- Android 15/API 35's package manager installed those exact bytes with an ARM64 ABI override on an x86 emulator. **This is not native ARM execution.**
- Android 8/API 26 rejected that ABI override (`ABI arm64-v8a not supported on this device`) before the installation attempt. This was a harness limitation, not evidence of an invalid APK. Follow-up run [42670011233](https://github.com/asomethinggood-sys/My-small-project/actions/runs/42670011233) then performed normal installation: the x86 emulator reached native library extraction and returned `INSTALL_FAILED_NO_MATCHING_ABIS`. This is explicitly **not** successful ARM-device installation. The API35 exact-package install succeeded again.

The phone model is POCO X7 Pro; the Android/HyperOS version and detailed installer error are still needed to reproduce the user's failure. Do not blame a corrupted download, a signature conflict or ABI incompatibility without that evidence. The earlier 0.4 success does not diagnose this failure.

## Implemented routing path

`scripts/egress_gateway.py` now supplies a real private HTTP/WebSocket gateway, not merely a session model:

1. A trusted TLS frontend forwards requests to its loopback listener.
2. `POST /v1/sessions` requires the provisioned bearer credential and matching `X-Nyx-User` identity. It accepts only an explicit country and boolean UDP requirement.
3. The controller selects a fresh, approved pool and installs a bounded per-lease local transport.
4. The response contains a TLS VLESS/WebSocket profile with an unguessable session path and generation, plus a short expiry.
5. A WebSocket request to that path checks the lease/generation again and rewrites only to the provisioned pool's fixed private path. Existing VLESS identity checks still apply inside the pool.
6. `POST /v1/disconnect` verifies ownership and closes the lease's existing transport sockets.
7. A separately configured default WebSocket route is independent of country lease failure/revocation. No host default route is replaced.

The listener is loopback-only and caps request workers. API bodies and headers are bounded; duplicate JSON fields, ambiguous body framing, incorrect credential ownership and unavailable countries are rejected. API credentials are not forwarded to pools. Access logs are disabled so session tokens do not enter request logs. This component still needs a hardened deployment frontend with TLS, ingress abuse controls, and credential provisioning; it must never be exposed as a plaintext public API.

## What passed

- **106 Python tests**, including seven new real-HTTP/socket gateway tests.
- Real issuance of an expiring TLS profile and owner-authorized disconnect.
- Wrong credentials, wrong owner, unavailable country, string-valued UDP flags, extra fields, duplicate JSON keys, chunked requests and unknown session paths rejected.
- An existing default WebSocket connection stays usable after a country connection is revoked.
- The kernel integration in **42669309251** exercises `HTTP session API → issued profile → WebSocket gateway → lease transport → Xray → WireGuard → local TCP/UDP fixtures`, followed by API disconnect and failed traffic. The test substitutes loopback/no-TLS only inside its isolated fixture; production profile generation requires TLS. Geography is synthetic and is not public German exit evidence.

## Still required before calling the project finished

- An approved, provisioned real upstream pool and its sustained health supervisor.
- Trusted TLS deployment and app credential/session provisioning.
- Production wiring of the tested Android country selection, bounded lease renewal and fail-closed routing. The authenticated synthetic TLS integration now passes; that is not live provider deployment.
- A real country selection from the phone with independent geography and UDP evidence, without disturbing a second user's/default connection.
- Reproduction and resolution of the reported APK installation failure on the relevant Android/device configuration.

The historical DE220 comparison remains bounded provider evidence, not a running public country service. Provider restrictions and hosted-runner limits have not been waived. No production route, main branch or working shared connection was changed.
