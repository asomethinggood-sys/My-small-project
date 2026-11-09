"""One bounded private VPNBook OpenVPN experiment; never a shared proxy service.

Encrypted OpenVPN socket stays on the host. A host-opened TUN fd is moved to a
firewalled namespace after authentication. No host addresses/routes are assigned.
Input includes public provider credentials/config; output is allowlisted metadata.
"""
import base64
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import uuid

from scripts.egress_config import global_ip
from scripts.egress_firewall import legacy_rules
from scripts.egress_openvpn import sanitize


DNS_UDP_PROBE = '''import socket,struct
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(4)
q=struct.pack('!HHHHHH',1789,0x100,1,0,0,0)+bytes.fromhex('076578616d706c6503636f6d0000010001')
s.sendto(q,('1.1.1.1',53));data,peer=s.recvfrom(4096)
assert peer==('1.1.1.1',53) and data[:2]==q[:2] and len(data)>=12
flags,questions,answers=struct.unpack('!HHH',data[2:8])
assert flags&0x8000 and flags&15==0 and answers>0
print('dns-udp-ok')
'''


class ProbeError(Exception):
    pass


def run(*argv, input=None, timeout=10):
    try:
        result = subprocess.run(argv, input=input, capture_output=True, text=True, timeout=timeout,
                                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
    except (OSError, subprocess.TimeoutExpired):
        raise ProbeError('command_failed') from None
    if result.returncode:
        raise ProbeError('command_failed')
    return result.stdout


def prepare(envelope):
    if envelope.get('provider') != 'vpnbook' or envelope.get('username') != 'vpnbook':
        raise ValueError('Unsupported test provider')
    if not isinstance(envelope.get('password'), str) or not re.fullmatch('[A-Za-z0-9_-]{4,64}', envelope['password']):
        raise ValueError('Invalid public credential format')
    text = base64.b64decode(envelope['profile_base64'], validate=True).decode('utf-8-sig')
    if len(text.encode()) > 128 * 1024:
        raise ValueError('Configuration size rejected')
    remote = re.search(r'^[ \t]*remote[ \t]+([A-Za-z0-9.-]+)[ \t]+(\d+)[ \t]*$', text, re.M)
    if not remote:
        raise ValueError('Unsupported remote syntax')
    hostname = remote[1]
    if re.fullmatch(r'de(?:20|220)\.vpnbook\.com', hostname.lower()):
        addresses = sorted({str(global_ip(item[4][0])) for item in
                            socket.getaddrinfo(hostname, int(remote[2]), socket.AF_INET, socket.SOCK_DGRAM)})
        if not addresses:
            raise ValueError('No public endpoint')
        address = addresses[0]
    else:
        address = str(global_ip(hostname))
    text = text[:remote.start()] + f'remote {address} {remote[2]}' + text[remote.end():]
    parsed = sanitize(text)
    if parsed['transport'] != 'udp' or parsed['endpoint_port'] not in (53, 25000):
        raise ValueError('This bounded probe only accepts advertised UDP ports')
    return parsed


def connected_address(line):
    line = line.removeprefix('>STATE:')
    fields = line.strip().split(',')
    if len(fields) < 4 or fields[1:3] != ['CONNECTED', 'SUCCESS']:
        return None
    address = ipaddress.ip_address(fields[3])
    if (address.version != 4 or address.is_loopback or address.is_multicast
            or address.is_link_local or address.is_unspecified or address.is_reserved):
        raise ValueError('Unsafe tunnel-assigned address')
    return str(address)


def wait_connected(path, process, seconds=40):
    deadline = time.monotonic() + seconds
    while not path.exists():
        if process.poll() is not None or time.monotonic() >= deadline:
            raise ProbeError('connection_not_established')
        time.sleep(0.1)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as control:
        control.settimeout(1)
        control.connect(str(path))
        control.sendall(b'state on\nstate\n')
        buffer = b''
        while time.monotonic() < deadline and process.poll() is None:
            try:
                chunk = control.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break
            buffer += chunk
            if len(buffer) > 65536:
                raise ProbeError('management_response_rejected')
            while b'\n' in buffer:
                raw, buffer = buffer.split(b'\n', 1)
                address = connected_address(raw.decode('utf-8', errors='replace'))
                if address:
                    return address
    raise ProbeError('connection_not_established')


def classify_log(text):
    for marker, code in [('AUTH_FAILED', 'authentication_rejected'),
                         ('VERIFY ERROR', 'certificate_verification_failed'),
                         ('Options error', 'configuration_incompatible'),
                         ('TLS Error', 'tls_handshake_failed'),
                         ('Connection refused', 'endpoint_refused')]:
        if marker in text:
            return code
    return 'connection_not_established'


def probe(envelope):
    if os.geteuid() != 0:
        raise ValueError('Root required for isolated test')
    parsed = prepare(envelope)
    token = uuid.uuid4().hex[:8]
    ns, device = 'nyxo-' + token, 'tun' + token
    result = {'provider': 'vpnbook', 'advertised_country': 'DE', 'shared_service': False,
              'status': 'not_connected', 'country_verified': False, 'connection_tested': True}
    namespace_created, resolver_created, moved = False, False, False
    process = None
    resolver_dir = Path('/etc/netns') / ns
    baselines = [run('ip', '-j', family, 'route', 'show', 'table', 'main') for family in ['-4', '-6']]
    with tempfile.TemporaryDirectory(prefix='nyx-openvpn-probe-') as temporary:
        directory = Path(temporary)
        log = directory / 'openvpn.log'
        try:
            run('ip', 'netns', 'add', ns)
            namespace_created = True
            resolver_dir.parent.mkdir(exist_ok=True)
            resolver_dir.mkdir(mode=0o700)
            resolver_created = True
            resolver_file = resolver_dir / 'resolv.conf'
            resolver_file.touch(mode=0o600)
            resolver_file.write_text('nameserver 1.1.1.1\noptions timeout:2 attempts:1\n')
            run('ip', '-n', ns, 'link', 'set', 'lo', 'up')
            ipv4, ipv6 = legacy_rules('198.19.250.1')
            run('ip', 'netns', 'exec', ns, 'iptables-legacy-restore', input=ipv4)
            run('ip', 'netns', 'exec', ns, 'ip6tables-legacy-restore', input=ipv6)
            config, auth, management = directory / 'client.conf', directory / 'auth', directory / 'control'
            for path, content in [(config, parsed['config']),
                                  (auth, envelope['username'] + '\n' + envelope['password'] + '\n')]:
                path.touch(mode=0o600)
                path.write_text(content)
            command = ['openvpn', '--config', str(config), '--dev', device, '--dev-type', 'tun',
                       '--disable-dco', '--auth-user-pass', str(auth), '--management', str(management), 'unix',
                       '--log', str(log), '--connect-retry-max', '1', '--connect-timeout', '10',
                       '--auth-retry', 'none', '--remap-usr1', 'SIGTERM', '--allow-compression', 'no',
                       '--pull-filter', 'reject', 'comp-lzo', '--pull-filter', 'reject', 'compress']
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
            address = wait_connected(management, process)
            result['handshake_completed'] = True
            run('ip', 'link', 'set', device, 'netns', ns)
            moved = True
            run('ip', '-n', ns, 'link', 'set', device, 'name', 'nyx-vpn')
            run('ip', '-n', ns, 'addr', 'add', address + '/32', 'dev', 'nyx-vpn')
            run('ip', '-n', ns, 'link', 'set', 'nyx-vpn', 'up')
            run('ip', '-n', ns, 'route', 'add', 'default', 'dev', 'nyx-vpn')
            udp = run('ip', 'netns', 'exec', ns, 'python3', '-c', DNS_UDP_PROBE, timeout=6)
            if udp.strip() != 'dns-udp-ok':
                raise ProbeError('udp_probe_failed')
            result['udp_dns_passed'] = True
            results = []
            for url in ['https://api.ipify.org?format=json', 'https://ifconfig.co/json', 'https://ipwho.is/']:
                body = run('ip', 'netns', 'exec', ns, 'curl', '--fail', '--silent', '--show-error',
                           '--connect-timeout', '5', '--max-time', '10', '--max-filesize', '32768',
                           '--proto', '=https', '--noproxy', '*', url, timeout=12)
                if len(body) > 32768:
                    raise ProbeError('probe_response_rejected')
                results.append(json.loads(body))
            addresses = [str(global_ip(item.get('ip', ''))) for item in results]
            countries = [results[1].get('country_iso'), results[2].get('country_code')]
            agreement = len(set(addresses)) == 1 and countries == ['DE', 'DE'] and results[2].get('success') is True
            result.update(status='german_exit_observed' if agreement else 'exit_unverified_or_wrong_country',
                          country_verified=agreement, independent_ip_agreement=len(set(addresses)) == 1,
                          observed_countries=[c if isinstance(c, str) and re.fullmatch('[A-Z]{2}', c) else 'unknown' for c in countries],
                          https_and_dns_passed=True)
            process.terminate()
            process.wait(timeout=5)
            try:
                run('ip', 'netns', 'exec', ns, 'curl', '--fail', '--silent', '--max-time', '2',
                    '--noproxy', '*', 'https://api.ipify.org?format=json', timeout=4)
                result['tunnel_drop_blocked'] = False
                result['country_verified'] = False
                result['status'] = 'leak_test_failed'
            except ProbeError:
                result['tunnel_drop_blocked'] = True
        except (ProbeError, ValueError, OSError, subprocess.TimeoutExpired):
            diagnostic = ''
            if log.exists():
                with log.open(errors='replace') as stream:
                    diagnostic = stream.read(65536)
            result['status'] = ('post_handshake_probe_failed' if result.get('handshake_completed') else
                                classify_log(diagnostic))
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            # Closing the OpenVPN TUN fd normally destroys its nonpersistent link.
            if namespace_created:
                run('ip', 'netns', 'del', ns)
            if resolver_created:
                (resolver_dir / 'resolv.conf').unlink(missing_ok=True)
                resolver_dir.rmdir()
    result['host_main_routes_unchanged'] = baselines == [run('ip', '-j', family, 'route', 'show', 'table', 'main') for family in ['-4', '-6']]
    if not result['host_main_routes_unchanged']:
        result.update(status='host_route_change_detected', country_verified=False)
    return result


def main():
    import sys
    import signal
    def deadline(*_):
        raise ProbeError('test_deadline_reached')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(90)
    try:
        raw = sys.stdin.buffer.read(256 * 1024 + 1)
        if len(raw) > 256 * 1024:
            raise ValueError('Input exceeds size budget')
        result = probe(json.loads(raw))
    except (ValueError, OSError, ProbeError):
        result = {'status': 'test_input_or_cleanup_failed', 'country_verified': False}
    signal.alarm(0)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
