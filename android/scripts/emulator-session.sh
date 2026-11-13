#!/usr/bin/env bash
# Runs only on a GitHub-hosted Linux runner with Android SDK + /dev/kvm.
set -euo pipefail
SDK="${ANDROID_HOME:?Android SDK required}"
RELEASE_APP_ID="${RELEASE_APP_ID:-app.nyx.vpn}"
RELEASE_ACTIVITY="${RELEASE_ACTIVITY:-app.continuum.MainActivity}"
RELEASE_ARM64_APK="${RELEASE_ARM64_APK:-android/release/nyx-0.6.0-arm64.apk}"
export PATH="$SDK/platform-tools:$PATH"
export ANDROID_USER_HOME="${RUNNER_TEMP:-/tmp}/continuum-android"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"
mkdir -p "$ANDROID_AVD_HOME"
"$SDK/cmdline-tools/latest/bin/sdkmanager" 'platform-tools' 'emulator' 'system-images;android-35;google_apis;x86_64'
printf 'no\n' | "$SDK/cmdline-tools/latest/bin/avdmanager" create avd --force --name continuum --package 'system-images;android-35;google_apis;x86_64' --device pixel_6 --path "$ANDROID_AVD_HOME/continuum.avd"
test -f "$ANDROID_AVD_HOME/continuum.avd/config.ini"
# New command-line tools and the emulator can use different default user homes.
# Provide an explicit index alongside the AVD rather than relying on those defaults.
printf 'avd.ini.encoding=UTF-8\npath=%s\ntarget=android-35\n' "$ANDROID_AVD_HOME/continuum.avd" > "$ANDROID_AVD_HOME/continuum.ini"
"$SDK/emulator/emulator" -list-avds
"$SDK/emulator/emulator" -avd continuum -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -no-snapshot -camera-back none -memory 2048 -cores 2 > android/emulator-runtime.log 2>&1 &
emulator_pid=$!
trap 'kill "$emulator_pid" 2>/dev/null || true' EXIT
timeout 180 adb wait-for-device
booted=false
for attempt in $(seq 1 60); do
  if ! kill -0 "$emulator_pid" 2>/dev/null; then cat android/emulator-runtime.log; exit 1; fi
  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]]; then booted=true; break; fi
  sleep 5
done
if [[ "$booted" != true ]]; then cat android/emulator-runtime.log; echo 'Android boot timed out'; exit 1; fi
adb shell input keyevent 82
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0
bash android/scripts/device-smoke.sh
if [[ "$RELEASE_APP_ID" == app.continuum ]]; then
  adb pull /sdcard/Download/continuum-home.png android/release/continuum-home.png
  adb pull /sdcard/Download/continuum-settings.png android/release/continuum-settings.png
fi
# Validate the minified release variant too; debug instrumentation is not a
# substitute for testing the final packaging. All uninstall operations are on
# this disposable emulator, never on a user's device.
(
  cd android
  gradle --no-daemon -PtargetAbi=x86_64 :app:assembleRelease
)
# Gradle may already have uninstalled its instrumentation target.
if adb shell pm path "$RELEASE_APP_ID" | grep -q '^package:'; then adb uninstall "$RELEASE_APP_ID"; fi
adb install --no-streaming android/app/build/outputs/apk/release/app-release.apk
adb logcat -c
adb shell am start -W -n "$RELEASE_APP_ID/$RELEASE_ACTIVITY" > android/release/RELEASE-LAUNCH.txt 2>&1
sleep 3
if ! adb shell pidof "$RELEASE_APP_ID"; then
  adb logcat -d -s AndroidRuntime >> android/release/RELEASE-LAUNCH.txt
  cat android/release/RELEASE-LAUNCH.txt
  exit 1
fi
if [[ "$RELEASE_APP_ID" == app.continuum ]]; then
  adb shell uiautomator dump /sdcard/continuum-release.xml
  adb pull /sdcard/continuum-release.xml android/release/UI-RELEASE.xml
  python3 android/scripts/check-managed-ui.py android/release/UI-RELEASE.xml
  for screen in MainActivity LocationsActivity; do
    if adb shell am start -W -n "app.continuum/app.continuum.$screen" 2>&1 | grep -q 'Status: ok'; then
      echo 'Disabled developer screen unexpectedly opened'; exit 1
    fi
  done
fi
adb uninstall "$RELEASE_APP_ID"
adb install --no-streaming --abi arm64-v8a "$RELEASE_ARM64_APK" > android/release/INSTALLATION.txt 2>&1
cat android/release/INSTALLATION.txt
echo '::notice title=Release package acceptance::Minified x86_64 release installed and launched. Exact ARM64 candidate installed with ABI override; physical ARM execution remains unverified.'
