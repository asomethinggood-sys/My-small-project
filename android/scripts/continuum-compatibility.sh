#!/usr/bin/env bash
set -euo pipefail
SDK="${ANDROID_HOME:?}"
export PATH="$SDK/platform-tools:$PATH"
API="${AUDIT_API:-35}"; ARCH="${AUDIT_ARCH:-x86_64}"; IMAGE="${AUDIT_IMAGE:-google_apis}"
DIR="$PWD/android/managed-compatibility"; mkdir -p "$DIR"
APK="$PWD/android/release/continuum-0.7.0-universal.apk"
(cd android; grep 'continuum-0.7.0-universal.apk$' release/SHA256SUMS | sha256sum -c -)
export ANDROID_USER_HOME="$RUNNER_TEMP/continuum-compat"
export ANDROID_AVD_HOME="$ANDROID_USER_HOME/avd"; mkdir -p "$ANDROID_AVD_HOME"
PACKAGE="system-images;android-$API;$IMAGE;$ARCH"
"$SDK/cmdline-tools/latest/bin/sdkmanager" 'platform-tools' 'emulator' "$PACKAGE"
printf 'no\n' | "$SDK/cmdline-tools/latest/bin/avdmanager" create avd --force --name continuum --package "$PACKAGE" --path "$ANDROID_AVD_HOME/continuum.avd"
printf 'avd.ini.encoding=UTF-8\npath=%s\ntarget=android-%s\n' "$ANDROID_AVD_HOME/continuum.avd" "$API" > "$ANDROID_AVD_HOME/continuum.ini"
"$SDK/emulator/emulator" -avd continuum -no-window -gpu swiftshader_indirect -noaudio -no-boot-anim -no-snapshot -memory 2048 -cores 2 > "$DIR/emulator.log" 2>&1 &
pid=$!; trap 'kill "$pid" 2>/dev/null || true' EXIT
timeout 180 adb wait-for-device
booted=false
for attempt in $(seq 1 90); do
  if [[ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == 1 ]]; then booted=true; break; fi
  kill -0 "$pid" || exit 1
  sleep 3
done
[[ "$booted" == true ]]
adb shell input keyevent 82
adb shell am force-stop com.google.android.apps.nexuslauncher || true
adb install --no-streaming "$APK" > "$DIR/install.txt" 2>&1
adb install --no-streaming -r "$APK" > "$DIR/update.txt" 2>&1
adb shell am start -W -n app.continuum/app.continuum.ContinuumActivity > "$DIR/launch.txt" 2>&1
ready=false
for attempt in $(seq 1 15); do
  if adb shell uiautomator dump /sdcard/home.xml && adb pull /sdcard/home.xml "$DIR/home.xml" && python3 android/scripts/check-managed-ui.py "$DIR/home.xml"; then ready=true; break; fi
  sleep 2
done
[[ "$ready" == true ]]
python3 - "$DIR/home.xml" <<'PY'
import re,subprocess,sys,xml.etree.ElementTree as ET
nodes=[n for n in ET.parse(sys.argv[1]).iter('node') if n.get('text')=='Settings']
assert len(nodes)==1
x1,y1,x2,y2=map(int,re.findall(r'\d+',nodes[0].get('bounds')))
subprocess.run(['adb','shell','input','tap',str((x1+x2)//2),str((y1+y2)//2)],check=True)
PY
sleep 2
adb shell uiautomator dump /sdcard/settings.xml
adb pull /sdcard/settings.xml "$DIR/settings.xml"
python3 - "$DIR/settings.xml" <<'PY'
import sys,xml.etree.ElementTree as ET
nodes=list(ET.parse(sys.argv[1]).iter('node'))
text=' '.join(n.get('text','') for n in nodes).lower()
assert 'connection settings' in text
assert not any('EditText' in n.get('class','') for n in nodes)
for word in ['github','subscription','import','https://','xray','repository']:assert word not in text
PY
for screen in MainActivity LocationsActivity; do
  if adb shell am start -W -n "app.continuum/app.continuum.$screen" 2>&1 | grep -q 'Status: ok'; then echo 'Developer screen opened'; exit 1; fi
done
if [[ "$IMAGE" == google_apis_ps16k ]]; then
  [[ "$(adb shell getconf PAGE_SIZE | tr -d '\r\n')" == 16384 ]]
fi
adb shell pidof app.continuum
adb logcat -d -s AndroidRuntime > "$DIR/crashes.txt"
if grep -q 'FATAL EXCEPTION' "$DIR/crashes.txt"; then exit 1; fi
echo "::notice title=Continuum release UI audit::API $API/$ARCH/$IMAGE: install, same-signer update, home/settings, disabled developer screens passed."
