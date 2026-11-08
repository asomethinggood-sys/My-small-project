#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! gradle --no-daemon :app:connectedDebugAndroidTest > emulator-log.txt 2>&1; then
  cat emulator-log.txt
  python3 - <<'PY'
from pathlib import Path
files=list(Path('app/build/outputs/androidTest-results').rglob('*.xml'))
text='\n'.join(p.read_text() for p in files)[-10000:] or Path('emulator-log.txt').read_text()[-10000:]
print('::error title=Android device smoke diagnostics::'+text.replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
PY
  exit 1
fi
cat emulator-log.txt
adb pull /sdcard/Android/data/app.continuum/files/continuum-screen.png continuum-screen.png
