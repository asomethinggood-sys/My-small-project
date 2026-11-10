#!/usr/bin/env python3
"""Invoked only inside the existing isolated Xray/WireGuard fixture namespace."""
import json
import http.client
import threading
from urllib.parse import urlparse, parse_qs
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.egress_control import Controller, Denied
from scripts.egress_ingress import LocalIngressPlane
from scripts.egress_gateway import Gateway
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
    gateway = Gateway(controller, 'fixture.example', {'fixture': (upstream['users'][0]['id'],
                      config['outbounds'][0]['streamSettings']['wsSettings']['path'])})
    thread = threading.Thread(target=gateway.serve_forever, daemon=True)
    thread.start()
    def api(path, body):
        connection = http.client.HTTPConnection(*gateway.server_address, timeout=5)
        connection.request('POST', path, json.dumps(body), {'Content-Type': 'application/json',
                           'Authorization': 'Bearer '+key, 'X-Nyx-User': 'fixture_user'})
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result
    process = None
    try:
        try:
            controller.connect('fixture_user', 'wrong-key', 'DE')
            raise AssertionError('Unauthenticated request accepted')
        except Denied:
            pass
        status, issued = api('/v1/sessions', {'country': 'DE', 'require_udp': True})
        assert status == 201
        # Only this isolated test substitutes loopback/no-TLS for the public TLS
        # hostname in the issued profile. Production profiles always require TLS.
        parsed = urlparse(issued['profile'])
        params = parse_qs(parsed.query)
        assert params['security'] == ['tls']
        upstream['users'][0]['id'] = parsed.username
        upstream['address'], upstream['port'] = gateway.server_address
        config['outbounds'][0]['streamSettings']['wsSettings']['path'] = params['path'][0]
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
            status, _ = api('/v1/disconnect', {'token': issued['token']})
            assert status == 200
            denied = subprocess.run(command, capture_output=True, timeout=6)
            assert denied.returncode != 0
            print('authenticated-lease-tcp-udp-and-revocation-passed; geography=synthetic-local-fixture')
    finally:
        controller.close()
        gateway.shutdown()
        gateway.server_close()
        thread.join(2)
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == '__main__':
    main()
