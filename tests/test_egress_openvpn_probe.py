import base64
import unittest
from unittest.mock import patch
from scripts.egress_openvpn_probe import connected_address, classify_log, prepare


class OpenVPNProbeBoundaryTests(unittest.TestCase):
    def test_state_requires_connected_success_and_safe_address(self):
        self.assertEqual(connected_address('>STATE:123,CONNECTED,SUCCESS,10.8.0.2,8.8.8.8,53'), '10.8.0.2')
        for line in ['123,AUTH,,,', '>INFO:state', '123,CONNECTED,FAILED,10.8.0.2']:
            self.assertIsNone(connected_address(line))
        for address in ['127.0.0.1', '169.254.169.254', '0.0.0.0', '224.0.0.1', '::1']:
            with self.assertRaises(ValueError):
                connected_address('123,CONNECTED,SUCCESS,' + address)

    def test_log_classification_does_not_return_raw_content(self):
        self.assertEqual(classify_log('user=secret\nAUTH_FAILED secret'), 'authentication_rejected')
        self.assertEqual(classify_log('VERIFY ERROR depth=1 secret'), 'certificate_verification_failed')
        self.assertNotIn('secret', classify_log('secret'))

    def test_requires_explicit_test_provider_credentials(self):
        for envelope in [{'provider': 'other', 'username': 'vpnbook', 'password': 'test'},
                         {'provider': 'vpnbook', 'username': 'other', 'password': 'test'},
                         {'provider': 'vpnbook', 'username': 'vpnbook', 'password': 'bad\nvalue'}]:
            with self.assertRaises(ValueError):
                prepare(envelope)

    def test_hostname_scope_rejected_without_arbitrary_dns(self):
        envelope = {'provider': 'vpnbook', 'username': 'vpnbook', 'password': 'test',
                    'profile_base64': base64.b64encode(b'remote attacker.example 53\n').decode()}
        with patch('scripts.egress_openvpn_probe.socket.getaddrinfo') as resolver:
            with self.assertRaises(ValueError):
                prepare(envelope)
        resolver.assert_not_called()

    def test_numeric_private_remote_rejected_before_sanitizer(self):
        envelope = {'provider': 'vpnbook', 'username': 'vpnbook', 'password': 'test',
                    'profile_base64': base64.b64encode(b'remote 169.254.169.254 53\n').decode()}
        with self.assertRaises(ValueError):
            prepare(envelope)
