#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
print('::notice title=Measured ARM64 APK::'+Path('release/APK-SIZE.txt').read_text().replace('\n','%0A'))
PY
gradle --no-daemon -PtargetAbi=x86_64 :probe:installDebug
adb push "$RUNNER_TEMP/continuum-fixture/profiles.json" /sdcard/Download/continuum-fixtures.json
if ! gradle --no-daemon -PtargetAbi=x86_64 :app:connectedDebugAndroidTest > emulator-log.txt 2>&1; then
  cat emulator-log.txt
  adb logcat -d -s AndroidRuntime > device-crash.txt
  python3 - <<'PY'
from pathlib import Path
import os
files=list(Path('app/build/outputs/androidTest-results').rglob('*.xml'))
text='\n'.join(p.read_text() for p in files)[-23000:] or Path('emulator-log.txt').read_text()[-18000:]
print('::error title=Android VPN regression tests::'+text.replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
for p in [Path('device-crash.txt'),Path(os.environ['RUNNER_TEMP'])/'continuum-fixture/xray.log']:
    text=p.read_text(errors='replace')[-6000:]
    print('::warning title='+p.name+'::'+text.replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
PY
  exit 1
fi
cat emulator-log.txt
adb pull /sdcard/Download/continuum-screen.png continuum-screen.png || true
