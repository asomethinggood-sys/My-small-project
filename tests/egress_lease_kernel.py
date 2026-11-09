#!/usr/bin/env python3
"""Invoked only inside the existing isolated Xray/WireGuard fixture namespace."""
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.egress_control import Controller, Denied
from scripts.egress_ingress import LocalIngressPlane
from scripts.egress_sessions import Sessions, Evidence
from egress_xray_fixture import UDP_PROBE, WAIT


def main():
    binary, template = sys.argv[1:]
    config = json.loads(Path(template).read_text())
    upstream = config['outbounds'][0]['settings']['vnext'][0]
    plane = LocalIngressPlane({'fixture': (upstream['address'], upstream['port'])})
    sessions = Sessions()
    sessions.register('fixture', 'DE', 'fixture', 'wireguard', True)
    # Synthetic geography is only an input to the controller, not an exit claim.
    sessions.mark_ready('fixture', Evidence('DE', True, True, True, True, True, time.monotonic()+60),
                        ticket=sessions.begin_probe('fixture'))
    key = secrets.token_urlsafe(32)
    controller = Controller(sessions, plane, {'fixture_user': key})
    process = None
    try:
        try:
            controller.connect('fixture_user', 'wrong-key', 'DE')
            raise AssertionError('Unauthenticated request accepted')
        except Denied:
            pass
        lease = controller.connect('fixture_user', key, 'DE')
        host, port = plane.endpoint(lease.token)
        upstream['address'], upstream['port'] = host, port
        config['inbounds'][0]['port'] = 10811
        with tempfile.TemporaryDirectory(prefix='nyx-lease-') as directory:
            path = Path(directory) / 'client.json'
            path.touch(mode=0o600)
            path.write_text(json.dumps(config))
            process = subprocess.Popen([binary, 'run', '-c', str(path)],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([sys.executable, '-c', WAIT, '127.0.0.1', '10811'], check=True, timeout=15)
            command = ['curl', '--fail', '--silent', '--max-time', '4', '--noproxy', '',
                       '--proxy', 'socks5h://127.0.0.1:10811', 'http://1.1.1.1:18082/']
            response = subprocess.run(command, capture_output=True, text=True, timeout=6, check=True)
            assert response.stdout == 'nyx-encrypted-path'
            udp = subprocess.run([sys.executable, '-c', UDP_PROBE.replace('10809', '10811')],
                                 capture_output=True, text=True, timeout=8, check=True)
            assert udp.stdout.strip() == 'udp-vless-wireguard-ok'
            controller.disconnect('fixture_user', key, lease.token)
            denied = subprocess.run(command, capture_output=True, timeout=6)
            assert denied.returncode != 0
            print('authenticated-lease-tcp-udp-and-revocation-passed; geography=synthetic-local-fixture')
    finally:
        controller.close()
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
