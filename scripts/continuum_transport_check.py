"""One short private origin/connector experiment, never a hosted service.

Same runner, UUID, origin and connector for baseline/WS early-data samples.
Only timing/status metadata is printed. No subscription or profile is published.
"""
import copy
import json
import re
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from scripts.continuum_server import configuration
from scripts.generate import generate

BIN = Path('.runtime/bin').resolve()


def main():
    children = []
    with tempfile.TemporaryDirectory(prefix='continuum-check-') as tmp:
        root = Path(tmp)
        def start(command, label):
            with (root / (label + '.log')).open('w') as log:
                child = subprocess.Popen(command, stdout=log, stderr=log)
            children.append(child)
            return child
        def stop(child):
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait()
        def request():
            result = subprocess.run(['curl', '--silent', '--show-error', '--noproxy', '',
                '--proxy', 'socks5h://127.0.0.1:10809', '--connect-timeout', '5', '--max-time', '12',
                '--output', '/dev/null', '--write-out', '%{json}', 'https://example.com/'],
                capture_output=True, text=True, timeout=15)
            try:
                data = json.loads(result.stdout)
                if result.returncode == 0 and data['http_code'] == 200 and data['size_download'] > 0:
                    return {'ttfb_ms': round(data['time_starttransfer'] * 1000),
                            'total_ms': round(data['time_total'] * 1000)}
            except (ValueError, KeyError):pass
            return None
        try:
            state = generate('seed.example.com', root / 'seed')
            origin_file = root / 'origin.json'
            origin_file.write_text(json.dumps(configuration(state['uuid'], state['path'])))
            origin_file.chmod(0o600)
            subprocess.run([str(BIN / 'xray'), 'run', '-test', '-config', str(origin_file)],
                           check=True, capture_output=True, timeout=10)
            origin = start([str(BIN / 'xray'), 'run', '-config', str(origin_file)], 'origin')
            tunnel = start([str(BIN / 'cloudflared'), 'tunnel', '--no-autoupdate', '--protocol', 'auto',
                            '--url', 'http://127.0.0.1:18888'], 'connector')
            deadline = time.monotonic() + 90
            host = None
            while time.monotonic() < deadline:
                if origin.poll() is not None or tunnel.poll() is not None:raise RuntimeError('component_exited')
                match = re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)', (root / 'connector.log').read_text())
                if match:host = match[1];break
                time.sleep(1)
            if not host:raise RuntimeError('connector_not_ready')
            client_dir = root / 'client'; client_dir.mkdir(mode=0o700)
            (client_dir / 'identity.json').write_text(json.dumps(state | {'host': host}))
            generate(host, client_dir)
            baseline = json.loads((client_dir / 'client-test.json').read_text())
            results = {'baseline': [], 'ws_early_data': []}
            # Interleave pairs to reduce order bias; not a Tehran benchmark.
            for trial in range(3):
                for mode in results:
                    config = copy.deepcopy(baseline)
                    if mode == 'ws_early_data':config['outbounds'][0]['streamSettings']['wsSettings']['path'] += '?ed=2048'
                    profile = root / 'candidate.json'; profile.write_text(json.dumps(config));profile.chmod(0o600)
                    client = start([str(BIN / 'xray'), 'run', '-config', str(profile)], 'candidate')
                    try:
                        time.sleep(.5)
                        sample = None
                        for attempt in range(6 if trial == 0 else 2):
                            if client.poll() is not None:break
                            sample = request()
                            if sample:break
                            time.sleep(1)
                        if not sample:raise RuntimeError('route_probe_failed')
                        results[mode].append(sample)
                    finally:stop(client)
            report = {mode: {'samples': rows, 'median_total_ms': statistics.median(r['total_ms'] for r in rows)} for mode, rows in results.items()}
            print('::notice title=Same-runner transport checks NOT client latency::' + json.dumps(report), flush=True)
        finally:
            for child in reversed(children):stop(child)


if __name__ == '__main__':
    try:main()
    except Exception as error:
        # Error text can contain runtime profile paths or transient hostnames.
        print('::error title=Bounded server check failed::' + type(error).__name__, flush=True)
        raise SystemExit(1)
