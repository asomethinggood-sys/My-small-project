"""Fail-closed IPv4 payload firewall for an isolated VPN namespace.

WireGuard's outer socket must live outside this namespace. OpenVPN is NOT
supported by these rules yet: its underlay endpoint requires a separate design.
IPv6 is deliberately blocked (except loopback), not silently routed directly.
Install with nft inside a newly created namespace, before starting any workload.
"""
import ipaddress
import re


def legacy_rules(ingress_ip, listener_port=18888, ingress='nyx-in', tunnel='nyx-vpn'):
    # Reuse identical identity validation. Called only inside disposable namespaces.
    rules(ingress_ip, listener_port, ingress, tunnel)
    ipv4 = ['*filter', ':INPUT DROP [0:0]', ':FORWARD DROP [0:0]', ':OUTPUT DROP [0:0]',
            '-A INPUT -i lo -j ACCEPT', '-A OUTPUT -o lo -j ACCEPT',
            f'-A INPUT -i {ingress} -s {ingress_ip} -p tcp --dport {listener_port} -m conntrack --ctstate NEW,ESTABLISHED -j ACCEPT',
            f'-A INPUT -i {tunnel} -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
            f'-A OUTPUT -o {ingress} -d {ingress_ip} -p tcp --sport {listener_port} -m conntrack --ctstate ESTABLISHED -j ACCEPT']
    for network in ['0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
                    '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16', '224.0.0.0/4', '240.0.0.0/4']:
        ipv4.append(f'-A OUTPUT -o {tunnel} -d {network} -j DROP')
    ipv4 += [f'-A OUTPUT -o {tunnel} -j ACCEPT', 'COMMIT']
    ipv6 = ['*filter', ':INPUT DROP [0:0]', ':FORWARD DROP [0:0]', ':OUTPUT DROP [0:0]',
            '-A INPUT -i lo -j ACCEPT', '-A OUTPUT -o lo -j ACCEPT', 'COMMIT']
    return '\n'.join(ipv4) + '\n', '\n'.join(ipv6) + '\n'


def rules(ingress_ip, listener_port=18888, ingress='nyx-in', tunnel='nyx-vpn'):
    address = ipaddress.ip_address(ingress_ip)
    if address.version != 4:
        raise ValueError('IPv4 ingress required')
    if type(listener_port) is not int or not 1024 <= listener_port <= 65535:
        raise ValueError('Unprivileged listener port required')
    for name in (ingress, tunnel):
        if not re.fullmatch('[a-z][a-z0-9-]{0,14}', name):
            raise ValueError('Unsafe interface name')
    if ingress == tunnel:
        raise ValueError('Ingress and tunnel must be distinct')
    # Never allow arbitrary established OUTPUT: after a route change that could
    # turn an established tunnel flow into plaintext underlay traffic.
    return f'''table inet nyx {{
  set forbidden4 {{
    type ipv4_addr
    flags interval
    elements = {{ 0.0.0.0/8, 10.0.0.0/8, 100.64.0.0/10, 127.0.0.0/8,
                 169.254.0.0/16, 172.16.0.0/12, 192.168.0.0/16,
                 224.0.0.0/4, 240.0.0.0/4 }}
  }}
  chain input {{
    type filter hook input priority 0; policy drop;
    iifname "lo" accept
    iifname "{ingress}" ip saddr {address} tcp dport {listener_port} ct state new,established accept
    iifname "{tunnel}" meta nfproto ipv4 ct state established,related accept
  }}
  chain output {{
    type filter hook output priority 0; policy drop;
    oifname "lo" accept
    oifname "{ingress}" ip daddr {address} tcp sport {listener_port} ct state established accept
    oifname "{tunnel}" ip daddr @forbidden4 drop
    oifname "{tunnel}" meta nfproto ipv4 accept
  }}
  chain forward {{
    type filter hook forward priority 0; policy drop;
  }}
}}
'''
