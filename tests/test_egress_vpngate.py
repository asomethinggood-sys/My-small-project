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

    def test_directory_deduplicates_and_filters_targets(self):
        row = 'vpn-test,8.8.8.8,JP,' + self.envelope['profile_base64'] + '\n'
        directory = '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\n' + row * 5
        self.assertEqual(len(candidates(directory, {'JP'})), 1)
        self.assertEqual(candidates(directory, {'DE'}), [])
        for limit in [0, 4, True]:
            with self.assertRaises(ValueError):candidates(directory, {'JP'}, limit)
        with self.assertRaises(ValueError):candidates('bad', {'JP'})
