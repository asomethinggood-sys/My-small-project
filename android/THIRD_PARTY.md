# Source and licensing

The original Continuum app source in this directory is distributed under GPL-3.0
(see LICENSE). The app is not a rebranded v2rayNG build; it uses a separately
packaged Xray engine and Android's VpnService/TUN facilities.

Native engine: 2dust/AndroidLibXrayLite, tag **v26.10.31**, LGPL-3.0.
- Source: https://github.com/2dust/AndroidLibXrayLite/tree/v26.10.31
- Exact binary: https://github.com/2dust/AndroidLibXrayLite/releases/tag/v26.10.31
- Build instructions: upstream README and workflows at that tag.
- License: LICENSE.libv2ray; preserve these notices when redistributing.
- Its Go dependency versions and source locations are specified in that tag's
  go.mod/go.sum, including XTLS/Xray-core (MPL-2.0) and its dependencies.
  Xray source/license: https://github.com/XTLS/Xray-core

The AAR is unmodified and checked by SHA-256 before building. The accompanying
Java binding sources JAR is included in the APK download artifact; it is **not**
the complete Go source. Complete native source and build instructions are at the
pinned upstream tag above. Rebuild/replace `app/libs/libv2ray.aar` and rebuild the
open app to relink a modified library. No anti-tampering restriction is imposed.
For downstream binary distribution, preserve/provide complete corresponding
source and dependencies as required by their licenses, not just the Java JAR.

Build tools: Android Gradle Plugin/SDK, Gradle, desugar_jdk_libs. Test-only:
JUnit 4.13.2, org.json 20240303. No ads, analytics, tracking SDK or proprietary
VPN engine is embedded. Source acknowledgements: v2rayNG and AndroidLibXrayLite
provide upstream API examples for Android core initialization and TUN handling.
