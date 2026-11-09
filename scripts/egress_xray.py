"""Generate internal VLESS/WS ingress for a single isolated pool.

These are private runtime configurations, NOT public connection profiles. The
host connector must terminate TLS and authorize/scopingly distribute identities.
A future supervisor must own process lifetimes and enforce session revocation.
"""
import ipaddress
import re
import uuid


def configurations(payload_ip, identity, path, socks_port=10809):
    address = ipaddress.ip_address(payload_ip)
    if address.version != 4 or address.is_unspecified or address.is_multicast:
        raise ValueError('IPv4 pool address required')
    identity = str(uuid.UUID(identity))
    if not re.fullmatch('/[a-f0-9]{32}', path):
        raise ValueError('Random fixed-format internal path required')
    if type(socks_port) is not int or not 1024 <= socks_port <= 65535:
        raise ValueError('Invalid test SOCKS port')
    stream = {'network': 'ws', 'security': 'none', 'wsSettings': {'path': path}}
    server = {
        'log': {'loglevel': 'warning'},
        'inbounds': [{'listen': str(address), 'port': 18888, 'protocol': 'vless',
                      'settings': {'clients': [{'id': identity}], 'decryption': 'none'},
                      'streamSettings': stream}],
        'outbounds': [{'protocol': 'freedom'}],
    }
    client = {
        'log': {'loglevel': 'warning'},
        'inbounds': [{'listen': '127.0.0.1', 'port': socks_port, 'protocol': 'socks',
                      'settings': {'auth': 'noauth', 'udp': True}}],
        'outbounds': [{'protocol': 'vless',
                       'settings': {'vnext': [{'address': str(address), 'port': 18888,
                                              'users': [{'id': identity, 'encryption': 'none'}]}]},
                       'streamSettings': stream}],
    }
    return server, client
