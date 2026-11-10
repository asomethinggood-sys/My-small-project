import base64
import contextlib
import io
import ssl
import unittest
from unittest.mock import patch

from scripts.egress_route_acceptance import test_snapshot as run_snapshot


class IssuedRouteAcceptanceTests(unittest.TestCase):
    def setUp(self):
        ca = ssl.DER_cert_to_PEM_cert(ssl.create_default_context().get_ca_certs(binary_form=True)[0])
        header = '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\n'
        rows = []
        for ip, country in [('8.8.8.8', 'KR'), ('1.1.1.1', 'KR'), ('9.9.9.9', 'JP')]:
            profile = f'client\ndev tun\nproto tcp\nremote {ip} 443\nauth SHA1\n<ca>\n{ca}</ca>\n'
            rows.append(f'a,{ip},{country},{base64.b64encode(profile.encode()).decode()}\n')
        self.text = header + ''.join(rows)

    def test_one_country_startup_retry_and_no_credentials_in_output(self):
        seen = []
        def fake_trial(ns, upstream, initial, *, acceptance_only):
            self.assertTrue(acceptance_only)
            initial['issued_route_evidence'] = {'verified_country': 'KR', 'country_verified': True, 'udp_dns_passed': True}
        def fake_probe(envelope, *, private_trial):
            seen.append(envelope['country'])
            if len(seen) == 1:
                return {'country_verified': False, 'failed_stage': 'authenticate'}
            result = {'advertised_country': 'KR', 'verified_country': 'KR', 'country_verified': True,
                      'host_main_routes_unchanged': True, 'tunnel_drop_blocked': True}
            private_trial('fake', None, result)
            return result
        output = io.StringIO()
        with patch('scripts.egress_route_acceptance.trial', fake_trial), contextlib.redirect_stdout(output):
            result = run_snapshot('KR', self.text, run_probe=fake_probe)
        self.assertEqual(seen, ['KR', 'KR'])
        self.assertTrue(result['issued_route_passed'])
        self.assertFalse(result['phone_settings_issued'])
        self.assertNotIn('profile_base64', output.getvalue())

    def test_never_switches_candidate_after_route_callback(self):
        count = []
        def fake_probe(envelope, *, private_trial):
            count.append(1)
            private_trial('fake', None, {})
            return {'country_verified': False, 'failed_stage': 'private_phone_trial'}
        with patch('scripts.egress_route_acceptance.trial'), contextlib.redirect_stdout(io.StringIO()):
            result = run_snapshot('KR', self.text, run_probe=fake_probe)
        self.assertEqual(len(count), 1)
        self.assertFalse(result['issued_route_passed'])

    def test_mismatched_route_country_is_rejected(self):
        def fake_probe(envelope, *, private_trial):
            result = {'advertised_country': 'KR', 'verified_country': 'KR', 'country_verified': True,
                      'host_main_routes_unchanged': True, 'tunnel_drop_blocked': True}
            private_trial('fake', None, result)
            result['issued_route_evidence'] = {'verified_country': 'JP', 'country_verified': True, 'udp_dns_passed': True}
            return result
        with patch('scripts.egress_route_acceptance.trial'), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(run_snapshot('KR', self.text, run_probe=fake_probe)['issued_route_passed'])

    def test_no_directory_candidates_or_unknown_target(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(run_snapshot('FR', self.text)['issued_route_passed'])
        with self.assertRaises(ValueError):
            run_snapshot('XX', self.text)

    def test_namespace_success_without_full_route_or_drop_does_not_pass(self):
        def fake_probe(envelope, *, private_trial):
            private_trial('fake', None, {})
            return {'country_verified': True, 'host_main_routes_unchanged': True}
        with patch('scripts.egress_route_acceptance.trial'), contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(run_snapshot('KR', self.text, run_probe=fake_probe)['issued_route_passed'])


if __name__ == '__main__':
    unittest.main()
