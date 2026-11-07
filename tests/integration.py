"""Loopback HTTP -> SOCKS -> VLESS/WS -> HTTP. TLS/ACME require real deployment."""
import functools
import http.server
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time


def wait_port(port, proc):
    for _ in range(100):
        if proc.poll() is not None:
            raise RuntimeError('Xray exited early')
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.1):
                return
        except OSError:
            time.sleep(.1)
    raise RuntimeError('Xray startup timed out')


root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as tmp:
    d = Path(tmp)
    (d / 'probe').write_text('roundtrip-ok')
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=tmp))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = json.loads((root / '.runtime/xray.json').read_text())
    origin['log'] = {'loglevel': 'debug'}
    (d / 'origin.json').write_text(json.dumps(origin))
    client = json.loads((root / '.runtime/client-test.json').read_text())
    client['log'] = {'loglevel': 'debug'}
    outbound = client['outbounds'][0]
    outbound['settings']['vnext'][0].update(address='127.0.0.1', port=18888)
    outbound['streamSettings']['security'] = 'none'
    del outbound['streamSettings']['tlsSettings']
    (d / 'client.json').write_text(json.dumps(client))
    processes = []
    try:
        for config, port in [(d / 'origin.json', 18888), (d / 'client.json', 10809)]:
            proc = subprocess.Popen([str(root / '.runtime/bin/xray'), 'run', '-c', str(config)])
            processes.append(proc)
            wait_port(port, proc)
        result = subprocess.check_output(['curl', '--fail', '--silent', '--show-error',
            '--max-time', '10', '--noproxy', '', '--proxy', 'socks5h://127.0.0.1:10809',
            f'http://127.0.0.1:{server.server_port}/probe'], text=True)
        assert result == 'roundtrip-ok', result
        print('Local VLESS/WS round trip passed. TLS/ACME and Tehran route NOT tested.')
    finally:
        for proc in processes:
            proc.terminate()
            proc.wait(timeout=5)
        server.shutdown()
