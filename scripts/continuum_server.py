"""Validated normal-Continuum WS origin; no provider pools or geography claims."""
import argparse
import json
from pathlib import Path
import re
import uuid


def configuration(identity, path, port=18888):
    identity = str(uuid.UUID(identity))
    if not re.fullmatch(r'/[a-zA-Z0-9_-]{1,128}', path):
        raise ValueError('Invalid WebSocket path')
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('Invalid loopback port')
    return {
        'log': {'loglevel': 'warning'},
        # Cache remote hostname lookups and avoid unusable runner IPv6 paths.
        # This is server-side DNS, not client-side DNS bypass.
        # Xray's `localhost` resolver bypasses its cache. Use independent
        # IP-literal DoH transports here instead. +local is server-only: it
        # resolves directly at the exit, never recursively through freedom.
        'dns': {'servers': [
                    {'address': 'https+local://1.1.1.1/dns-query', 'timeoutMs': 3000},
                    {'address': 'https+local://8.8.8.8/dns-query', 'timeoutMs': 3000}],
                'queryStrategy': 'UseIPv4', 'enableParallelQuery': True,
                'disableCache': False, 'serveStale': False},
        'inbounds': [{'listen': '127.0.0.1', 'port': port, 'protocol': 'vless',
                      'settings': {'clients': [{'id': identity}], 'decryption': 'none'},
                      'streamSettings': {'network': 'ws', 'wsSettings': {'path': path}}}],
        'outbounds': [{'tag': 'internet', 'protocol': 'freedom',
                       'settings': {'targetStrategy': 'UseIPv4'},
                       'streamSettings': {'sockopt': {'tcpKeepAliveIdle': 60, 'tcpKeepAliveInterval': 30}}}]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uuid', required=True)
    parser.add_argument('--path', required=True)
    parser.add_argument('--port', type=int, default=18888)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    config = configuration(args.uuid, args.path, args.port)
    output = Path(args.output)
    output.touch(mode=0o600, exist_ok=True)
    output.chmod(0o600)
    output.write_text(json.dumps(config, indent=2) + '\n')


if __name__ == '__main__':
    main()
