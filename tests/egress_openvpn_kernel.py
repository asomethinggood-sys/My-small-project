#!/usr/bin/env python3
"""Real local OpenVPN handshake, TUN migration and UDP/DNS; metadata is simulated.

No public provider contact. All endpoints and TLS keys are ephemeral local fixtures.
"""
import base64
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.egress_openvpn_probe import probe
from egress_kernel import DNS_SERVER


def run(*args, input=None, timeout=20):
    result = subprocess.run(args, input=input, text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        # Arguments in this fixture are paths and fixed test commands, never keys.
        raise RuntimeError('Local OpenVPN fixture command failed: ' + str(args[:3]))
    return result.stdout


def child():
    envelope = json.loads(sys.stdin.read())
    result = probe(envelope, metadata_fetcher=lambda _: {
        'ip': '8.8.4.4', 'country_iso': 'DE', 'country_code': 'DE', 'success': True})
    print(json.dumps(result))
    return 0 if (result.get('udp_dns_passed') and result.get('tunnel_drop_blocked')
                 and result.get('host_main_routes_unchanged')) else 1


def main():
    if os.geteuid() != 0:
        raise SystemExit('Root required')
    suffix = uuid.uuid4().hex[:8]
    control, peer = 'nyxoc-' + suffix, 'nyxoe-' + suffix
    created, processes = [], []
    baseline = run('ip', '-j', 'route', 'show', 'table', 'main')
    with tempfile.TemporaryDirectory(prefix='nyx-openvpn-fixture-') as temporary:
        directory = Path(temporary)
        try:
            ca, ca_key = directory / 'ca.pem', directory / 'ca.key'
            run('openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                '-subj', '/CN=Nyx-Local-Test-CA', '-keyout', str(ca_key), '-out', str(ca))
            certs = {}
            for role, usage in [('server', 'serverAuth'), ('client', 'clientAuth')]:
                key, csr, cert, extension = [directory / (role + ending) for ending in ['.key', '.csr', '.pem', '.ext']]
                run('openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=nyx-' + role,
                    '-keyout', str(key), '-out', str(csr))
                extension.write_text('basicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=' + usage + '\n')
                run('openssl', 'x509', '-req', '-in', str(csr), '-CA', str(ca), '-CAkey', str(ca_key),
                    '-CAcreateserial', '-days', '1', '-out', str(cert), '-extfile', str(extension))
                certs[role] = (cert, key)
            for ns in [control, peer]:
                run('ip', 'netns', 'add', ns)
                created.append(ns)
                run('ip', '-n', ns, 'link', 'set', 'lo', 'up')
            run('ip', '-n', control, 'link', 'add', 'outer', 'type', 'veth',
                'peer', 'name', 'outer', 'netns', peer)
            for ns, address in [(control, '10.201.0.1/30'), (peer, '10.201.0.2/30')]:
                run('ip', '-n', ns, 'addr', 'add', address, 'dev', 'outer')
                run('ip', '-n', ns, 'link', 'set', 'outer', 'up')
            for address in ['8.8.8.8/32', '1.1.1.1/32']:
                run('ip', '-n', peer, 'addr', 'add', address, 'dev', 'lo')
            run('ip', '-n', control, 'route', 'add', '8.8.8.8/32', 'via', '10.201.0.2')
            server_config = directory / 'server.conf'
            server_config.write_text(f'''local 8.8.8.8
port 53
proto udp
dev tunserver
dev-type tun
disable-dco
topology subnet
server 10.8.0.0 255.255.255.0
ca {ca}
cert {certs['server'][0]}
key {certs['server'][1]}
dh none
tls-version-min 1.2
data-ciphers AES-256-GCM:AES-128-GCM
auth SHA256
keepalive 5 30
verb 3
''')
            processes.append(subprocess.Popen(['ip', 'netns', 'exec', peer, 'openvpn', '--config', str(server_config)],
                                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            dns = subprocess.Popen(['ip', 'netns', 'exec', peer, sys.executable, '-u', '-c', DNS_SERVER,
                                    '1.1.1.1', '53', 'fixture'], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
            processes.append(dns)
            readable, _, _ = select.select([dns.stdout], [], [], 3)
            if not readable or dns.stdout.readline().strip() != 'ready':
                raise RuntimeError('DNS fixture failed to start')
            config = ('client\ndev tun\nproto udp\nremote 8.8.8.8 53\nauth-user-pass\n'
                      'auth SHA256\ndata-ciphers AES-256-GCM:AES-128-GCM\n')
            for tag, path in [('ca', ca), ('cert', certs['client'][0]), ('key', certs['client'][1])]:
                config += f'<{tag}>\n' + path.read_text() + f'</{tag}>\n'
            envelope = {'provider': 'vpnbook', 'username': 'vpnbook', 'password': 'test-only',
                        'profile_base64': base64.b64encode(config.encode()).decode()}
            result = subprocess.run(['nsenter', '--net=/var/run/netns/' + control, '--', sys.executable,
                                     str(Path(__file__).resolve()), '--child'], input=json.dumps(envelope),
                                    capture_output=True, text=True, timeout=100)
            outcome = json.loads(result.stdout)
            if result.returncode:
                # Result contains only allowlisted metadata, never config or keys.
                print(json.dumps({'local_fixture_failure': outcome}))
                raise RuntimeError('Local OpenVPN payload fixture failed')
        finally:
            for process in processes:
                process.terminate()
            for process in processes:
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
            for ns in reversed(created):
                run('ip', 'netns', 'del', ns)
    assert baseline == run('ip', '-j', 'route', 'show', 'table', 'main')
    print(json.dumps({'kind': 'local_openvpn_fixture', 'tls_handshake': True, 'tun_migration': True,
                      'udp_dns': True, 'drop_test': True, 'country_metadata': 'simulated_not_verified',
                      'public_provider_contact': False, 'host_main_routes_unchanged': True}))


if __name__ == '__main__':
    if sys.argv[1:] == ['--child']:
        raise SystemExit(child())
    main()
