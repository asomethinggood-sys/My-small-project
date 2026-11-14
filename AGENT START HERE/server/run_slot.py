"""Dormant beta worker. Runs only after an operator installs/enables workflows.
No schedules, tokens, profile credentials or real server addresses live here.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.continuum_server import configuration


def rotation_end(slot, now):
    # Per-run endpoint lifetime, NOT an experiment deadline. Every successor
    # computes a fresh lifetime, indefinitely while the operator switch is on.
    if not 1 <= slot <= 10:
        raise ValueError('Invalid slot')
    return now + (240 + slot * 6) * 60


def document(slot, generation, host, identity, path, now, end):
    if not 1 <= slot <= 10 or not re.fullmatch(r'[a-z0-9-]+\.trycloudflare\.com', host):
        raise ValueError('Invalid slot or public hostname')
    identity = str(uuid.UUID(identity))
    if not re.fullmatch(r'/[a-zA-Z0-9_-]{1,128}', path):
        raise ValueError('Invalid path')
    if not now < end <= now + 6 * 3600:
        raise ValueError('Invalid publication lifetime')
    query = urllib.parse.urlencode({'security': 'tls', 'type': 'ws', 'sni': host, 'host': host, 'path': path})
    return {'schema': 1, 'slot': slot, 'generation': str(generation), 'issued_at': now,
            'expires_at': end, 'country': 'US',
            'uri': f'vless://{identity}@{host}:443?{query}'}


def read_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Continuum-Beta-Readiness/1.0'}), timeout=10) as response:
        return json.loads(response.read(65537))


def verify_us():
    # Runner labels are NOT exit-geography proof. Both checks must agree.
    return read_json('https://api.country.is/').get('country') == 'US' and read_json('https://ipapi.co/json/').get('country_code') == 'US'


def gh(*args):
    return subprocess.run(['gh', *args], check=True, capture_output=True, text=True, timeout=45).stdout


def enabled():
    return gh('variable', 'get', 'ENABLE_CONTINUUM_BETA').strip() == 'true'


def main(slot):
    if os.environ.get('ENABLE_CONTINUUM_BETA') != 'true':
        raise ValueError('Beta is disabled')
    now = int(time.time())
    # Distinct lifetimes reduce synchronized ten-slot rotations.
    end = rotation_end(slot, now)
    ref = os.environ['WORKFLOW_REF']
    if not ref or ref.startswith('-'):
        raise ValueError('Invalid workflow ref')
    # Fail closed before publishing if this token cannot read the kill switch.
    if not enabled():
        raise ValueError('Beta kill switch is off')
    if not verify_us():
        raise ValueError('US geography not confirmed; slot will not be advertised')
    tag = f'continuum-beta-{slot:02d}'
    children = []
    published = False
    with tempfile.TemporaryDirectory(prefix=f'continuum-slot-{slot:02d}-') as tmp:
        root = Path(tmp)
        identity = str(uuid.uuid4()); path = '/' + uuid.uuid4().hex
        config = configuration(identity, path)
        config['policy'] = {'levels': {'0': {'connIdle': 600, 'uplinkOnly': 30, 'downlinkOnly': 30}}}
        origin = root / 'origin.json'; origin.write_text(json.dumps(config)); origin.chmod(0o600)
        binary = Path.home() / 'bin'
        def start(command, name):
            log = (root / name).open('w')
            try:
                child = subprocess.Popen(command, stdout=log, stderr=log)
            finally:
                log.close()
            children.append(child)
            return child
        def interrupt(*_):
            raise KeyboardInterrupt()
        signal.signal(signal.SIGTERM, interrupt)
        try:
            start([str(binary / 'xray'), 'run', '-c', str(origin)], 'origin.log')
            tunnel = start([str(binary / 'cloudflared'), 'tunnel', '--no-autoupdate', '--protocol', 'auto', '--url', 'http://127.0.0.1:18888'], 'connector.log')
            deadline = time.monotonic() + 180
            host = None
            while time.monotonic() < deadline:
                if any(p.poll() is not None for p in children):
                    raise RuntimeError('Startup process stopped')
                match = re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)', (root / 'connector.log').read_text())
                if match:
                    host = match[1]; break
                time.sleep(2)
            if not host:
                raise RuntimeError('No connector address')
            # Use the existing full VLESS+TLS+WS egress readiness gate, not just a TCP ping.
            subprocess.run([sys.executable, str(ROOT / 'scripts/check-tunnel.py'), host, identity, path, str(binary / 'xray'), '--attempts', '12'], check=True, capture_output=True, timeout=300)
            generation = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
            record = document(slot, generation, host, identity, path, int(time.time()), end)
            asset = root / 'slot.json'; asset.write_text(json.dumps(record)); asset.chmod(0o600)
            # One release per slot: no ten-writer aggregate manifest races.
            try:
                gh('release', 'view', tag)
            except subprocess.CalledProcessError:
                gh('release', 'create', tag, '--target', os.environ['GITHUB_SHA'], '--prerelease', '--title', f'Continuum beta slot {slot:02d}', '--notes', 'Ephemeral shared beta connection. Not a private credential store.')
            gh('release', 'upload', tag, str(asset), '--clobber')
            published = True
            print(f'Slot {slot:02d} passed readiness and published. No URI logged.', flush=True)
            while time.time() < end - 45:
                if any(p.poll() is not None for p in children):
                    raise RuntimeError('Serving process stopped')
                if not enabled():
                    raise RuntimeError('Operator disabled beta')
                # The workflow queued one successor before installation/startup.
                # It cannot serve until this slot releases its concurrency lock.
                # There is no experiment-wide calendar deadline.
                time.sleep(60)
        finally:
            if published:
                # Shorten the advertised lifetime on orderly stop. Crashes still
                # have the hard original expiry; clients must probe/fail over.
                try:
                    record['expires_at'] = int(time.time())
                    asset.write_text(json.dumps(record))
                    gh('release', 'upload', tag, str(asset), '--clobber')
                except Exception:
                    print('Could not retire slot asset; original expiry remains.', flush=True)
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        child.kill(); child.wait()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--slot', required=True, type=int, choices=range(1, 11))
    args = parser.parse_args()
    try:
        main(args.slot)
    except (Exception, KeyboardInterrupt) as error:
        # Exceptions from gh/curl/config can contain connection material: do not print them.
        print('Slot stopped: ' + type(error).__name__, file=sys.stderr)
        sys.exit(1)
