#!/usr/bin/env python3
"""Bounded, same-runner QUIC vs HTTP/2 experiment. No Tehran measurements."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

try:
    from .generate import generate
except ImportError:
    from generate import generate

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.runtime/experiment'
BIN = ROOT / '.runtime/bin'


def cloudflared_command(protocol, metrics_port):
    if protocol not in ('quic', 'http2', 'auto'):
        raise ValueError('Invalid tunnel transport')
    return [str(BIN / 'cloudflared'), 'tunnel', '--no-autoupdate', '--protocol', protocol,
            '--metrics', f'127.0.0.1:{metrics_port}', '--url', 'http://127.0.0.1:18888']


def launch(command, name):
    with (OUT / f'{name}.log').open('w') as log:
        proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    return proc


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def probe(proxy):
    result = subprocess.run(['curl', '--silent', '--show-error', '--noproxy', '',
        '--proxy', proxy, '--connect-timeout', '5', '--max-time', '15',
        '--output', '/dev/null', '--write-out', '%{http_code}', 'https://example.com/'],
        capture_output=True, text=True)
    return result.returncode == 0 and result.stdout == '200'


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    # Clear previous public results, never reuse stale verified URIs after failure.
    for path in OUT.glob('*.txt'):
        path.unlink()
    identity = generate('seed.example.com', OUT / 'origin')
    subprocess.run([str(BIN / 'xray'), 'run', '-test', '-c', str(OUT / 'origin/xray.json')], check=True)
    origin = launch([str(BIN / 'xray'), 'run', '-c', str(OUT / 'origin/xray.json')], 'origin')
    keep = [origin]
    ready = []
    results = {}
    try:
        tunnels = {mode: launch(cloudflared_command(mode, 20241 + i), mode)
                   for i, mode in enumerate(('quic', 'http2'))}
        keep.extend(tunnels.values())
        # Each candidate uses the same UUID, path, Xray origin and runner.
        for mode, tunnel in tunnels.items():
            client = None
            try:
                deadline = time.monotonic() + 120
                host = None
                while time.monotonic() < deadline:
                    if tunnel.poll() is not None or origin.poll() is not None:
                        raise RuntimeError('Origin or connector exited')
                    match = re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)',
                                      (OUT / f'{mode}.log').read_text())
                    if match:
                        host = match[1]
                        break
                    time.sleep(2)
                if host is None:
                    raise RuntimeError('No Quick Tunnel URL')
                directory = OUT / mode
                directory.mkdir(exist_ok=True)
                (directory / 'identity.json').write_text(json.dumps({**identity, 'host': host}))
                generate(host, directory)
                client = launch([str(BIN / 'xray'), 'run', '-c', str(directory / 'client-test.json')], f'{mode}-client')
                success = False
                for _ in range(12):
                    time.sleep(2)
                    if client.poll() is not None:
                        raise RuntimeError('Test client exited')
                    if probe('socks5h://127.0.0.1:10809'):
                        success = True
                        break
                if not success:
                    raise RuntimeError('VLESS/TLS/WS egress test did not return HTTP 200')
                uri = (directory / 'candidate-uri.txt').read_text().strip().replace('#Direct-VPS', f'#Experiment-{mode}')
                ready.append(uri)
                print(f'VERIFIED FROM RUNNER ONLY ({mode}): {uri}', flush=True)
                subprocess.run([sys.executable, str(ROOT / 'scripts/measure.py'),
                    '--label', f'GitHub-runner-NOT-Tehran-{mode}', '--url', 'https://example.com/',
                    '--proxy', 'socks5h://127.0.0.1:10809', '--count', '5',
                    '--output', str(OUT / f'{mode}-{time.time_ns()}.csv')], check=True)
                results[mode] = {'functional': True, 'host': host}
            except (RuntimeError, subprocess.CalledProcessError) as exc:
                results[mode] = {'functional': False, 'error': str(exc)}
                print(f'{mode}: {exc}', flush=True)
                stop(tunnel)
            finally:
                if client is not None:
                    stop(client)
        (OUT / 'results.json').write_text(json.dumps(results, indent=2))
        if not ready:
            raise RuntimeError('Neither candidate passed; no profiles exported')
        body = '\n'.join(ready) + '\n'
        (OUT / 'verified-uri.txt').write_text(body)
        (OUT / 'verified-subscription.txt').write_text(base64.b64encode(body.encode()).decode() + '\n')
        (OUT / 'pids.json').write_text(json.dumps([p.pid for p in keep if p.poll() is None]))
        summary = os.environ.get('GITHUB_STEP_SUMMARY')
        if summary:
            with open(summary, 'a') as f:
                f.write('## Bounded tunnel experiment\n\nFunctional checks from the GitHub runner ONLY. '
                        'No Tehran latency result. Profiles expire when this job ends.\n\n```\n' + body + '```\n')
    except BaseException:
        for proc in keep:
            stop(proc)
        raise


def serve(minutes):
    pids = json.loads((OUT / 'pids.json').read_text())
    try:
        deadline = time.monotonic() + minutes * 60
        while time.monotonic() < deadline:
            for pid in pids:
                os.kill(pid, 0)
            time.sleep(min(10, max(0, deadline - time.monotonic())))
    finally:
        for pid in pids:
            try:
                os.kill(pid, 15)
            except ProcessLookupError:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--serve-minutes', type=int, choices=range(31), default=0)
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        serve(args.serve_minutes)
