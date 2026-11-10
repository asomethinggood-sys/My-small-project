"""Bounded private VPNBook/VPNGate experiments; never a shared proxy service.

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
import signal
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
        if 'curl' in argv:
            code = {6: 'dns_failed', 7: 'connect_failed', 22: 'http_error', 28: 'timeout',
                    35: 'tls_handshake_failed', 60: 'certificate_verification_failed',
                    63: 'response_size_rejected'}.get(result.returncode, 'https_probe_failed')
            raise ProbeError(code)
        raise ProbeError('command_failed')
    return result.stdout


def prepare(envelope):
    if envelope.get('provider') == 'vpngate':
        if not re.fullmatch('[A-Z]{2}', str(envelope.get('country', ''))):
            raise ValueError('Explicit advertised country required')
        encoded = envelope.get('profile_base64', '')
        if not isinstance(encoded, str) or len(encoded) > 180000:
            raise ValueError('Configuration size rejected')
        parsed = sanitize(base64.b64decode(encoded, validate=True).decode('utf-8-sig'), aead_only=True)
        if parsed['endpoint_ip'] != str(global_ip(envelope.get('endpoint_ip', ''))):
            raise ValueError('Directory endpoint mismatch')
        if parsed['credentials_required']:
            raise ValueError('Certificate-only candidate required')
        return parsed
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
    expected_server = envelope.get('expected_server')
    expected_port = envelope.get('expected_port')
    if expected_server is not None:
        if expected_server not in ('de20', 'de220') or type(expected_port) is not int or expected_port not in (53, 25000):
            raise ValueError('Invalid expected candidate')
        if int(remote[2]) != expected_port:
            raise ValueError('Downloaded protocol port does not match selection')
        expected_host = expected_server + '.vpnbook.com'
        if hostname.lower() != expected_host:
            address = str(global_ip(hostname))
            expected_addresses = {str(global_ip(item[4][0])) for item in
                                  socket.getaddrinfo(expected_host, expected_port, socket.AF_INET, socket.SOCK_DGRAM)}
            if address not in expected_addresses:
                raise ValueError('Downloaded endpoint does not match selection')
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
    if expected_server is not None:
        parsed['candidate_id'] = f'vpnbook-{expected_server}-udp{expected_port}'
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


def assess_responses(results, expected_country='DE', *, require_conflict_source=False):
    if type(require_conflict_source) is not bool:
        raise ValueError('Explicit conflict-source policy required')
    if not re.fullmatch('[A-Z]{2}', expected_country):
        raise ValueError('Explicit expected country required')
    addresses = [str(global_ip(item['ip'])) for item in results.values()]
    countries = []
    for index, field in [(1, 'country_iso'), (2, 'country_code'), (3, 'country'), (4, 'country')]:
        item = results.get(index, {})
        code = item.get(field)
        if index == 2 and item.get('success') is not True:
            continue
        if isinstance(code, str) and re.fullmatch('[A-Z]{2}', code):
            countries.append(code)
    ip_agreement = len(addresses) >= 2 and len(set(addresses)) == 1
    conflict_checked = bool(re.fullmatch('[A-Z]{2}', str(results.get(4, {}).get('country', ''))))
    agreement = (ip_agreement and len(countries) >= 2 and set(countries) == {expected_country}
                 and (not require_conflict_source or conflict_checked))
    success = 'german_exit_observed' if expected_country == 'DE' else 'verified_exit_observed'
    return {'status': success if agreement else 'exit_unverified_or_wrong_country',
            'verified_country': expected_country if agreement else None,
            'conflict_source_checked': conflict_checked,
            'exit_ipv4': addresses[0] if ip_agreement else None,
            'country_verified': agreement, 'independent_ip_agreement': ip_agreement,
            'observed_countries': countries, 'https_and_dns_passed': bool(results)}


def probe(envelope, metadata_fetcher=None, *, private_trial=None):
    if os.geteuid() != 0:
        raise ValueError('Root required for isolated test')
    parsed = prepare(envelope)
    token = uuid.uuid4().hex[:8]
    ns, device = 'nyxo-' + token, 'tun' + token
    country = envelope.get('country', 'DE') if envelope['provider'] == 'vpngate' else 'DE'
    result = {'provider': envelope['provider'], 'advertised_country': country, 'shared_service': False,
              'candidate_id': parsed.get('candidate_id', 'local-fixture-or-unspecified'),
              'endpoint_port': parsed['endpoint_port'],
              'status': 'not_connected', 'country_verified': False, 'connection_tested': True}
    namespace_created, resolver_created, moved = False, False, False
    process = None
    paused = False
    stage = 'namespace_setup'
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
            files = [(config, parsed['config'])]
            auth_args = []
            if envelope['provider'] == 'vpnbook':
                files.append((auth, envelope['username'] + '\n' + envelope['password'] + '\n'))
                auth_args = ['--auth-user-pass', str(auth)]
            for path, content in files:
                path.touch(mode=0o600)
                path.write_text(content)
            command = ['openvpn', '--config', str(config), '--dev', device, '--dev-type', 'tun',
                       '--disable-dco', *auth_args, '--management', str(management), 'unix',
                       '--log', str(log), '--connect-retry-max', '1', '--connect-timeout', '10',
                       '--auth-retry', 'none', '--remap-usr1', 'SIGTERM', '--allow-compression', 'no',
                       '--pull-filter', 'reject', 'comp-lzo', '--pull-filter', 'reject', 'compress']
            stage = 'openvpn_start'
            process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
            stage = 'authenticate'
            address = wait_connected(management, process)
            result['handshake_completed'] = True
            # Quiesce the owned process during interface down/move/up so a TUN
            # read cannot observe the transient down state and trigger recovery.
            stage = 'move_tun'
            process.send_signal(signal.SIGSTOP)
            paused = True
            run('ip', 'link', 'set', device, 'netns', ns)
            moved = True
            stage = 'configure_tun'
            run('ip', '-n', ns, 'link', 'set', device, 'name', 'nyx-vpn')
            run('ip', '-n', ns, 'addr', 'add', address + '/32', 'dev', 'nyx-vpn')
            run('ip', '-n', ns, 'link', 'set', 'nyx-vpn', 'mtu', '1280', 'up')
            run('ip', '-n', ns, 'route', 'add', 'default', 'dev', 'nyx-vpn')
            process.send_signal(signal.SIGCONT)
            paused = False
            stage = 'udp_dns'
            udp = run('ip', 'netns', 'exec', ns, 'python3', '-c', DNS_UDP_PROBE, timeout=6)
            if udp.strip() != 'dns-udp-ok':
                raise ProbeError('udp_probe_failed')
            result['udp_dns_passed'] = True
            results = {}
            result['endpoint_probes'] = {}
            for index, url in enumerate(['https://api.ipify.org?format=json', 'https://ifconfig.co/json',
                                         'https://ipwho.is/', 'https://ipinfo.io/json', 'https://api.country.is/']):
                stage = ['https_ip_echo', 'https_geo_first', 'https_geo_second', 'https_geo_fallback', 'https_geo_conflict_check'][index]
                try:
                    if metadata_fetcher is not None:
                        # Injection is Python-only for isolated local fixtures.
                        body = metadata_fetcher(url)
                    else:
                        text = run('ip', 'netns', 'exec', ns, 'curl', '--ipv4', '--fail', '--silent', '--show-error',
                                   '--connect-timeout', '4', '--max-time', '8', '--max-filesize', '32768',
                                   '--proto', '=https', '--noproxy', '*', url, timeout=10)
                        if len(text) > 32768:
                            raise ProbeError('probe_response_rejected')
                        body = json.loads(text)
                    if not isinstance(body, dict) or not isinstance(body.get('ip'), str):
                        raise ValueError('Invalid response shape')
                    global_ip(body.get('ip', ''))
                    results[index] = body
                    result['endpoint_probes'][stage] = 'passed'
                except (ProbeError, ValueError) as error:
                    result['endpoint_probes'][stage] = str(error) if isinstance(error, ProbeError) else 'invalid_response'
            # Country.is implicit lookups have disagreed with explicit IP
            # lookups. Bind this independent observation to the measured exit.
            if envelope['provider'] == 'vpngate':
                results.pop(4, None)
                if 0 in results and metadata_fetcher is None:
                    try:
                        measured = str(global_ip(results[0]['ip']))
                        body = json.loads(run('curl', '--fail', '--silent', '--max-time', '8',
                                              '--max-filesize', '32768', '--proto', '=https',
                                              'https://api.country.is/' + measured, timeout=10))
                        if body.get('ip') == measured:
                            results[4] = body
                    except (ProbeError, ValueError, AttributeError):
                        pass
            result.update(assess_responses(results, country, require_conflict_source=(
                private_trial is not None or envelope['provider'] == 'vpngate')))
            if private_trial is not None:
                if metadata_fetcher is not None or not result.get('country_verified') or not result.get('udp_dns_passed'):
                    raise ProbeError('private_trial_requires_real_verified_exit')
                stage = 'private_phone_trial'
                private_trial(ns, process, result)
            stage = 'tunnel_drop'
            process.terminate()
            process.wait(timeout=5)
            drop_checks = []
            # Recheck the same UDP query that passed with the tunnel alive.
            try:
                run('ip', 'netns', 'exec', ns, 'python3', '-c', DNS_UDP_PROBE, timeout=6)
                drop_checks.append(False)
            except ProbeError:
                drop_checks.append(True)
            if results:
                # Never use an endpoint that already failed as the negative control.
                successful_url = ['https://api.ipify.org?format=json', 'https://ifconfig.co/json',
                                  'https://ipwho.is/', 'https://ipinfo.io/json', 'https://api.country.is/'][min(results)]
                try:
                    run('ip', 'netns', 'exec', ns, 'curl', '--ipv4', '--fail', '--silent', '--max-time', '2',
                        '--noproxy', '*', successful_url, timeout=4)
                    drop_checks.append(False)
                except ProbeError:
                    drop_checks.append(True)
            result['tunnel_drop_blocked'] = len(drop_checks) == 2 and all(drop_checks)
            if not all(drop_checks):
                result.update(country_verified=False, status='leak_test_failed')
            elif len(drop_checks) != 2:
                result.update(country_verified=False, status='drop_test_inconclusive')
        except (ProbeError, ValueError, OSError, subprocess.TimeoutExpired) as failure:
            result['failure_type'] = type(failure).__name__
            if isinstance(failure, OSError):
                result['failure_errno'] = failure.errno
            diagnostic = ''
            if log.exists():
                with log.open(errors='replace') as stream:
                    diagnostic = stream.read(65536)
            result['reported_ciphers'] = sorted(set(re.findall(
                r'(?<![A-Za-z0-9-])(?:AES-(?:128|256)-(?:GCM|CBC)|CHACHA20-POLY1305|BF-CBC)(?![A-Za-z0-9-])', diagnostic)))
            result['log_markers'] = [label for marker, label in [
                ('VERIFY OK', 'certificate_chain_checked'),
                ('Peer Connection Initiated', 'tls_peer_connected'),
                ('PUSH_REPLY', 'configuration_received'),
                ('AUTH_FAILED', 'server_auth_failed'),
                ('Data channel cipher negotiation failed', 'cipher_negotiation_failed'),
                ('failed to negotiate cipher', 'cipher_negotiation_failed'),
                ('OPTIONS ERROR', 'pushed_options_rejected'),
                ('Compression is not allowed', 'compression_rejected'),
                ('Initialization Sequence Completed', 'initialization_completed'),
                ('Connection reset', 'connection_reset'),
                ('Exiting due to fatal error', 'fatal_error'),
            ] if marker in diagnostic]
            result['country_verified'] = False
            result['verified_country'] = None
            result['failed_stage'] = stage
            result['openvpn_alive_at_failure'] = process is not None and process.poll() is None
            result['status'] = ('post_handshake_probe_failed' if result.get('handshake_completed') else
                                classify_log(diagnostic))
        finally:
            if process and process.poll() is None:
                if paused:
                    process.send_signal(signal.SIGCONT)
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
    if not result.get('country_verified'):
        result['verified_country'] = None
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
