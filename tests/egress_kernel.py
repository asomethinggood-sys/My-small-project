#!/usr/bin/env python3
"""Privileged LOCAL kernel integration: no provider, public traffic or host routes.

Creates two payload namespaces and two local fixture networks. Default 'VPN'
interfaces are veth stand-ins; --wireguard uses real encrypted local peers.
Checks kernel filtering and ingress isolation, but not public-provider correctness.
All namespaces/processes are cleaned even on test failure.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.egress_firewall import rules, legacy_rules


def run(*args, **kwargs):
    result = subprocess.run(list(args), capture_output=True, text=True, timeout=10, **kwargs)
    if result.returncode:
        raise RuntimeError(f'Local fixture command failed: {args!r}: {result.stderr}')
    return result


SERVER = '''import socket,sys
s=socket.socket(socket.AF_INET6 if ':' in sys.argv[1] else socket.AF_INET);s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind((sys.argv[1],int(sys.argv[2])));s.listen(10)
print('ready',flush=True)
while True:
 c,a=s.accept()
 try: c.sendall(sys.argv[3].encode())
 except OSError: pass
 c.close()
'''
UDP_SERVER = '''import socket,sys
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind((sys.argv[1],int(sys.argv[2])))
print('ready',flush=True)
while True:
 data,addr=s.recvfrom(1024);s.sendto(sys.argv[3].encode(),addr)
'''
DNS_SERVER = '''import socket,sys,struct
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind((sys.argv[1],int(sys.argv[2])))
print('ready',flush=True)
while True:
 data,addr=s.recvfrom(512)
 if len(data)<12: continue
 response=data[:2]+struct.pack('!HHHHH',0x8180,1,1,0,0)+data[12:]+bytes.fromhex('c00c000100010000003c0004c6336401')
 s.sendto(response,addr)
'''
DNS_CLIENT = '''import socket,sys,struct
query=struct.pack('!HHHHHH',1234,0x100,1,0,0,0)+b'\\x04test\\x07invalid\\x00'+struct.pack('!HH',1,1)
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(0.6)
try:
 s.sendto(query,(sys.argv[1],int(sys.argv[2])));data=s.recv(512)
 if data[:2]!=query[:2] or data[2:4]!=b'\\x81\\x80' or data[-4:]!=bytes([198,51,100,1]): sys.exit(8)
 print('dns-fixture')
except OSError: sys.exit(7)
'''
CLIENT = '''import socket,sys
try:
 s=socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=0.6)
 print(s.recv(128).decode());s.close()
except OSError: sys.exit(7)
'''
UDP_CLIENT = '''import socket,sys
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(0.6)
try:
 s.sendto(b'probe',(sys.argv[1],int(sys.argv[2])));print(s.recv(128).decode())
except OSError: sys.exit(7)
'''


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo; only disposable namespaces are changed')
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firewall', choices=['nft', 'legacy'], default='nft')
    parser.add_argument('--wireguard', type=Path, help='Use real local encrypted peers with this wg binary')
    args = parser.parse_args()
    if args.wireguard:
        args.wireguard = args.wireguard.resolve(strict=True)
    prefix = 'nyxt-' + uuid.uuid4().hex[:8]
    namespaces, processes, results = [], [], []
    baseline = run('ip', '-j', 'route', 'show', 'table', 'main').stdout
    try:
        def namespace(suffix):
            name = prefix + suffix
            run('ip', 'netns', 'add', name)
            namespaces.append(name)
            run('ip', '-n', name, 'link', 'set', 'lo', 'up')
            return name

        ingress = namespace('i')
        exitns = namespace('e')
        pools = [namespace('a'), namespace('b')]

        def link(left, lname, laddr, right, rname, raddr):
            # Both ends are created directly in disposable namespaces.
            run('ip', '-n', left, 'link', 'add', lname, 'type', 'veth',
                'peer', 'name', rname, 'netns', right)
            for ns, name, addr in [(left, lname, laddr), (right, rname, raddr)]:
                run('ip', '-n', ns, 'addr', 'add', addr, 'dev', name)
                run('ip', '-n', ns, 'link', 'set', name, 'up')

        def serve(ns, address, port, label, udp=False, dns=False):
            # A pipe readiness notification avoids assuming process startup timing.
            import select
            proc = subprocess.Popen(['ip', 'netns', 'exec', ns, sys.executable, '-u', '-c',
                                     DNS_SERVER if dns else UDP_SERVER if udp else SERVER, address, str(port), label],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append(proc)
            readable, _, _ = select.select([proc.stdout], [], [], 3)
            if not readable or proc.stdout.readline().strip() != 'ready':
                raise RuntimeError('Fixture listener failed to start')

        def probe(ns, address, port, expected=None, udp=False, dns=False):
            result = subprocess.run(['ip', 'netns', 'exec', ns, sys.executable, '-c',
                                     DNS_CLIENT if dns else UDP_CLIENT if udp else CLIENT, address, str(port)],
                                    capture_output=True, text=True, timeout=3)
            if expected is None:
                if result.returncode != 7:
                    raise AssertionError('Expected blocked traffic')
            elif result.returncode or result.stdout.strip() != expected:
                raise AssertionError('Expected fixture path did not work')

        if args.wireguard:
            link(ingress, 'outer', '10.201.0.1/30', exitns, 'outer', '10.201.0.2/30')

        def encrypted_link(index, pool):
            # Socket birthplace is ingress; plaintext interface lives only in pool.
            wg = str(args.wireguard)
            private_a = run(wg, 'genkey').stdout.strip()
            private_b = run(wg, 'genkey').stdout.strip()
            public_a = run(wg, 'pubkey', input=private_a).stdout.strip()
            public_b = run(wg, 'pubkey', input=private_b).stdout.strip()
            run('ip', '-n', ingress, 'link', 'add', f'birth{index}', 'type', 'wireguard')
            run('ip', '-n', ingress, 'link', 'set', f'birth{index}', 'netns', pool)
            run('ip', '-n', pool, 'link', 'set', f'birth{index}', 'name', 'nyx-vpn')
            run('ip', '-n', exitns, 'link', 'add', f'ex{index}', 'type', 'wireguard')
            for ns, device, private, public, listen, endpoint, address in [
                    (pool, 'nyx-vpn', private_a, public_b, 51000 + index,
                     f'10.201.0.2:{52000 + index}', f'198.18.{index}.2/30'),
                    (exitns, f'ex{index}', private_b, public_a, 52000 + index,
                     f'10.201.0.1:{51000 + index}', f'198.18.{index}.1/30')]:
                config = (f'[Interface]\nPrivateKey = {private}\nListenPort = {listen}\n'
                          f'[Peer]\nPublicKey = {public}\nAllowedIPs = 0.0.0.0/0, ::/0\n'
                          f'Endpoint = {endpoint}\n')
                run('ip', 'netns', 'exec', ns, wg, 'setconf', device, '/dev/stdin', input=config)
                run('ip', '-n', ns, 'addr', 'add', address, 'dev', device)
                run('ip', '-n', ns, 'link', 'set', device, 'up')

        for index, pool in enumerate(pools, 1):
            link(ingress, f'in{index}', f'10.200.{index}.1/30',
                 pool, 'nyx-in', f'10.200.{index}.2/30')
            if args.wireguard:
                encrypted_link(index, pool)
            else:
                link(exitns, f'ex{index}', f'198.18.{index}.1/30',
                     pool, 'nyx-vpn', f'198.18.{index}.2/30')
            run('ip', '-n', pool, 'route', 'add', 'default', 'via', f'198.18.{index}.1', 'metric', '10')
            # Deliberately dangerous fallback route: firewall must still block it.
            run('ip', '-n', pool, 'route', 'add', 'default', 'via', f'10.200.{index}.1', 'metric', '100')
            if args.firewall == 'nft':
                run('ip', 'netns', 'exec', pool, 'nft', '-f', '-', input=rules(f'10.200.{index}.1'))
            else:
                ipv4, ipv6 = legacy_rules(f'10.200.{index}.1')
                run('ip', 'netns', 'exec', pool, 'iptables-legacy-restore', input=ipv4)
                run('ip', 'netns', 'exec', pool, 'ip6tables-legacy-restore', input=ipv6)
            serve(pool, f'10.200.{index}.2', 18888, f'ingress-{index}')
            serve(pool, f'10.200.{index}.2', 18889, 'must-not-reach')
            serve(exitns, f'198.18.{index}.1', 18080, f'exit-{index}')
            serve(exitns, f'198.18.{index}.1', 18081, f'udp-{index}', udp=True)
            serve(ingress, f'10.200.{index}.1', 18080, 'underlay-leak')
            serve(exitns, f'198.18.{index}.1', 53, 'dns-fixture', dns=True)
            serve(ingress, f'10.200.{index}.1', 53, 'dns-fixture', dns=True)
            probe(pool, f'198.18.{index}.1', 53, 'dns-fixture', dns=True)
            probe(pool, f'10.200.{index}.1', 53, dns=True)
            results.append(f'pool-{index}: DNS fixture works over exit; direct underlay DNS blocked')
            probe(ingress, f'10.200.{index}.2', 18888, f'ingress-{index}')
            results.append(f'pool-{index}: allowed ingress and return traffic')
            probe(ingress, f'10.200.{index}.2', 18889)
            results.append(f'pool-{index}: unexpected ingress port blocked')
            probe(pool, f'198.18.{index}.1', 18080, f'exit-{index}')
            probe(pool, f'198.18.{index}.1', 18081, f'udp-{index}', udp=True)
            results.append(f'pool-{index}: local TCP and UDP exit paths work')
            if args.wireguard:
                handshake = run('ip', 'netns', 'exec', pool, str(args.wireguard),
                                'show', 'nyx-vpn', 'latest-handshakes').stdout.split()
                if len(handshake) != 2 or int(handshake[1]) <= 0:
                    raise AssertionError('Missing WireGuard handshake')
                results.append(f'pool-{index}: real local WireGuard handshake verified')
            probe(pool, f'10.200.{index}.1', 18080)
            results.append(f'pool-{index}: direct underlay egress blocked')

        # Exercise IPv6 explicitly with an available route/listener, not absence of IPv6.
        run('ip', '-n', exitns, '-6', 'addr', 'add', 'fd00:123::1/64', 'dev', 'ex1', 'nodad')
        run('ip', '-n', pools[0], '-6', 'addr', 'add', 'fd00:123::2/64', 'dev', 'nyx-vpn', 'nodad')
        serve(exitns, 'fd00:123::1', 18080, 'ipv6-fixture')
        probe(exitns, 'fd00:123::1', 18080, 'ipv6-fixture')
        if args.firewall == 'legacy':
            # Positive control proves this IPv6 path works without the restriction.
            # Limit the temporary exception to the local fixture and then remove it.
            allow_out = ['OUTPUT', '-o', 'nyx-vpn', '-d', 'fd00:123::1', '-p', 'tcp',
                         '--dport', '18080', '-j', 'ACCEPT']
            allow_in = ['INPUT', '-i', 'nyx-vpn', '-s', 'fd00:123::1', '-p', 'tcp',
                        '--sport', '18080', '-j', 'ACCEPT']
            run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-I', *allow_out)
            run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-I', *allow_in)
            if not args.wireguard:
                # Veth requires neighbor discovery; WireGuard interfaces do not.
                run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-I', 'INPUT', '-p', 'ipv6-icmp', '-j', 'ACCEPT')
                run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-I', 'OUTPUT', '-p', 'ipv6-icmp', '-j', 'ACCEPT')
            probe(pools[0], 'fd00:123::1', 18080, 'ipv6-fixture')
            run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-D', *allow_out)
            run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-D', *allow_in)
            if not args.wireguard:
                run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-D', 'INPUT', '-p', 'ipv6-icmp', '-j', 'ACCEPT')
                run('ip', 'netns', 'exec', pools[0], 'ip6tables-legacy', '-D', 'OUTPUT', '-p', 'ipv6-icmp', '-j', 'ACCEPT')
            results.append('IPv6 positive control passes before restoring the block policy')
        probe(pools[0], 'fd00:123::1', 18080)
        results.append('pool-1: IPv6 connection blocked with a configured route and live fixture listener')

        run('ip', '-n', pools[0], 'link', 'del', 'nyx-vpn')
        probe(pools[0], '10.200.1.1', 18080)
        probe(pools[0], '198.18.1.1', 18080)
        probe(pools[0], '198.18.1.1', 18081, udp=True)
        probe(pools[0], '198.18.1.1', 53, dns=True)
        probe(pools[0], '10.200.1.1', 53, dns=True)
        results.append('pool-1: tunnel-interface removal blocks TCP/UDP and underlay fallback')
        probe(pools[1], '198.18.2.1', 18080, 'exit-2')
        probe(pools[1], '198.18.2.1', 18081, 'udp-2', udp=True)
        probe(ingress, '10.200.2.2', 18888, 'ingress-2')
        results.append('pool-2: TCP/UDP and ingress survive pool-1 failure')
        probe(ingress, '10.200.1.2', 18888, 'ingress-1')
        results.append('pool-1: ingress control path survives tunnel-interface removal')
    finally:
        for proc in processes:
            proc.terminate()
        for proc in processes:
            try:
                proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
        for ns in reversed(namespaces):
            run('ip', 'netns', 'del', ns)
    if run('ip', '-j', 'route', 'show', 'table', 'main').stdout != baseline:
        raise AssertionError('Host main route table changed')
    results.append('host main routes unchanged; disposable namespaces removed')
    print(json.dumps({'kind': 'local_kernel_fixture_not_provider_test',
                      'transport': 'wireguard' if args.wireguard else 'veth',
                      'firewall': args.firewall, 'passed': results}, indent=2))


if __name__ == '__main__':
    main()
