"""Validate/apply Android sources only. NEVER installs or starts workflows."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def plan():
    expected = json.loads((HERE / 'overlay-base.json').read_text())
    files = []
    for source in sorted((HERE / 'overlay').rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(HERE / 'overlay')
        if relative.parts[0] != 'android' or '..' in relative.parts:
            raise ValueError('Only Android overlay paths are allowed')
        target = ROOT / relative
        if target.exists():
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            if target.read_bytes() != source.read_bytes() and expected.get(relative.as_posix()) != digest:
                raise ValueError(f'Base changed: {relative}. Rebase the staged patch; do not overwrite.')
        elif relative.as_posix() in expected:
            raise ValueError(f'Base file missing: {relative}')
        files.append((source, target))
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Explicitly overwrite only validated Android overlay paths')
    args = parser.parse_args()
    files = plan()  # Validate every path before writing any path.
    if args.apply:
        for source, target in files:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    print(f'{len(files)} Android files ' + ('applied. No workflow files touched.' if args.apply else 'validated; no files changed. Use --apply to install the overlay.'))
