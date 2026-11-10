"""Reusable WireGuard namespace resource manager; not a readiness verifier.

Requires root, trusted wg tooling and an authorized provider configuration. Never
changes the host default route. start() means resources installed, NOT a verified
country exit. Only a separate full-path verifier may publish a route.
"""
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import threading

from scripts.egress_config import parse_wireguard
from scripts.egress_firewall import legacy_rules, rules


class NetworkError(RuntimeError):
    pass


class WireGuardPool:
    # This component requires a single owning supervisor process. Serialize local
    # route-conflict checks/allocation across its pool objects, not just per pool.
    _allocation_lock = threading.RLock()

    def __init__(self, wg_binary, slot, firewall='legacy', shared_use_approved=False,
                 run=None, netns_root='/etc/netns'):
        if shared_use_approved is not True:
            raise ValueError('Explicit provider shared-use approval required')
        if type(slot) is not int or not 1 <= slot <= 254:
            raise ValueError('Slot must be an integer in 1..254')
        if firewall not in ('legacy', 'nft'):
            raise ValueError('Unsupported firewall backend')
        binary = Path(wg_binary)
        if not binary.is_absolute():
            raise ValueError('Trusted absolute wg binary path required')
        suffix = secrets.token_hex(4)
        self.namespace = 'nyxp-' + suffix
        self.host_link = 'nyxh-' + suffix
        self.birth_link = 'nyxw-' + suffix
        self.host_ip, self.payload_ip = f'198.19.{slot}.1', f'198.19.{slot}.2'
        self.subnet = ipaddress.ip_network(f'198.19.{slot}.0/30')
        self.wg, self.firewall = str(binary), firewall
        self.resolver_directory = Path(netns_root) / self.namespace
        self._run = run or self._execute
        self._undo = []
        self._lock = threading.RLock()
        self.state = 'new'

    @staticmethod
    def _execute(argv, input=None):
        try:
            result = subprocess.run(argv, input=input, capture_output=True, text=True,
                                    timeout=15, check=False, env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin'})
        except (OSError, subprocess.TimeoutExpired):
            raise NetworkError('Network operation could not complete') from None
        if result.returncode:
            # Config stdin can contain keys. Never include command/stdout/stderr.
            raise NetworkError('Network operation failed')
        return result.stdout

    def _ns(self, *argv, input=None):
        return self._run(['ip', 'netns', 'exec', self.namespace, *argv], input=input)

    def _ip(self, *argv):
        return self._run(['ip', '-n', self.namespace, *argv])

    def _check_route_conflict(self):
        for route in json.loads(self._run(['ip', '-j', '-4', 'route', 'show', 'table', 'all'])):
            destination = route.get('dst', 'default')
            if destination == 'default':
                continue
            try:
                existing = ipaddress.ip_network(destination, strict=False)
            except ValueError:
                raise NetworkError('Unrecognized host route; refusing allocation') from None
            if self.subnet.overlaps(existing):
                raise NetworkError('Pool subnet conflicts with existing host routes')

    def start(self, configuration):
        with self._allocation_lock, self._lock:
            if self.state != 'new':
                raise NetworkError('Pool instance cannot be reused')
            parsed = parse_wireguard(configuration)
            if not parsed['dns']:
                raise ValueError('Explicit tunneled DNS resolver required')
            # IPv6 is deliberately unsupported until its complete path is verified.
            if (parsed['ipv6_requested'] or any(':' in address for address in parsed['addresses'])
                    or any(':' in address for address in parsed['dns'])):
                raise ValueError('This pool currently requires IPv4-only configuration')
            if len(parsed['addresses']) > 4 or len(parsed['dns']) > 3:
                raise ValueError('Address or resolver budget exceeded')
            # Prevent provider interface addresses from colliding with ingress.
            for address in parsed['addresses']:
                interface = ipaddress.ip_interface(address)
                if (interface.ip.is_loopback or interface.ip.is_link_local or interface.ip.is_multicast
                        or interface.ip.is_unspecified or interface.ip.is_reserved
                        or interface.network.prefixlen < 16):
                    raise ValueError('Unsafe tunnel interface address')
                if interface.network.overlaps(self.subnet):
                    raise ValueError('Tunnel address conflicts with ingress subnet')
            self.state = 'starting'
            try:
                self._check_route_conflict()
                self._run(['ip', 'netns', 'add', self.namespace])
                self._undo.append(('command', ['ip', 'netns', 'del', self.namespace]))
                self.resolver_directory.parent.mkdir(mode=0o755, exist_ok=True)
                self.resolver_directory.mkdir(mode=0o700, parents=False, exist_ok=False)
                self._undo.append(('resolver', None))
                resolver = self.resolver_directory / 'resolv.conf'
                fd = os.open(resolver, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    stream.write(''.join('nameserver ' + address + '\n' for address in parsed['dns']))
                    stream.write('options timeout:2 attempts:2\n')
                self._ip('link', 'set', 'lo', 'up')
                # Install drop policies before creating either data interface.
                if self.firewall == 'legacy':
                    ipv4, ipv6 = legacy_rules(self.host_ip)
                    self._ns('iptables-legacy-restore', input=ipv4)
                    self._ns('ip6tables-legacy-restore', input=ipv6)
                else:
                    self._ns('nft', '-f', '-', input=rules(self.host_ip))
                self._run(['ip', 'link', 'add', self.host_link, 'type', 'veth',
                           'peer', 'name', 'nyx-in', 'netns', self.namespace])
                self._undo.append(('command', ['ip', 'link', 'del', self.host_link]))
                self._run(['ip', 'addr', 'add', self.host_ip + '/30', 'dev', self.host_link])
                self._run(['ip', 'link', 'set', self.host_link, 'up'])
                self._ip('addr', 'add', self.payload_ip + '/30', 'dev', 'nyx-in')
                self._ip('link', 'set', 'nyx-in', 'up')
                # Outer UDP socket is born on the normal host route.
                self._run(['ip', 'link', 'add', self.birth_link, 'type', 'wireguard'])
                birth_cleanup = ('command', ['ip', 'link', 'del', self.birth_link])
                self._undo.append(birth_cleanup)
                self._run(['ip', 'link', 'set', self.birth_link, 'netns', self.namespace])
                self._undo.remove(birth_cleanup)
                moved_cleanup = ('command', ['ip', '-n', self.namespace, 'link', 'del', self.birth_link])
                self._undo.append(moved_cleanup)
                self._ip('link', 'set', self.birth_link, 'name', 'nyx-vpn')
                self._undo.remove(moved_cleanup)
                self._undo.append(('command', ['ip', '-n', self.namespace, 'link', 'del', 'nyx-vpn']))
                self._ns(self.wg, 'setconf', 'nyx-vpn', '/dev/stdin', input=parsed['wg_config'])
                for address in parsed['addresses']:
                    self._ip('addr', 'add', address, 'dev', 'nyx-vpn')
                self._ip('link', 'set', 'nyx-vpn', 'mtu', str(parsed['mtu']), 'up')
                self._ip('route', 'add', 'default', 'dev', 'nyx-vpn')
                self.state = 'configured_unverified'
                return {'namespace': self.namespace, 'ingress_ip': self.payload_ip,
                        'ingress_port': 18888, 'state': self.state}
            except Exception:
                self.state = 'failed'
                try:
                    self.close()
                except NetworkError:
                    raise NetworkError('Startup failed and cleanup requires attention') from None
                raise

    def close(self):
        with self._allocation_lock, self._lock:
            while self._undo:
                kind, value = self._undo[-1]
                try:
                    if kind == 'command':
                        self._run(value)
                    else:
                        resolver = self.resolver_directory / 'resolv.conf'
                        if resolver.exists():
                            resolver.unlink()
                        self.resolver_directory.rmdir()
                except (OSError, NetworkError):
                    # Preserve dependency order: deleting the namespace after a
                    # failed interface removal would make a retry ambiguous.
                    self.state = 'cleanup_failed'
                    raise NetworkError('Resource cleanup incomplete; do not allocate replacement blindly') from None
                self._undo.pop()
            self.state = 'closed'

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
