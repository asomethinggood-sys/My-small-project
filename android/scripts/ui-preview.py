"""Small CI-only screenshot previews for review through the GitHub API.

Screenshots are from local emulator fixtures, never a user's device or credentials.
Full-resolution originals remain release assets. No app runtime dependency.
"""
import base64
import os
import re
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path
from PIL import Image

totals = {}
for label, directory in [('JVM', 'android/app/build/test-results/testDebugUnitTest'),
                         ('Android instrumentation', 'android/app/build/outputs/androidTest-results')]:
    count = 0
    for path in Path(directory).rglob('TEST-*.xml'):
        root = ET.parse(path).getroot()
        assert int(root.get('failures', 0)) == 0 and int(root.get('errors', 0)) == 0
        count += int(root.get('tests', 0))
    assert count > 0, 'Missing validation reports'
    totals[label] = count
rust = re.search(r'test result: ok[.] (\d+) passed', Path('android/build-log.txt').read_text())
assert rust is not None
totals['Rust'] = int(rust[1])
report = '\n'.join(f'{label}: {count} passed' for label, count in totals.items())
report += '\nSource: ' + os.environ['GITHUB_SHA'] + '\nRun: ' + os.environ['GITHUB_RUN_ID'] + '\n'
Path('android/release/VALIDATION.txt').write_text(report)
print('::notice title=Nyx validation totals::' + report.replace('\n', '%0A'))

for name in ('home', 'locations'):
    with Image.open(Path('android/release') / f'nyx-{name}.png') as image:
        image.thumbnail((320, 760))
        output = BytesIO()
        image.convert('RGB').save(output, 'WEBP', quality=65, method=6)
    encoded = base64.b64encode(output.getvalue()).decode()
    chunks = [encoded[i:i+3500] for i in range(0, len(encoded), 3500)]
    if len(chunks) > 5:
        raise ValueError('UI preview exceeds annotation budget')
    for index, chunk in enumerate(chunks):
        print(f'::notice title=Nyx UI {name} {index} of {len(chunks)}::{chunk}')
