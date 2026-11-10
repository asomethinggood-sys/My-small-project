import base64
import ssl
import unittest

from scripts.egress_openvpn_probe import prepare
from scripts.egress_vpngate import candidates


class VPNGateTests(unittest.TestCase):
    def setUp(self):
        cert = ssl.DER_cert_to_PEM_cert(ssl.create_default_context().get_ca_certs(binary_form=True)[0])
        self.profile = 'client\ndev tun\nproto tcp\nremote 8.8.8.8 443\nauth SHA1\n<ca>\n' + cert + '</ca>\n'
        self.envelope = dict(provider='vpngate', country='JP', endpoint_ip='8.8.8.8',
                             profile_base64=base64.b64encode(self.profile.encode()).decode())

    def test_prepare_pins_modern_cipher_and_endpoint(self):
        parsed = prepare(self.envelope)
        self.assertEqual(parsed['transport'], 'tcp')
        self.assertFalse(parsed['credentials_required'])
        self.assertIn('data-ciphers-fallback AES-128-GCM', parsed['config'])
        self.assertNotIn('SHA1', parsed['config'])
        for extra in [dict(country=''), dict(endpoint_ip='1.1.1.1'),
                      dict(endpoint_ip='127.0.0.1'), dict(profile_base64='x' * 180001)]:
            with self.assertRaises(ValueError):
                prepare(self.envelope | extra)

    def test_rejects_interactive_credentials(self):
        encoded = base64.b64encode((self.profile + 'auth-user-pass\n').encode()).decode()
        with self.assertRaises(ValueError):
            prepare(self.envelope | dict(profile_base64=encoded))

    def test_acquisition_is_exact_and_private(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts.egress_vpngate import acquire
        row = 'vpn-test,8.8.8.8,JP,' + self.envelope['profile_base64'] + '\n'
        directory = '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\n' + row
        with tempfile.TemporaryDirectory() as root, patch('scripts.egress_catalog.fetch_directory', return_value=directory):
            path = Path(root) / 'input.json'
            acquire('JP', '8.8.8.8', path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text())['cipher_policy'], 'cbc_sha256')
            with self.assertRaises(ValueError):acquire('DE', '8.8.8.8', Path(root) / 'other')
            with self.assertRaises(ValueError):acquire('JP', '1.1.1.1', Path(root) / 'other')
            with self.assertRaises(FileExistsError):acquire('JP', '8.8.8.8', path)

    def test_current_batch_stays_in_selected_country(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts.egress_vpngate import acquire_current
        row = 'vpn-test,8.8.8.8,JP,' + self.envelope['profile_base64'] + '\n'
        directory = '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\n' + row
        with tempfile.TemporaryDirectory() as root, patch('scripts.egress_catalog.fetch_directory', return_value=directory):
            path = Path(root) / 'batch.json'
            acquire_current('JP', path)
            batch = json.loads(path.read_text())['candidates']
            self.assertEqual(len(batch), 1)
            self.assertEqual(batch[0]['country'], 'JP')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):acquire_current('DE', Path(root) / 'other')

    def test_trial_rejects_unverified_or_mismatched_country_before_network(self):
        from scripts.egress_phone_trial import trial
        from scripts.egress_openvpn_probe import ProbeError
        for evidence in [{}, dict(verified_country='JP', advertised_country='DE', provider='vpngate', country_verified=True)]:
            with self.assertRaises(ProbeError):trial('unused', None, evidence)

    def test_directory_deduplicates_and_filters_targets(self):
        row = 'vpn-test,8.8.8.8,JP,' + self.envelope['profile_base64'] + '\n'
        directory = '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\n' + row * 5
        self.assertEqual(len(candidates(directory, {'JP'})), 1)
        self.assertEqual(candidates(directory, {'DE'}), [])
        for limit in [0, 4, True]:
            with self.assertRaises(ValueError):candidates(directory, {'JP'}, limit)
        with self.assertRaises(ValueError):candidates('bad', {'JP'})
