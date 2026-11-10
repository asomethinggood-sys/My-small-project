import base64
import json
from pathlib import Path
import tempfile
import unittest
from scripts.egress_wireguard import WireGuardPool, NetworkError

KEY = base64.b64encode(bytes(range(32))).decode()
CONFIG = f'''[Interface]
PrivateKey = {KEY}
Address = 10.2.0.2/32
DNS = 1.1.1.1
[Peer]
PublicKey = {KEY}
AllowedIPs = 0.0.0.0/0
Endpoint = 8.8.8.8:51820
'''


class Recorder:
    def __init__(self, fail_at=None, routes=None):
        self.calls, self.fail_at = [], fail_at
        self.routes = routes or []

    def __call__(self, argv, input=None):
        self.calls.append((argv, input))
        if len(self.calls) == self.fail_at:
            raise NetworkError('injected failure')
        return json.dumps(self.routes) if argv[:4] == ['ip', '-j', '-4', 'route'] else ''


class WireGuardLifecycleTests(unittest.TestCase):
    def make(self, root, recorder):
        return WireGuardPool('/trusted/wg', 7, shared_use_approved=True,
                             run=recorder, netns_root=root)

    def test_configure_never_means_ready_and_close_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            recorder = Recorder()
            pool = self.make(root, recorder)
            result = pool.start(CONFIG)
            self.assertEqual(result['state'], 'configured_unverified')
            self.assertNotIn(KEY, json.dumps(result))
            resolver = pool.resolver_directory / 'resolv.conf'
            self.assertEqual(resolver.stat().st_mode & 0o777, 0o600)
            self.assertIn('nameserver 1.1.1.1', resolver.read_text())
            self.assertTrue(all(KEY not in ' '.join(argv) for argv, _ in recorder.calls))
            pool.close()
            self.assertEqual(list(Path(root).iterdir()), [])
            length = len(recorder.calls)
            pool.close()
            self.assertEqual(len(recorder.calls), length)

    def test_firewall_precedes_interfaces_and_host_default_is_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            recorder = Recorder()
            with self.make(root, recorder) as pool:
                pool.start(CONFIG)
                commands = [argv for argv, _ in recorder.calls]
                firewall = next(i for i, argv in enumerate(commands) if 'ip6tables-legacy-restore' in argv)
                creation = next(i for i, argv in enumerate(commands) if 'veth' in argv)
                self.assertLess(firewall, creation)
                default = [argv for argv in commands if 'default' in argv]
                self.assertEqual(len(default), 1)
                self.assertEqual(default[0][:3], ['ip', '-n', pool.namespace])

    def test_every_command_failure_rolls_back_created_resources(self):
        with tempfile.TemporaryDirectory() as root:
            recorder = Recorder()
            with self.make(root, recorder) as pool:
                pool.start(CONFIG)
                count = len(recorder.calls)
            for failure in range(1, count + 1):
                with self.subTest(failure=failure):
                    pool = self.make(root, Recorder(fail_at=failure))
                    with self.assertRaises(NetworkError):
                        pool.start(CONFIG)
                    self.assertEqual(pool.state, 'closed')
                    self.assertEqual(pool._undo, [])
                    self.assertEqual(list(Path(root).iterdir()), [])

    def test_conflicting_host_route_refuses_before_namespace_creation(self):
        with tempfile.TemporaryDirectory() as root:
            recorder = Recorder(routes=[{'dst': '198.19.0.0/16'}])
            pool = self.make(root, recorder)
            with self.assertRaises(NetworkError):
                pool.start(CONFIG)
            self.assertEqual(len(recorder.calls), 1)

    def test_dns_ipv6_and_bad_input_fail_before_network_changes(self):
        with tempfile.TemporaryDirectory() as root:
            for config in [CONFIG.replace('DNS = 1.1.1.1\n', ''),
                           CONFIG.replace('0.0.0.0/0', '0.0.0.0/0, ::/0'),
                           CONFIG.replace('10.2.0.2/32', '198.19.7.2/30'),
                           CONFIG.replace('10.2.0.2/32', '127.0.0.1/32'),
                           CONFIG.replace('10.2.0.2/32', '10.2.0.2/8'),
                           CONFIG.replace('DNS = 1.1.1.1', 'DNS = 2606:4700:4700::1111'),
                           CONFIG + 'PostUp = evil\n']:
                recorder = Recorder()
                with self.assertRaises(ValueError):
                    self.make(root, recorder).start(config)
                self.assertEqual(recorder.calls, [])

    def test_approval_and_slot_validation(self):
        for kwargs in [dict(slot=0, shared_use_approved=True),
                       dict(slot=True, shared_use_approved=True),
                       dict(slot=1, shared_use_approved='true')]:
            with self.assertRaises(ValueError):
                WireGuardPool('/trusted/wg', **kwargs)

    def test_cleanup_failure_is_reported_and_retryable(self):
        with tempfile.TemporaryDirectory() as root:
            recorder = Recorder()
            pool = self.make(root, recorder)
            pool.start(CONFIG)
            recorder.fail_at = len(recorder.calls) + 1
            with self.assertRaises(NetworkError):
                pool.close()
            self.assertEqual(pool.state, 'cleanup_failed')
            self.assertGreater(len(pool._undo), 1)
            pool.close()
            self.assertEqual(pool.state, 'closed')
