import ssl
import unittest
import subprocess
import tempfile
from pathlib import Path
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

    def test_route_hints_are_stripped_and_device_name_normalized(self):
        result = sanitize(self.config.replace('dev tun', 'dev tun1') +
                          'pull\nredirect-gateway def1\nroute-delay 2\nfast-io\n')
        self.assertIn('dev tun\n', result['config'])
        self.assertNotIn('\nredirect-gateway', result['config'])
        self.assertNotIn('\nroute-delay', result['config'])
        self.assertIn('route-noexec', result['config'])
        self.assertIn('auth SHA256', result['config'])

    def test_inline_client_certificate_key_pair_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            cert, key = Path(directory) / 'cert.pem', Path(directory) / 'key.pem'
            subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=nyx-test-only'], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            text = self.config + '<cert>\n' + cert.read_text() + '</cert>\n<key>\n' + key.read_text() + '</key>\n'
            self.assertIn('<cert>', sanitize(text)['config'])
            padded = text.replace('<key>\n', '<key>\n\n').replace('</key>', '\n\n</key>')
            self.assertIn('<key>\n-----BEGIN ', sanitize(padded)['config'])
            with self.assertRaises(ValueError):
                sanitize(text.replace(key.read_text().strip(), 'invalid-key'))
        with self.assertRaises(ValueError):
            sanitize(self.config + '<key>\ninvalid\n</key>\n')

    def test_tcp_client_alias_is_canonicalized_without_server_mode(self):
        result = sanitize(self.config.replace('proto udp', 'proto tcp'))
        self.assertEqual(result['transport'], 'tcp')
        self.assertIn('proto tcp-client\n', result['config'])
        with self.assertRaises(ValueError):sanitize(self.config.replace('proto udp', 'proto tcp-server'))

    def test_explicit_aead_mode_discards_only_legacy_data_mac_hints(self):
        legacy = self.config + 'auth SHA1\ncipher AES-128-CBC\n'
        with self.assertRaises(ValueError):sanitize(legacy)
        result = sanitize(legacy, aead_only=True)
        self.assertEqual(result['cipher_policy'], 'aead_only_no_fallback')
        self.assertIn('data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305', result['config'])
        self.assertIn('auth SHA256', result['config'])
        self.assertIn('remote-cert-tls server', result['config'])
        self.assertIn('tls-version-min 1.2', result['config'])
        for removed in ['SHA1', 'CBC', 'data-ciphers-fallback']:
            self.assertNotIn(removed, result['config'])

    def test_aead_mode_does_not_weaken_tls_or_control_channel(self):
        for extra in ['auth MD5\n', 'tls-version-min 1.0\n', 'cipher BF-CBC\n',
                      'data-ciphers-fallback AES-128-CBC\n',
                      'auth SHA1\n<tls-auth>\ninvalid\n</tls-auth>\n']:
            with self.assertRaises(ValueError):sanitize(self.config + extra, aead_only=True)
        with self.assertRaises(ValueError):sanitize(self.config, aead_only='yes')

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
