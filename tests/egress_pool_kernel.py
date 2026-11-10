#!/usr/bin/env python3
"""Exercise reusable WireGuardPool against a local encrypted peer, no Internet.

The manager's 'host' is itself a disposable namespace. Public-looking IPs below
exist only inside that fixture. No provider configuration or traffic is used.
"""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.egress_wireguard import WireGuardPool
from egress_kernel import run, SERVER, UDP_SERVER, DNS_SERVER, CLIENT, UDP_CLIENT, DNS_CLIENT


def main():
    if os.geteuid() != 0 or len(sys.argv) not in (2, 3):
        raise SystemExit('Usage: sudo python3 tests/egress_pool_kernel.py /path/to/wg [/path/to/xray]')
    wg = str(Path(sys.argv[1]).resolve(strict=True))
    suffix = uuid.uuid4().hex[:8]
    control, peer = 'nyxc-' + suffix, 'nyxe-' + suffix
    created, processes, results = [], [], []
    pool = None
    baseline = run('ip', '-j', 'route', 'show', 'table', 'main').stdout
    try:
        for ns in [control, peer]:
            run('ip', 'netns', 'add', ns)
            created.append(ns)
            run('ip', '-n', ns, 'link', 'set', 'lo', 'up')
        run('ip', '-n', control, 'link', 'add', 'outer', 'type', 'veth',
            'peer', 'name', 'outer', 'netns', peer)
        for ns, address in [(control, '10.201.0.1/30'), (peer, '10.201.0.2/30')]:
            run('ip', '-n', ns, 'addr', 'add', address, 'dev', 'outer')
            run('ip', '-n', ns, 'link', 'set', 'outer', 'up')
        run('ip', '-n', peer, 'addr', 'add', '8.8.8.8/32', 'dev', 'lo')
        run('ip', '-n', control, 'route', 'add', '8.8.8.8/32', 'via', '10.201.0.2')
        private_client, private_peer = [run(wg, 'genkey').stdout.strip() for _ in range(2)]
        public_client = run(wg, 'pubkey', input=private_client).stdout.strip()
        public_peer = run(wg, 'pubkey', input=private_peer).stdout.strip()
        run('ip', '-n', peer, 'link', 'add', 'vpn', 'type', 'wireguard')
        peer_config = (f'[Interface]\nPrivateKey = {private_peer}\nListenPort = 51820\n'
                       f'[Peer]\nPublicKey = {public_client}\nAllowedIPs = 10.2.0.2/32\n')
        run('ip', 'netns', 'exec', peer, wg, 'setconf', 'vpn', '/dev/stdin', input=peer_config)
        run('ip', '-n', peer, 'addr', 'add', '1.1.1.1/32', 'dev', 'vpn')
        run('ip', '-n', peer, 'link', 'set', 'vpn', 'up')
        run('ip', '-n', peer, 'route', 'add', '10.2.0.2/32', 'dev', 'vpn')

        def execute(argv, input=None):
            # Enter only the network namespace. ip netns exec also unshares mount
            # state, which would hide newly created namespace handles on return.
            return WireGuardPool._execute(['nsenter', '--net=/var/run/netns/' + control,
                                           '--', *argv], input=input)

        pool = WireGuardPool(wg, 221, shared_use_approved=True, run=execute)
        config = (f'[Interface]\nPrivateKey = {private_client}\nAddress = 10.2.0.2/32\n'
                  f'DNS = 1.1.1.1\n[Peer]\nPublicKey = {public_peer}\n'
                  'AllowedIPs = 0.0.0.0/0\nEndpoint = 8.8.8.8:51820\n')
        status = pool.start(config)
        assert status['state'] == 'configured_unverified'
        results.append('Reusable manager configures a real isolated WireGuard pool without declaring it ready')
        resolver = run('ip', 'netns', 'exec', pool.namespace, 'cat', '/etc/resolv.conf').stdout
        assert 'nameserver 1.1.1.1\n' in resolver
        results.append('ip netns exec binds the pool-specific resolver file')
        for script, port in [(SERVER, 18080), (UDP_SERVER, 18081), (DNS_SERVER, 53)]:
            process = subprocess.Popen(['ip', 'netns', 'exec', peer, sys.executable, '-u', '-c',
                                        script, '1.1.1.1', str(port), 'local-peer'],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            processes.append(process)
            readable, _, _ = select.select([process.stdout], [], [], 3)
            if not readable or process.stdout.readline().strip() != 'ready':
                raise RuntimeError('Local peer failed to start')
        for script, port, expected in [(CLIENT, 18080, 'local-peer'),
                                       (UDP_CLIENT, 18081, 'local-peer'),
                                       (DNS_CLIENT, 53, 'dns-fixture')]:
            result = run('ip', 'netns', 'exec', pool.namespace, sys.executable, '-c',
                         script, '1.1.1.1', str(port))
            assert result.stdout.strip() == expected
        results.append('Manager-created tunnel passes real TCP, UDP and DNS fixture probes')
        # The actual libc resolver uses /etc/resolv.conf, not a manually chosen socket address.
        result = run('ip', 'netns', 'exec', pool.namespace, sys.executable, '-c',
                     "import socket; print(socket.gethostbyname('test.invalid'))")
        assert result.stdout.strip() == '198.51.100.1'
        results.append('System resolver lookup passes through the tunnel to the local DNS fixture')
        handshakes = run('ip', 'netns', 'exec', pool.namespace, wg,
                         'show', 'nyx-vpn', 'latest-handshakes').stdout.split()
        assert len(handshakes) == 2 and int(handshakes[1]) > 0
        results.append('Real encrypted handshake verified')
        if len(sys.argv) == 3:
            from egress_xray_fixture import test_xray
            results.extend(test_xray(str(Path(sys.argv[2]).resolve(strict=True)), pool, control, peer))
        pool_namespace = pool.namespace
        resolver_directory = pool.resolver_directory
        pool.close()
        pool.close()
        assert not resolver_directory.exists()
        assert pool_namespace not in run('ip', 'netns', 'list').stdout
        results.append('Idempotent close removes tunnel, host veth, namespace and resolver file')
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        if pool is not None:
            pool.close()
        for ns in reversed(created):
            run('ip', 'netns', 'del', ns)
    assert run('ip', '-j', 'route', 'show', 'table', 'main').stdout == baseline
    results.append('Actual host main routes unchanged; no public provider traffic')
    print(json.dumps({'kind': 'local_pool_manager_integration', 'passed': results}, indent=2))


if __name__ == '__main__':
    main()
