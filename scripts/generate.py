#!/usr/bin/env python3
"""Generate direct-VPS server and client files; these are NOT deployment proof."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import uuid
from urllib.parse import urlencode, quote


def generate(host, directory):
    host = host.lower()
    if len(host) > 253 or not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?', host):
        raise ValueError('Use a public DNS hostname, not an IP, URL, wildcard or port')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_file = directory / 'identity.json'
    if state_file.exists():
        state = json.loads(state_file.read_text())
        if state['host'] != host:
            raise ValueError('Hostname changed; use a new output directory')
        uuid.UUID(state['uuid'])
        if not re.fullmatch(r'/[0-9a-f]{32}', state['path']):
            raise ValueError('Invalid saved WebSocket path')
    else:
        state = {'host': host, 'uuid': str(uuid.uuid4()), 'path': '/' + uuid.uuid4().hex}
    def save(name, content):
        path = directory / name
        path.write_text(content)
        path.chmod(0o600)
    save('identity.json', json.dumps(state, indent=2) + '\n')
    config = {
        'log': {'loglevel': 'warning'},
        'inbounds': [{'listen': '127.0.0.1', 'port': 18888, 'protocol': 'vless',
                      'settings': {'clients': [{'id': state['uuid']}], 'decryption': 'none'},
                      'streamSettings': {'network': 'ws', 'wsSettings': {'path': state['path']}}}],
        'outbounds': [{'protocol': 'freedom'}]}
    save('xray.json', json.dumps(config, indent=2) + '\n')
    save('Caddyfile', f'''{host} {{
    handle {state['path']} {{
        reverse_proxy 127.0.0.1:18888
    }}
    handle /healthz {{
        respond "ok" 200
    }}
    handle {{
        respond "Not found" 404
    }}
}}
''')
    params = urlencode({'encryption': 'none', 'security': 'tls', 'sni': host,
                        'type': 'ws', 'host': host, 'path': state['path']}, quote_via=quote)
    uri = f"vless://{state['uuid']}@{host}:443?{params}#Direct-VPS"
    save('candidate-uri.txt', uri + '\n')
    save('candidate-subscription.txt', base64.b64encode(uri.encode()).decode() + '\n')
    # Used only to verify a complete VLESS round trip before exporting the URI.
    client = {'inbounds': [{'listen': '127.0.0.1', 'port': 10809, 'protocol': 'socks',
                           'settings': {'auth': 'noauth', 'udp': False}}],
              'outbounds': [{'protocol': 'vless', 'settings': {'vnext': [{
                  'address': host, 'port': 443, 'users': [{'id': state['uuid'], 'encryption': 'none'}]}]},
                  'streamSettings': {'network': 'ws', 'security': 'tls',
                                     'tlsSettings': {'serverName': host, 'allowInsecure': False},
                                     'wsSettings': {'path': state['path'], 'headers': {'Host': host}}}}]}
    save('client-test.json', json.dumps(client, indent=2) + '\n')
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--output', default='.runtime')
    args = parser.parse_args()
    os.umask(0o077)
    generate(args.host, args.output)
    print('Candidate files generated. Deploy and run verify.sh before importing.')
