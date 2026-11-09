"""Conservative OpenVPN config sanitizer for a future isolated supervisor.

Untrusted configs are never passed straight to OpenVPN. This deliberately rejects
many valid provider extensions: incompatibility must not become arbitrary file
access, script execution, weakened TLS, or provider-pushed host route changes.
Returns sensitive material; callers must not log or publish it. Does not connect.
"""
import ipaddress
import re
import shlex
import ssl
from scripts.egress_config import global_ip

MAX_BYTES = 128 * 1024


def sanitize(text):
    if len(text.encode()) > MAX_BYTES or '\x00' in text:
        raise ValueError('Configuration size/content rejected')
    values, blocks = {}, {}
    current, body = None, []
    allowed = {
        'client', 'dev', 'proto', 'remote', 'resolv-retry', 'nobind', 'persist-key',
        'persist-tun', 'remote-cert-tls', 'verb', 'auth-user-pass', 'auth', 'cipher',
        'data-ciphers', 'tls-version-min', 'key-direction', 'explicit-exit-notify',
    }
    for raw in text.splitlines():
        line = raw.strip()
        if current:
            if line == f'</{current}>':
                blocks[current] = '\n'.join(body)
                current, body = None, []
            else:
                body.append(line)
            continue
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('<'):
            name = line[1:-1]
            if line != f'<{name}>' or name not in {'ca', 'tls-auth', 'tls-crypt'} or name in blocks:
                raise ValueError('Unsupported inline block')
            current = name
            continue
        try:
            tokens = shlex.split(line, comments=False)
        except ValueError:
            raise ValueError('Invalid directive syntax') from None
        name, arguments = tokens[0], tokens[1:]
        if name not in allowed or name in values:
            raise ValueError('Unsupported or duplicate OpenVPN directive')
        values[name] = arguments
    if current:
        raise ValueError('Unclosed inline block')
    if values.get('client') != [] or values.get('dev') != ['tun']:
        raise ValueError('TUN client configuration required')
    protocol = values.get('proto', ['udp'])
    if protocol not in (['udp'], ['udp4'], ['tcp-client'], ['tcp4-client']):
        raise ValueError('Unsupported transport')
    remote = values.get('remote', [])
    if len(remote) != 2 or not remote[1].isdigit():
        raise ValueError('One explicit IP and port required')
    address = global_ip(remote[0])
    if address.version != 4 or not 1 <= int(remote[1]) <= 65535:
        raise ValueError('This adapter supports public IPv4 endpoint only')
    for name in ['nobind', 'persist-key', 'persist-tun', 'auth-user-pass']:
        if name in values and values[name]:
            raise ValueError('Directive arguments not permitted')
    if values.get('remote-cert-tls', ['server']) != ['server']:
        raise ValueError('Server certificate validation required')
    if values.get('tls-version-min', ['1.2']) not in (['1.2'], ['1.3']):
        raise ValueError('TLS downgrade rejected')
    safe_ciphers = {'AES-128-GCM', 'AES-256-GCM', 'CHACHA20-POLY1305', 'AES-128-CBC', 'AES-256-CBC'}
    for name in ['cipher', 'data-ciphers']:
        if name in values and (len(values[name]) != 1 or
                               not set(values[name][0].split(':')).issubset(safe_ciphers)):
            raise ValueError('Unsupported cipher')
    if values.get('auth', ['SHA256']) not in (['SHA256'], ['SHA384'], ['SHA512']):
        raise ValueError('Unsupported authentication digest')
    for name, allowed_values in [('verb', {'0', '1', '2', '3', '4'}),
                                 ('resolv-retry', {'infinite', '10', '30', '60'}),
                                 ('key-direction', {'0', '1'}),
                                 ('explicit-exit-notify', {'0', '1', '2'})]:
        if name in values and (len(values[name]) != 1 or values[name][0] not in allowed_values):
            raise ValueError('Unsupported directive value')
    ca = blocks.get('ca', '')
    certificates = re.findall(r'-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----', ca)
    if not certificates or re.sub(r'-----BEGIN CERTIFICATE-----\s+[A-Za-z0-9+/=\s]+-----END CERTIFICATE-----', '', ca).strip():
        raise ValueError('Inline CA certificates required')
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=ca)
    except ssl.SSLError:
        raise ValueError('Invalid inline CA certificate') from None
    if 'tls-auth' in blocks and 'tls-crypt' in blocks:
        raise ValueError('Conflicting TLS key modes')
    for name in ['tls-auth', 'tls-crypt']:
        if name in blocks:
            data = blocks[name]
            match = re.fullmatch(r'-----BEGIN OpenVPN Static key V1-----\s+([0-9a-fA-F\s]+)-----END OpenVPN Static key V1-----', data)
            if not match or len(''.join(match[1].split())) != 512:
                raise ValueError('Invalid inline TLS key')
    if 'key-direction' in values and 'tls-auth' not in blocks:
        raise ValueError('Key direction requires tls-auth')
    output = ['client', 'dev tun', 'proto ' + protocol[0],
              f'remote {address} {int(remote[1])}', 'nobind', 'remote-cert-tls server',
              'tls-version-min ' + values.get('tls-version-min', ['1.2'])[0],
              'script-security 1', 'auth-nocache', 'route-noexec', 'ifconfig-noexec',
              'route-nopull', 'pull-filter ignore redirect-gateway',
              'pull-filter ignore dhcp-option', 'verb 3']
    for name in ['cipher', 'data-ciphers', 'auth', 'key-direction']:
        if name in values:
            output.append(name + ' ' + values[name][0])
    for name, content in blocks.items():
        output += [f'<{name}>', content, f'</{name}>']
    # The supervisor must supply credentials through its own private file/FD,
    # never a provider-specified path. It also applies namespace IPs/routes itself.
    return {'config': '\n'.join(output) + '\n', 'endpoint_ip': str(address),
            'endpoint_port': int(remote[1]), 'transport': 'udp' if protocol[0].startswith('udp') else 'tcp',
            'credentials_required': 'auth-user-pass' in values}
