#!/usr/bin/env bash
# Exact ARM64 release installation audit. ABI override on x86 is explicitly not
# native ARM execution. No new release is built or published by this script.
set -euo pipefail
SDK="${ANDROID_HOME:?}"
API="${AUDIT_API:?}"
DIR="$PWD/.runtime/install-audit"
APK="$DIR/nyx-0.5.0-arm64.apk"
export PATH="$SDK/platform-tools:$PATH"
"$SDK/cmdline-tools/latest/bin/sdkmanager" 'build-tools;35.0.0' 'platform-tools' 'emulator' "system-images;android-$API;google_apis;x86_64"
"$SDK/build-tools/35.0.0/apksigner" verify --verbose --print-certs --min-sdk-version "$API" --max-sdk-version "$API" "$APK" > "$DIR/signature.txt"
"$SDK/build-tools/35.0.0/aapt2" dump badging "$APK" > "$DIR/manifest.txt"
"$SDK/build-tools/35.0.0/zipalign" -c -P 16 -v 4 "$APK" > "$DIR/alignment.txt"
python3 - <<'PY'
from pathlib import Path
import zipfile, struct
p=Path('.runtime/install-audit/nyx-0.5.0-arm64.apk')
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    libraries=[n for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')]
    assert libraries and all(n.startswith('lib/arm64-v8a/') for n in libraries)
    for name in libraries:
        data=z.read(name)
        assert data[:4]==b'\x7fELF' and data[4]==2 and struct.unpack_from('<H',data,18)[0]==183
print('::notice title=Exact APK integrity::Published SHA256 matches; ZIP CRC and all ARM64 ELF headers pass')
PY
export ANDROID_USER_HOME="$RUNNER_TEMP/nyx-audit"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
mkdir -p "$ANDROID_AVD_HOME"
printf 'no\n' | "$SDK/cmdline-tools/latest/bin/avdmanager" create avd --force --name nyxaudit --package "system-images;android-$API;google_apis;x86_64" --path "$ANDROID_AVD_HOME/nyxaudit.avd"
printf 'avd.ini.encoding=UTF-8\npath=%s\ntarget=android-%s\n' "$ANDROID_AVD_HOME/nyxaudit.avd" "$API" > "$ANDROID_AVD_HOME/nyxaudit.ini"
"$SDK/emulator/emulator" -avd nyxaudit -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -no-snapshot -memory 2048 -cores 2 > "$DIR/emulator.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true' EXIT
timeout 180 adb wait-for-device
booted=false
for attempt in $(seq 1 60); do
  if ! kill -0 "$pid" 2>/dev/null; then tail -40 "$DIR/emulator.log"; exit 1; fi
  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]]; then booted=true; break; fi
  sleep 5
done
[[ "$booted" == true ]]
adb shell getprop ro.product.cpu.abilist > "$DIR/device-abis.txt"
# Test package parsing, resources, certificates and native library extraction of
# the actual ARM64 artifact. Do not attempt execution on the x86 CPU.
set +e
adb install --no-streaming --abi arm64-v8a "$APK" > "$DIR/install.txt" 2>&1
result=$?
set -e
python3 - <<'PY'
from pathlib import Path
text=Path('.runtime/install-audit/install.txt').read_text()[-3000:]
print('::notice title=Exact ARM64 package installation (ABI override; not ARM execution)::'+text.replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
PY
if [[ "$result" != 0 ]]; then
  adb logcat -d -s PackageManager PackageInstaller installd > "$DIR/package-manager.txt"
  exit "$result"
fi
adb shell dumpsys package app.nyx.vpn > "$DIR/installed-package.txt"
grep -E 'versionCode=|versionName=|primaryCpuAbi=|pkgFlags=' "$DIR/installed-package.txt"
