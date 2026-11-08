#!/usr/bin/env bash
# Runs only on a GitHub-hosted Linux runner with Android SDK + /dev/kvm.
set -euo pipefail
SDK="${ANDROID_HOME:?Android SDK required}"
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
