#!/usr/bin/env python3
"""Local Psiphon OSSH -> SOCKS -> HTTP integration, no public Psiphon access.

A namespace with loopback only prevents all Internet traffic. Keys/server entries
are generated for this test and removed. This does not validate packet-tunnel UDP,
public network provisioning, country exits or production use of upstream RC tools.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
import uuid

HTTP = '''import socket
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('1.1.1.1',18080));s.listen(8)
print('ready',flush=True)
while True:
 c,a=s.accept();c.settimeout(2)
 try:
  c.recv(4096);c.sendall(b'HTTP/1.1 200 OK\\r\\nContent-Length: 17\\r\\nConnection: close\\r\\n\\r\\nnyx-psiphon-local')
 except OSError: pass
 c.close()
'''


def run(*argv, cwd=None):
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=20)
    if result.returncode:
        raise RuntimeError('Local Psiphon fixture operation failed')
    return result.stdout


def notice_types(path):
    types = set()
    if path.exists():
        with path.open(errors='replace') as stream:
            for line in stream.read(2 * 1024 * 1024).splitlines():
                try:
                    kind = json.loads(line).get('noticeType')
                except (ValueError, AttributeError):
                    continue
                if kind in {'Error', 'Info', 'Alert', 'Tunnels', 'ConnectingServer', 'ConnectedServer',
                            'ListeningSocksProxyPort', 'LocalProxyError', 'ActiveTunnel', 'Exiting'}:
                    types.add(kind)
    return sorted(types)


def connected(path):
    if not path.exists():
        return False
    with path.open(errors='replace') as stream:
        for line in stream.read(2 * 1024 * 1024).splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if (isinstance(value, dict) and value.get('noticeType') == 'Tunnels'
                    and isinstance(value.get('data'), dict) and value['data'].get('count') == 1):
                return True
    return False


def main():
    if os.geteuid() != 0 or len(sys.argv) != 3:
        raise SystemExit('Usage: sudo python3 tests/egress_psiphon_kernel.py CLIENT SERVER')
    client, server = [str(Path(path).resolve(strict=True)) for path in sys.argv[1:]]
    ns = 'nyxps-' + uuid.uuid4().hex[:8]
    processes, files = [], []
    created = False
    host_routes = run('ip', '-j', 'route', 'show', 'table', 'main')
    with tempfile.TemporaryDirectory(prefix='nyx-psiphon-fixture-') as temporary:
        directory = Path(temporary)
        notices = directory / 'notices.jsonl'
        stage = 'generate_configuration'
        try:
            run(server, '-ipaddress', '127.0.0.1', '-protocol', 'OSSH:19999', 'generate', cwd=directory)
            rules_file = directory / 'psiphond-traffic-rules.config'
            rules = json.loads(rules_file.read_text())
            # Public-looking destination exists only on this isolated loopback.
            # Preserve Psiphon's bogon guard rather than disabling it for the test.
            rules['DefaultRules']['AllowSubnets'] = ['1.1.1.1/32']
            rules['DefaultRules']['AllowTCPPorts'] = [18080]
            rules_file.write_text(json.dumps(rules))
            (directory / 'state').mkdir(mode=0o700)
            config = {
                'LocalHttpProxyPort': 18088, 'LocalSocksProxyPort': 10809,
                # Values from upstream's localhost example, not public-network entitlement.
                'PropagationChannelId': '24BCA4EE20BEB92C', 'SponsorId': '721AE60D76700F5A',
                'TargetServerEntry': (directory / 'server-entry.dat').read_text().strip(),
                'DisableRemoteServerListFetcher': True, 'DisableTactics': True,
                'TunnelPoolSize': 1, 'DataRootDirectory': str(directory / 'state'),
            }
            path = directory / 'client.json'
            path.touch(mode=0o600)
            path.write_text(json.dumps(config))
            stage = 'namespace_setup'
            run('ip', 'netns', 'add', ns)
            created = True
            run('ip', '-n', ns, 'link', 'set', 'lo', 'up')
            assert json.loads(run('ip', '-n', ns, '-j', 'route', 'show')) == []
            run('ip', '-n', ns, 'addr', 'add', '1.1.1.1/32', 'dev', 'lo')
            origin = subprocess.Popen(['ip', 'netns', 'exec', ns, sys.executable, '-u', '-c', HTTP],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append(origin)
            ready, _, _ = select.select([origin.stdout], [], [], 3)
            if not ready or origin.stdout.readline().strip() != 'ready':
                raise RuntimeError('Local HTTP fixture did not start')
            server_log = open(directory / 'server.log', 'w')
            files.append(server_log)
            processes.append(subprocess.Popen(['ip', 'netns', 'exec', ns, server, 'run'], cwd=directory,
                                              stdout=server_log, stderr=server_log,
                                              env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'}))
            output = open(directory / 'client.log', 'w')
            files.append(output)
            client_process = subprocess.Popen(['ip', 'netns', 'exec', ns, client, '-config', str(path),
                                               '-notices', str(notices)], cwd=directory, stdout=output, stderr=output,
                                              env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
            processes.append(client_process)
            stage = 'connect_local_tunnel'
            deadline = time.monotonic() + 35
            while time.monotonic() < deadline:
                if connected(notices):
                    break
                if client_process.poll() is not None or processes[1].poll() is not None:
                    raise RuntimeError('Local Psiphon process exited')
                time.sleep(0.2)
            else:
                raise RuntimeError('Local Psiphon tunnel timeout')
            stage = 'http_through_socks'
            response = run('ip', 'netns', 'exec', ns, 'curl', '--fail', '--silent', '--max-time', '8',
                           '--noproxy', '', '--proxy', 'socks5h://127.0.0.1:10809', 'http://1.1.1.1:18080/')
            assert response == 'nyx-psiphon-local'
            stage = 'wrong_server_key_rejection'
            entry_text = bytes.fromhex(config['TargetServerEntry']).decode()
            split = entry_text.index('{')
            entry = json.loads(entry_text[split:])
            host_key = bytearray(base64.b64decode(entry['sshHostKey'], validate=True))
            host_key[-1] ^= 1
            entry['sshHostKey'] = base64.b64encode(host_key).decode()
            bad_config = dict(config)
            bad_config['TargetServerEntry'] = (entry_text[:split] + json.dumps(entry)).encode().hex()
            bad_config.update(LocalSocksProxyPort=10810, LocalHttpProxyPort=18089,
                              DataRootDirectory=str(directory / 'bad-state'))
            (directory / 'bad-state').mkdir(mode=0o700)
            bad_path, bad_notices = directory / 'bad-client.json', directory / 'bad-notices.jsonl'
            bad_path.touch(mode=0o600)
            bad_path.write_text(json.dumps(bad_config))
            bad_process = subprocess.Popen(['ip', 'netns', 'exec', ns, client, '-config', str(bad_path),
                                            '-notices', str(bad_notices)], cwd=directory,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
            processes.append(bad_process)
            deadline = time.monotonic() + 5
            while 'ListeningSocksProxyPort' not in notice_types(bad_notices):
                if time.monotonic() >= deadline or bad_process.poll() is not None:
                    raise RuntimeError('Wrong-key test client did not start')
                time.sleep(0.1)
            denied = subprocess.run(['ip', 'netns', 'exec', ns, 'curl', '--fail', '--silent', '--max-time', '3',
                                     '--noproxy', '', '--proxy', 'socks5h://127.0.0.1:10810',
                                     'http://1.1.1.1:18080/'], capture_output=True, timeout=5)
            assert denied.returncode != 0 and not connected(bad_notices)
            response = run('ip', 'netns', 'exec', ns, 'curl', '--fail', '--silent', '--max-time', '8',
                           '--noproxy', '', '--proxy', 'socks5h://127.0.0.1:10809', 'http://1.1.1.1:18080/')
            assert response == 'nyx-psiphon-local'
        except Exception:
            print('::error title=Nyx local Psiphon fixture::stage=' + stage +
                  '; notice_types=' + ','.join(notice_types(notices)), file=sys.stderr)
            raise
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()
            for file in files:
                file.close()
            if created:
                run('ip', 'netns', 'del', ns)
    assert host_routes == run('ip', '-j', 'route', 'show', 'table', 'main')
    print(json.dumps({'kind': 'local_psiphon_fixture', 'transport': 'OSSH', 'tcp_http': True,
                      'public_network_contact': False, 'country_verified': False, 'udp_verified': False,
                      'wrong_server_key_denied': True, 'valid_client_unaffected': True,
                      'tools': 'pinned_upstream_release_candidates_not_production_release',
                      'client_sha256': hashlib.sha256(Path(client).read_bytes()).hexdigest(),
                      'server_sha256': hashlib.sha256(Path(server).read_bytes()).hexdigest(),
                      'host_main_routes_unchanged': True}))


if __name__ == '__main__':
    main()
