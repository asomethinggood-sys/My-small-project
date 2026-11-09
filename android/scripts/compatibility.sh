#!/usr/bin/env bash
# Install the exact four-ABI release normally; never bypass ABI checks.
set -euo pipefail
SDK="${ANDROID_HOME:?}"
API="${AUDIT_API:?}"
ARCH="${AUDIT_ARCH:?}"
IMAGE="${AUDIT_IMAGE:-google_apis}"
PACKAGE="system-images;android-$API;$IMAGE;$ARCH"
DIR="$PWD/android/compatibility"
APK="$PWD/android/release/nyx-0.6.0-universal.apk"
mkdir -p "$DIR"
export PATH="$SDK/platform-tools:$PATH"
(cd android; grep 'nyx-0.6.0-universal.apk$' release/SHA256SUMS | sha256sum -c -)
"$SDK/cmdline-tools/latest/bin/sdkmanager" 'build-tools;35.0.0' 'platform-tools' 'emulator' "$PACKAGE"
"$SDK/build-tools/35.0.0/apksigner" verify --verbose --min-sdk-version "$API" --max-sdk-version "$API" "$APK" > "$DIR/signatures.txt"
"$SDK/build-tools/35.0.0/aapt2" dump badging "$APK" > "$DIR/manifest.txt"
sha256sum "$APK" > "$DIR/sha256.txt"
export ANDROID_USER_HOME="$RUNNER_TEMP/nyx-compatibility"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
mkdir -p "$ANDROID_AVD_HOME"
printf 'no\n' | "$SDK/cmdline-tools/latest/bin/avdmanager" create avd --force --name nyx --package "$PACKAGE" --path "$ANDROID_AVD_HOME/nyx.avd"
printf 'avd.ini.encoding=UTF-8\npath=%s\ntarget=android-%s\n' "$ANDROID_AVD_HOME/nyx.avd" "$API" > "$ANDROID_AVD_HOME/nyx.ini"
"$SDK/emulator/emulator" -avd nyx -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -no-snapshot -memory 2048 -cores 2 > "$DIR/emulator.log" 2>&1 &
pid=$!
trap 'adb logcat -d -s AndroidRuntime > "$DIR/crashes.txt" 2>/dev/null || true; kill "$pid" 2>/dev/null || true' EXIT
timeout 180 adb wait-for-device
booted=false
for attempt in $(seq 1 60); do
  if ! kill -0 "$pid" 2>/dev/null; then tail -40 "$DIR/emulator.log"; exit 1; fi
  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]]; then booted=true; break; fi
  sleep 5
done
[[ "$booted" == true ]]
adb shell input keyevent 82
adb shell getprop ro.product.cpu.abilist > "$DIR/abis.txt"
adb shell getconf PAGE_SIZE > "$DIR/page-size.txt"
if [[ "$IMAGE" == google_apis_ps16k ]]; then
  [[ "$(tr -d '\r\n' < "$DIR/page-size.txt")" == 16384 ]]
fi
adb install --no-streaming "$APK" > "$DIR/install.txt" 2>&1
# Same certificate/package upgrade must work without uninstalling app data.
adb install --no-streaming -r "$APK" > "$DIR/update.txt" 2>&1
adb logcat -c
adb shell am start -W -n app.nyx.vpn/app.continuum.MainActivity > "$DIR/MainActivity.txt" 2>&1
sleep 3
adb shell pidof app.nyx.vpn >> "$DIR/MainActivity.txt"
if grep -E 'Error:|Exception|Status: timeout' "$DIR/MainActivity.txt"; then exit 1; fi
# Locations is deliberately not exported: exercise the real home-screen link.
adb shell uiautomator dump /sdcard/nyx-home.xml
adb pull /sdcard/nyx-home.xml "$DIR/home.xml"
python3 - "$DIR/home.xml" <<'PY'
import re, subprocess, sys, xml.etree.ElementTree as ET
nodes=[n for n in ET.parse(sys.argv[1]).iter('node') if n.get('text')=='Exit locations']
assert len(nodes)==1, 'Home country-list navigation missing'
x1,y1,x2,y2=map(int,re.findall(r'\d+',nodes[0].get('bounds')))
subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)],check=True)
PY
sleep 3
adb shell pidof app.nyx.vpn > "$DIR/LocationsActivity.txt"
adb shell dumpsys activity activities >> "$DIR/LocationsActivity.txt"
grep -E '(mResumedActivity|topResumedActivity).*app.continuum.LocationsActivity' "$DIR/LocationsActivity.txt"
adb shell dumpsys package app.nyx.vpn > "$DIR/package.txt"
adb logcat -d -s AndroidRuntime > "$DIR/crashes.txt"
if grep -q 'FATAL EXCEPTION' "$DIR/crashes.txt"; then exit 1; fi
echo "::notice title=Native compatibility::API $API / $ARCH: exact universal APK installed, same-signer reinstall passed, home and country list launched. Not ARM hardware or live VPN proof."
