#!/usr/bin/env python3
"""Readiness gate for legacy loop: a URL alone is not a functioning proxy."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
from generate import generate

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('host')
p.add_argument('uuid')
p.add_argument('path')
p.add_argument('xray')
args = p.parse_args()
with tempfile.TemporaryDirectory() as tmp:
    directory = Path(tmp)
    (directory / 'identity.json').write_text(json.dumps({'host': args.host, 'uuid': args.uuid, 'path': args.path}))
    generate(args.host, directory)
    with (directory / 'client.log').open('w') as log:
        client = subprocess.Popen([args.xray, 'run', '-c', str(directory / 'client-test.json')], stdout=log, stderr=log)
    try:
        for _ in range(12):
            time.sleep(2)
            if client.poll() is not None:
                raise SystemExit('Probe client exited; refusing to publish')
            result = subprocess.run(['curl', '--silent', '--show-error', '--noproxy', '',
                '--proxy', 'socks5h://127.0.0.1:10809', '--connect-timeout', '5', '--max-time', '15',
                '--output', '/dev/null', '--write-out', '%{http_code}', 'https://example.com/'],
                capture_output=True, text=True)
            if result.returncode == 0 and result.stdout == '200':
                print('TLS/WS/VLESS egress verified from runner; NOT a Tehran latency test')
                break
        else:
            raise SystemExit('No successful VLESS probe; refusing to publish')
    finally:
        client.terminate()
        try:
            client.wait(timeout=5)
        except subprocess.TimeoutExpired:
            client.kill()
            client.wait()
