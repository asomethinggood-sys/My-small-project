#!/usr/bin/env python3
"""Prove a host-owned TUN fd can carry payload in another network namespace.

No VPN provider/network traffic. One synthetic UDP exchange over a raw local TUN.
"""
import fcntl
import json
import os
from pathlib import Path
import select
import struct
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.egress_firewall import legacy_rules


def run(*args, input=None):
    return subprocess.run(args, input=input, text=True, capture_output=True, check=True, timeout=10)


def main():
    if os.geteuid() != 0:
        raise SystemExit('Requires root')
    name = 'nyxt-' + uuid.uuid4().hex[:8]
    namespace = name + 'n'
    fd, child, created = None, None, False
    host_name = name
    before = run('ip', '-j', 'route', 'show', 'table', 'main').stdout
    try:
        run('ip', 'netns', 'add', namespace)
        created = True
        fd = os.open('/dev/net/tun', os.O_RDWR | os.O_CLOEXEC)
        fcntl.ioctl(fd, 0x400454ca, struct.pack('16sH', name.encode(), 0x0001 | 0x1000))
        run('ip', 'link', 'set', name, 'netns', namespace)
        host_name = None
        run('ip', '-n', namespace, 'link', 'set', name, 'name', 'nyx-vpn')
        ipv4, ipv6 = legacy_rules('198.19.250.1')
        run('ip', 'netns', 'exec', namespace, 'iptables-legacy-restore', input=ipv4)
        run('ip', 'netns', 'exec', namespace, 'ip6tables-legacy-restore', input=ipv6)
        run('ip', '-n', namespace, 'addr', 'add', '10.211.0.2/32', 'dev', 'nyx-vpn')
        run('ip', '-n', namespace, 'link', 'set', 'nyx-vpn', 'up')
        run('ip', '-n', namespace, 'route', 'add', 'default', 'dev', 'nyx-vpn')
        code = "import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(3);s.sendto(b'probe',('1.1.1.1',53));assert s.recv(128)==b'tun-fd-ok';print('passed')"
        child = subprocess.Popen(['ip', 'netns', 'exec', namespace, sys.executable, '-c', code],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            readable, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
            if not readable:
                raise RuntimeError('No outgoing TUN packet')
            packet = os.read(fd, 4096)
            if len(packet) >= 28 and packet[0] >> 4 == 4 and packet[9] == 17:
                break
        else:
            raise RuntimeError('No UDP packet')
        header_length = (packet[0] & 15) * 4
        source_port, dest_port = struct.unpack('!HH', packet[header_length:header_length+4])
        assert dest_port == 53 and packet[16:20] == bytes([1, 1, 1, 1])
        payload = b'tun-fd-ok'
        udp = struct.pack('!HHHH', dest_port, source_port, len(payload) + 8, 0) + payload
        header = struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20 + len(udp), 1, 0, 64, 17, 0,
                             packet[16:20], packet[12:16])
        checksum = sum(struct.unpack('!10H', header))
        while checksum >> 16:
            checksum = (checksum & 65535) + (checksum >> 16)
        checksum = (~checksum) & 65535
        header = header[:10] + struct.pack('!H', checksum) + header[12:]
        os.write(fd, header + udp)
        stdout, stderr = child.communicate(timeout=5)
        assert child.returncode == 0 and stdout.strip() == 'passed'
    finally:
        if child and child.poll() is None:
            child.kill()
            child.communicate()
        if fd is not None:
            os.close(fd)
        if created:
            run('ip', 'netns', 'del', namespace)
    assert before == run('ip', '-j', 'route', 'show', 'table', 'main').stdout
    print(json.dumps({'passed': True, 'test': 'host TUN fd still reads/writes after interface namespace migration',
                      'public_network_used': False, 'host_main_routes_unchanged': True}))


if __name__ == '__main__':
    main()
