import ssl
import unittest
from scripts.egress_openvpn import sanitize
from scripts.egress_firewall import rules, legacy_rules


class OpenVPNBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Public test certificate from the local OS trust store; no key or network.
        cert = ssl.create_default_context().get_ca_certs(binary_form=True)[0]
        cls.config = ('client\ndev tun\nproto udp\nremote 8.8.8.8 1194\n'
                      'auth-user-pass\nremote-cert-tls server\n<ca>\n'
                      + ssl.DER_cert_to_PEM_cert(cert) + '</ca>\n')

    def test_rebuilds_config_without_host_routes_or_credentials(self):
        result = sanitize(self.config)
        self.assertTrue(result['credentials_required'])
        self.assertEqual(result['transport'], 'udp')
        self.assertIn('route-noexec', result['config'])
        self.assertIn('ifconfig-noexec', result['config'])
        self.assertIn('script-security 1', result['config'])
        self.assertNotIn('auth-user-pass', result['config'])

    def test_tcp_transport_distinct_from_udp_payload_capability(self):
        result = sanitize(self.config.replace('proto udp', 'proto tcp-client'))
        self.assertEqual(result['transport'], 'tcp')
        self.assertNotIn('udp_verified', result)

    def test_rejects_scripts_plugins_files_and_push_configuration(self):
        for directive in ['up evil', 'plugin /tmp/evil.so', 'config /tmp/nested',
                          'log /tmp/file', 'management 0.0.0.0 1234', 'script-security 2',
                          'route 0.0.0.0 0.0.0.0', 'auth-user-pass /tmp/passwords',
                          'ca /tmp/ca', 'compress lzo', 'remote 1.1.1.1 443']:
            with self.subTest(directive=directive), self.assertRaises(ValueError):
                sanitize(self.config + directive + '\n')

    def test_rejects_invalid_certificate_and_tls_downgrade(self):
        for text in [self.config.replace('<ca>', '<cert>'), self.config + 'tls-version-min 1.0\n',
                     self.config + 'auth SHA1\n', self.config + 'cipher BF-CBC\n',
                     self.config.replace('-----BEGIN CERTIFICATE-----', 'invalid')]:
            with self.assertRaises(ValueError):
                sanitize(text)

    def test_rejects_unresolved_private_endpoint_and_tap(self):
        for text in [self.config.replace('8.8.8.8', '127.0.0.1'),
                     self.config.replace('8.8.8.8', 'vpn.example.com'),
                     self.config.replace('dev tun', 'dev tap'),
                     self.config.replace('1194', '99999')]:
            with self.assertRaises(ValueError):
                sanitize(text)

    def test_rejects_unclosed_or_duplicate_ca_block(self):
        for text in [self.config.replace('</ca>', ''), self.config + '<ca>\n']:
            with self.assertRaises(ValueError):
                sanitize(text)


class FirewallRulesTests(unittest.TestCase):
    def test_underlay_established_allow_is_listener_scoped(self):
        text = rules('10.200.1.1')
        self.assertIn('tcp sport 18888 ct state established accept', text)
        self.assertNotIn('\n    ct state established', text)
        self.assertIn('oifname "nyx-vpn" meta nfproto ipv4 accept', text)
        self.assertNotIn('nfproto ipv6 accept', text)

    def test_legacy_denies_ipv6_except_loopback(self):
        ipv4, ipv6 = legacy_rules('10.200.1.1')
        self.assertIn(':OUTPUT DROP', ipv4)
        self.assertIn(':OUTPUT DROP', ipv6)
        self.assertEqual(ipv6.count('-j ACCEPT'), 2)
        self.assertIn('--sport 18888', ipv4)

    def test_rejects_rule_injection_and_identical_interfaces(self):
        for kwargs in [dict(ingress='bad;evil'), dict(tunnel='nyx-in'), dict(listener_port=80)]:
            with self.assertRaises(ValueError):
                rules('10.200.1.1', **kwargs)
        with self.assertRaises(ValueError):
            rules('10.200.1.1; accept')
