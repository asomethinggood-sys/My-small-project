#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
gradle --no-daemon -PtargetAbi=x86_64 :probe:installDebug
adb push "$RUNNER_TEMP/continuum-fixture/profiles.json" /sdcard/Download/continuum-fixtures.json
if ! gradle --no-daemon -PtargetAbi=x86_64 :app:connectedDebugAndroidTest > emulator-log.txt 2>&1; then
  cat emulator-log.txt
  adb logcat -d -s AndroidRuntime > device-crash.txt
  adb logcat -d -s ContinuumProbe:I '*:S' > network-report.txt
  python3 - <<'PY'
from pathlib import Path
import os
files=list(Path('app/build/outputs/androidTest-results').rglob('*.xml'))
text='\n'.join(p.read_text() for p in files)[-24000:] or Path('emulator-log.txt').read_text()[-18000:]
print('::error title=Android VPN regression tests::'+text.replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
for p in [Path('device-crash.txt'),Path('network-report.txt'),Path(os.environ['RUNNER_TEMP'])/'continuum-fixture/xray.log']:
    text=p.read_text(errors='replace')[-10000:]
    print('::warning title='+p.name+'::'+text.replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
PY
  exit 1
fi
cat emulator-log.txt
adb logcat -d -s ContinuumProbe:I '*:S' > network-report.txt
python3 - <<'PY'
from pathlib import Path
print('::notice title=Runner network checks (not Tehran or battery evidence)::'+Path('network-report.txt').read_text()[-16000:].replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
PY
adb pull /sdcard/Download/continuum-screen.png continuum-screen.png || true
adb pull /sdcard/Download/nyx-home.png release/nyx-home.png
adb pull /sdcard/Download/nyx-locations.png release/nyx-locations.png
