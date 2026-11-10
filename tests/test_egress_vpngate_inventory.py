import base64
import json
import ssl
import unittest
from unittest.mock import patch

from scripts.egress_vpngate_inventory import inspect


HEADER = '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\n'


class VPNGateInventoryTests(unittest.TestCase):
    def setUp(self):
        cert = ssl.DER_cert_to_PEM_cert(ssl.create_default_context().get_ca_certs(binary_form=True)[0])
        def profile(ip, proto):
            value = f'client\ndev tun\nproto {proto}\nremote {ip} 443\nauth SHA1\n<ca>\n{cert}</ca>\n'
            return base64.b64encode(value.encode()).decode()
        self.tcp = profile('8.8.8.8', 'tcp')
        self.udp = profile('1.1.1.1', 'udp')

    def test_snapshot_counts_are_separate_from_usable_and_do_not_leak_profiles(self):
        row = f'a,8.8.8.8,JP,{self.tcp}\n'
        text = HEADER + row * 2 + f'b,1.1.1.1,JP,{self.udp}\n' + 'c,9.9.9.9,DE,broken\n*\n'
        report = inspect(text, ['JP', 'DE', 'FR'])
        self.assertEqual(report['countries']['JP']['advertised_unique_ingress_ips'], 2)
        self.assertEqual(report['countries']['JP']['inspected_unique_ingress_ips'], 2)
        self.assertEqual(report['countries']['JP']['accepted_profiles'], {'tcp': 1, 'udp': 1})
        self.assertEqual(report['countries']['DE']['rejected_profiles'], 1)
        self.assertEqual(report['countries']['FR']['advertised_unique_ingress_ips'], 0)
        self.assertEqual(report['verified_exits'], 0)
        self.assertFalse(report['udp_capability_tested'])
        serialized = json.dumps(report)
        for secret in (self.tcp, self.udp, '8.8.8.8', '1.1.1.1', 'broken'):
            self.assertNotIn(secret, serialized)

    def test_caps_inspections_not_advertised_count(self):
        rows = ''.join(f'a,{ip},JP,{self.tcp}\n' for ip in ['8.8.8.8', '1.1.1.1', '9.9.9.9'])
        report = inspect(HEADER + rows, ['JP'], per_country=1)
        self.assertEqual(report['countries']['JP']['advertised_unique_ingress_ips'], 3)
        self.assertEqual(report['inspected_total'], 1)

    def test_rejects_invalid_and_conflicting_snapshots_and_budgets(self):
        for text in ['bad', HEADER + 'a,8.8.8.8,JP,x\nb,8.8.8.8,DE,x\n']:
            with self.assertRaises(ValueError):
                inspect(text, ['JP', 'DE'])
        for kw in [{'per_country': True}, {'per_country': 6}, {'total': 0}]:
            with self.assertRaises(ValueError):
                inspect(HEADER, ['JP'], **kw)
        with patch('scripts.egress_catalog.MAX_ROWS', 1):
            with self.assertRaises(ValueError):
                inspect(HEADER + 'a,8.8.8.8,JP,x\nb,1.1.1.1,JP,x\n', ['JP'])

    def test_malformed_directive_rejected_instead_of_crashing(self):
        profile = base64.b64decode(self.tcp).decode() + '""\n'
        encoded = base64.b64encode(profile.encode()).decode()
        report = inspect(HEADER + f'a,8.8.8.8,JP,{encoded}\n', ['JP'])
        self.assertEqual(report['countries']['JP']['rejected_profiles'], 1)


if __name__ == '__main__':
    unittest.main()
