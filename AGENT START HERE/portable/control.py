"""Portable workflow control. Runs only when an operator starts a workflow.
Uses the destination repository's GITHUB_TOKEN; no PAT, variable setup or source
repository write access. No connection credentials are printed.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

TAG = 'continuum-beta-control'
ASSET = 'control.json'


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True, timeout=60).stdout


def read():
    try:
        value = json.loads(gh('release', 'download', TAG, '--pattern', ASSET, '--output', '-'))
        if value.get('schema') != 1 or not isinstance(value.get('enabled'), bool):
            raise ValueError('Invalid control state')
        return value
    except subprocess.CalledProcessError:
        return {'schema': 1, 'enabled': False, 'phase': 'absent', 'generation': ''}


def enabled():
    value = read()
    return value['enabled'] and value.get('phase') == 'active'


def write(value):
    try:
        gh('release', 'view', TAG)
    except subprocess.CalledProcessError:
        gh('release', 'create', TAG, '--target', os.environ['GITHUB_SHA'], '--prerelease', '--title', 'Continuum beta control', '--notes', 'Operator-controlled state; contains no access credentials.')
    with tempfile.TemporaryDirectory() as directory:
        file = Path(directory) / ASSET
        file.write_text(json.dumps(value))
        gh('release', 'upload', TAG, str(file), '--clobber')


def preflight():
    repository = os.environ['GITHUB_REPOSITORY']
    data = json.loads(gh('api', 'repos/' + repository))
    if data['private']:
        raise ValueError('A public destination repository is required for unauthenticated Android discovery')
    ref = os.environ['WORKFLOW_REF']
    if ref != data['default_branch']:
        raise ValueError('Run on the destination default branch so successors can be dispatched')
    for slot in range(1, 11):
        gh('api', f'repos/{repository}/actions/workflows/continuum-beta-{slot:02d}.yml')


def main(command):
    generation = os.environ.get('CONTROL_GENERATION', '')
    if command == 'check':
        if not enabled():
            raise ValueError('Beta is stopped')
        return
    if command == 'begin':
        preflight()
        if read()['enabled']:
            raise ValueError('Already running; use Stop beta before starting again')
        if not generation:
            raise ValueError('Missing start generation')
        write({'schema': 1, 'enabled': False, 'phase': 'building', 'generation': generation})
        print('App build reserved. Servers remain stopped.')
    elif command == 'activate':
        value = read()
        if value.get('generation') != generation or value.get('phase') != 'building':
            raise ValueError('Start superseded or explicitly stopped during app build')
        value.update(enabled=True, phase='active')
        write(value)
        try:
            for slot in range(1, 11):
                current = read()
                if not current['enabled'] or current.get('generation') != generation:
                    raise ValueError('Activation interrupted by stop')
                gh('workflow', 'run', f'continuum-beta-{slot:02d}.yml', '--ref', os.environ['WORKFLOW_REF'])
                print(f'Slot {slot:02d} dispatched; readiness is checked by its worker.')
        except Exception:
            # Do not leave a partly dispatched pool advertised as enabled.
            # Worker entry/heartbeat checks observe this; Stop beta also cancels
            # any queued/running jobs if the control upload itself fails.
            current = read()
            if current.get('generation') == generation:
                current.update(enabled=False, phase='activation-failed')
                write(current)
            raise
    elif command == 'stop':
        write({'schema': 1, 'enabled': False, 'phase': 'stopped', 'generation': generation})
        failed = []
        for slot in range(1, 11):
            name = f'continuum-beta-{slot:02d}.yml'
            try:
                rows = json.loads(gh('run', 'list', '--workflow', name, '--limit', '100', '--json', 'databaseId,status'))
                for row in rows:
                    if row['status'] != 'completed':
                        try:
                            gh('run', 'cancel', str(row['databaseId']))
                        except subprocess.CalledProcessError:
                            failed.append(row['databaseId'])
            except subprocess.CalledProcessError:
                failed.append(name)
        if failed:
            print('Stop is published. Check these cancellation results:', failed)
            raise ValueError('Some cancellations require verification')
        print('Stop published; beta running/pending runs cancelled.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['begin', 'activate', 'stop', 'check'])
    args = parser.parse_args()
    try:
        main(args.command)
    except Exception as error:
        # These messages describe control state, not any slot URI/credentials.
        print(str(error) if isinstance(error, ValueError) else type(error).__name__)
        raise SystemExit(1)
