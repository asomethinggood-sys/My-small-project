from pathlib import Path
import xml.etree.ElementTree as ET

def annotation(title,text):
    print('::error title='+title+'::'+text[-3500:].replace('%','%25').replace('\n','%0A').replace('\r','%0D'))
for p in Path('android/app/build').rglob('*.xml'):
    if 'test-results' not in str(p) and 'lint-results' not in p.name: continue
    try:
        root=ET.parse(p).getroot()
        for fail in root.iter('failure'): annotation(p.name,''.join(fail.itertext()))
        for issue in root.iter('issue'):
            if issue.get('severity') in ('Error','Fatal'):annotation('Lint '+issue.get('id',''),issue.get('message',''))
    except ET.ParseError:pass
p=Path('android/build-log.txt')
if p.exists() and 'BUILD FAILED' in p.read_text():annotation('Gradle build',p.read_text())
for name in ['android/emulator-boot.log','android/release/INSTALLATION.txt','android/release/RELEASE-LAUNCH.txt']:
    p=Path(name)
    if p.exists():annotation(p.name,p.read_text(errors='replace'))
