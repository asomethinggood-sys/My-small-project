"""Strict WireGuard input boundary. No shell hooks, DNS changes or host routes.

Returns wg(8) configuration, not wg-quick configuration. Calling code must create
an isolated interface and apply addresses/firewall rules separately. Unknown
provider extensions fail closed, rather than being silently executed or ignored.
"""
import base64
import ipaddress
import re

MAX_CONFIG_BYTES = 32768


def key(value):
    try:
        decoded = base64.b64decode(value, validate=True)
    except ValueError:
        raise ValueError('Invalid WireGuard key') from None
    if len(decoded) != 32:
        raise ValueError('Invalid WireGuard key length')
    return value


def global_ip(value):
    address = ipaddress.ip_address(value)
    if not address.is_global or address.is_multicast:
        raise ValueError('Public unicast endpoint required')
    return address


def parse_wireguard(text):
    if len(text.encode()) > MAX_CONFIG_BYTES or '\x00' in text:
        raise ValueError('Invalid configuration size/content')
    sections = {}
    section = None
    allowed = {
        'Interface': {'PrivateKey', 'Address', 'DNS', 'MTU'},
        'Peer': {'PublicKey', 'PresharedKey', 'AllowedIPs', 'Endpoint', 'PersistentKeepalive'},
    }
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            if line not in ('[Interface]', '[Peer]') or line[1:-1] in sections:
                raise ValueError('Exactly one interface and peer supported')
            section = line[1:-1]
            sections[section] = {}
            continue
        if section is None or '=' not in line:
            raise ValueError('Invalid configuration syntax')
        name, value = (part.strip() for part in line.split('=', 1))
        if name not in allowed[section] or name in sections[section] or not value:
            raise ValueError('Unsupported or duplicate directive')
        sections[section][name] = value
    if set(sections) != set(allowed):
        raise ValueError('Interface and peer required')
    interface, peer = sections['Interface'], sections['Peer']
    if not {'PrivateKey', 'Address'}.issubset(interface) or not {
            'PublicKey', 'AllowedIPs', 'Endpoint'}.issubset(peer):
        raise ValueError('Missing required directive')
    key(interface['PrivateKey'])
    key(peer['PublicKey'])
    if 'PresharedKey' in peer:
        key(peer['PresharedKey'])
    addresses = [str(ipaddress.ip_interface(v.strip())) for v in interface['Address'].split(',')]
    routes = {str(ipaddress.ip_network(v.strip(), strict=True)) for v in peer['AllowedIPs'].split(',')}
    if routes not in ({'0.0.0.0/0'}, {'0.0.0.0/0', '::/0'}):
        raise ValueError('Full IPv4 tunnel required; optional full IPv6 only')
    match = re.fullmatch(r'(?:\[([^\]]+)\]|([^:]+)):(\d{1,5})', peer['Endpoint'])
    if not match:
        raise ValueError('Invalid endpoint')
    # Names must first be resolved/validated by a separate trusted acquisition layer.
    endpoint = global_ip(match[1] or match[2])
    port = int(match[3])
    if not 1 <= port <= 65535:
        raise ValueError('Invalid endpoint port')
    dns = [str(global_ip(v.strip())) for v in interface.get('DNS', '').split(',') if v.strip()]
    mtu = int(interface.get('MTU', '1280'))
    keepalive = int(peer.get('PersistentKeepalive', '25'))
    if not 1280 <= mtu <= 1420 or not 0 <= keepalive <= 120:
        raise ValueError('MTU or keepalive outside supported bounds')
    endpoint_string = f'[{endpoint}]:{port}' if endpoint.version == 6 else f'{endpoint}:{port}'
    lines = ['[Interface]', 'PrivateKey = ' + interface['PrivateKey'], '[Peer]',
             'PublicKey = ' + peer['PublicKey']]
    if 'PresharedKey' in peer:
        lines.append('PresharedKey = ' + peer['PresharedKey'])
    lines += ['AllowedIPs = ' + ', '.join(sorted(routes)), 'Endpoint = ' + endpoint_string,
              'PersistentKeepalive = ' + str(keepalive)]
    return {'wg_config': '\n'.join(lines) + '\n', 'addresses': addresses, 'dns': dns,
            'mtu': mtu, 'endpoint_ip': str(endpoint), 'endpoint_port': port,
            'ipv6_requested': '::/0' in routes}
