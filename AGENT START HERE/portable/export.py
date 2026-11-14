"""Create a ready-to-import destination tree. Never calls git/gh or starts jobs.
Only curated app/server source and predesigned manual workflows are exported.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
HANDOFF = HERE.parent
ROOT = HANDOFF.parent


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Source template changed; refusing ambiguous transformation: ' + old[:70])
    return text.replace(old, new, 1)


def put(root, relative, text):
    file = root / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text)


def export(destination):
    destination = destination.resolve()
    if destination.exists():
        raise ValueError('Destination must not exist; no existing repository will be overwritten')
    destination.mkdir(parents=True)
    ignored = shutil.ignore_patterns('.git', '.gradle', 'build', 'target', '__pycache__', 'release', 'libs', 'third-party', '*.log', '*.apk', '*.jks', '*.keystore', '*.key', '*.pem', 'local.properties')
    for name in ['android', 'scripts', 'config']:
        shutil.copytree(ROOT / name, destination / name, ignore=ignored)
    for file in (HANDOFF / 'overlay').rglob('*'):
        if file.is_file():
            target = destination / file.relative_to(HANDOFF / 'overlay')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, target)
    gradle = (destination / 'android/app/build.gradle').read_text()
    gradle = replace_once(gradle, "def managed =", "def betaRepository = providers.environmentVariable('GITHUB_REPOSITORY').getOrElse('')\nif (!(betaRepository ==~ /[A-Za-z0-9_.-]+\\/[A-Za-z0-9_.-]+/)) throw new GradleException('Invalid beta repository')\ndef managed =")
    gradle = replace_once(gradle, "        buildConfigField 'boolean', 'BETA_POOL', managed.toString()", "        buildConfigField 'boolean', 'BETA_POOL', managed.toString()\n        buildConfigField 'String', 'BETA_REPOSITORY', '\"' + betaRepository + '\"'")
    put(destination, 'android/app/build.gradle', gradle)
    catalog = (destination / 'android/app/src/main/java/app/continuum/BetaCatalog.java').read_text()
    catalog = replace_once(catalog, '"https://github.com/asomethinggood-sys/My-small-project/releases/download/continuum-beta-"', '"https://github.com/"+BuildConfig.BETA_REPOSITORY+"/releases/download/continuum-beta-"')
    put(destination, 'android/app/src/main/java/app/continuum/BetaCatalog.java', catalog)
    # Assert that the app actually uses the destination identity during CI tests.
    test = (destination / 'android/app/src/test/java/app/continuum/BetaCatalogTest.java').read_text()
    test = replace_once(test, '    @Test public void tenDistinctSourcesAndFixedLabels()', '    @Test public void destinationRepositoryIsEmbedded(){assertEquals("https://github.com/"+BuildConfig.BETA_REPOSITORY+"/releases/download/continuum-beta-01/slot.json",BetaCatalog.source(1));}\n    @Test public void tenDistinctSourcesAndFixedLabels()')
    put(destination, 'android/app/src/test/java/app/continuum/BetaCatalogTest.java', test)
    worker = (HANDOFF / 'server/run_slot.py').read_text()
    worker = replace_once(worker, 'parents[2]', 'parents[1]')
    worker = replace_once(worker, "    return gh('variable', 'get', 'ENABLE_CONTINUUM_BETA').strip() == 'true'", '    from portable.control import enabled as control_enabled\n    return control_enabled()')
    put(destination, 'server/run_slot.py', worker)
    put(destination, 'portable/control.py', (HERE / 'control.py').read_text())
    for slot in range(1, 11):
        filename = f'continuum-beta-{slot:02d}.yml'
        put(destination, '.github/workflows/' + filename, (HANDOFF / 'workflows' / filename).read_text())
    workflow = (HANDOFF / 'workflows/continuum-beta-slot.yml').read_text()
    workflow = replace_once(workflow, "    if: vars.ENABLE_CONTINUUM_BETA == 'true'\n", '')
    workflow = replace_once(workflow, '      - name: Queue one successor', '      - id: successor\n        name: Queue one successor')
    workflow = replace_once(workflow, '          [[ "$(gh variable get ENABLE_CONTINUUM_BETA)" == true ]]', '          python3 portable/control.py check')
    workflow = replace_once(workflow, '          ENABLE_CONTINUUM_BETA: ${{ vars.ENABLE_CONTINUUM_BETA }}', "          ENABLE_CONTINUUM_BETA: 'true'")
    workflow = replace_once(workflow, "python3 'AGENT START HERE/server/run_slot.py'", 'python3 server/run_slot.py')
    workflow = replace_once(workflow, '        if: failure()', "        if: failure() && steps.successor.outcome == 'success'")
    put(destination, '.github/workflows/continuum-beta-slot.yml', workflow)
    build = (ROOT / '.github/workflows/continuum-beta-build.yml').read_text()
    _, tail = build.split('permissions:\n', 1)
    build = 'name: Build destination Android APK\non:\n  workflow_call:\n  workflow_dispatch:\npermissions:\n' + tail
    build = replace_once(build, "      - name: Apply only reviewed Android overlay\n        run: python3 'AGENT START HERE/apply_overlay.py' --apply\n", '')
    # Run-specific tags avoid collisions between manual builds, starts and reruns.
    build = replace_once(build, 'continuum-android-1.0-beta-${GITHUB_RUN_NUMBER}', 'continuum-android-1.0-beta-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}')
    build = replace_once(build, 'No experiment deadline: server rotation continues while the operator switch remains enabled.', 'This APK reads this destination repository. Start beta dispatches servers only after this build succeeds; Stop beta disables them. There is no experiment deadline.')
    put(destination, '.github/workflows/continuum-beta-build.yml', build)
    put(destination, '.github/workflows/start-beta.yml', (HERE / 'start.yml').read_text())
    put(destination, '.github/workflows/stop-beta.yml', (HERE / 'stop.yml').read_text())
    put(destination, 'README.md', (HERE / 'DESTINATION-README.md').read_text())
    put(destination, '.gitignore', (ROOT / '.gitignore').read_text() + '\n.venv/\n')
    files = {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(destination.rglob('*')) if p.is_file()}
    put(destination, 'PORTABLE-MANIFEST.json', json.dumps({'schema': 1, 'files': files}, indent=2)+'\n')
    return len(files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='New directory, never an existing repository')
    parser.add_argument('--zip', type=Path, help='Alternatively create a ready-to-import ZIP')
    args = parser.parse_args()
    if bool(args.output) == bool(args.zip):
        parser.error('Choose exactly one of --output or --zip')
    if args.output:
        print(f'Exported {export(args.output)} source files; no git/gh/network actions performed.')
    else:
        if args.zip.exists():
            raise SystemExit('ZIP already exists; refusing overwrite')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'repository'
            count = export(root)
            args.zip.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(args.zip, 'w', zipfile.ZIP_DEFLATED) as archive:
                for file in sorted(root.rglob('*')):
                    if file.is_file():
                        archive.write(file, file.relative_to(root))
        print(f'Exported {count} files to {args.zip}; no git/gh/network actions performed.')
