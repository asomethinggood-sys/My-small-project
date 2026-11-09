#!/usr/bin/env bash
# Install the exact four-ABI release normally; never bypass ABI checks.
set -euo pipefail
SDK="${ANDROID_HOME:?}"
API="${AUDIT_API:?}"
ARCH="${AUDIT_ARCH:?}"
DIR="$PWD/android/compatibility"
APK="$PWD/android/release/nyx-0.6.0-universal.apk"
mkdir -p "$DIR"
export PATH="$SDK/platform-tools:$PATH"
"$SDK/cmdline-tools/latest/bin/sdkmanager" 'build-tools;35.0.0' 'platform-tools' 'emulator' "system-images;android-$API;google_apis;$ARCH"
"$SDK/build-tools/35.0.0/apksigner" verify --verbose --min-sdk-version "$API" --max-sdk-version "$API" "$APK" > "$DIR/signatures.txt"
"$SDK/build-tools/35.0.0/aapt2" dump badging "$APK" > "$DIR/manifest.txt"
sha256sum "$APK" > "$DIR/sha256.txt"
export ANDROID_USER_HOME="$RUNNER_TEMP/nyx-compatibility"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
mkdir -p "$ANDROID_AVD_HOME"
printf 'no\n' | "$SDK/cmdline-tools/latest/bin/avdmanager" create avd --force --name nyx --package "system-images;android-$API;google_apis;$ARCH" --path "$ANDROID_AVD_HOME/nyx.avd"
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
adb install --no-streaming "$APK" > "$DIR/install.txt" 2>&1
# Same certificate/package upgrade must work without uninstalling app data.
adb install --no-streaming -r "$APK" > "$DIR/update.txt" 2>&1
adb logcat -c
for activity in MainActivity LocationsActivity; do
  adb shell am start -W -n "app.nyx.vpn/app.continuum.$activity" > "$DIR/$activity.txt" 2>&1
  sleep 3
  adb shell pidof app.nyx.vpn >> "$DIR/$activity.txt"
  if grep -E 'Error:|Exception|Status: timeout' "$DIR/$activity.txt"; then exit 1; fi
done
adb shell dumpsys package app.nyx.vpn > "$DIR/package.txt"
adb logcat -d -s AndroidRuntime > "$DIR/crashes.txt"
if grep -q 'FATAL EXCEPTION' "$DIR/crashes.txt"; then exit 1; fi
echo "::notice title=Native compatibility::API $API / $ARCH: exact universal APK installed, same-signer reinstall passed, home and country list launched. Not ARM hardware or live VPN proof."
