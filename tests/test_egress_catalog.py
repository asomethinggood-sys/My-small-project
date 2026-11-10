import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import egress_catalog as catalog


HEADER = '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\n'


class EgressCatalogTests(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads(Path('config/egress.json').read_text())

    def test_thirty_targets_are_not_thirty_working_exits(self):
        result = catalog.build_catalog(self.policy, [], [], now=100)
        self.assertEqual(len(result['countries']), 30)
        self.assertEqual(result['expires_at'], 1000)
        self.assertTrue(all(not row['selectable'] for row in result['countries']))

    def test_dedup_and_no_configuration_or_address_export(self):
        rows = catalog.parse_vpngate(HEADER + 'a,8.8.8.8,DE,SECRET\nb,8.8.8.8,DE,SECRET\n*\n', {'DE'})
        self.assertEqual(len(rows), 1)
        self.assertNotIn('SECRET', json.dumps(rows))
        self.assertNotIn('8.8.8.8', json.dumps(rows))
        result = catalog.build_catalog(self.policy, rows, [], now=1)
        germany = next(c for c in result['countries'] if c['country'] == 'DE')
        self.assertEqual(germany['discovered_servers'], 1)
        self.assertEqual(germany['discovered_providers'], 1)
        self.assertEqual(germany['verified_servers'], 0)

    def test_private_multicast_and_invalid_addresses_rejected(self):
        text = HEADER + ''.join(f'a,{ip},DE,x\n' for ip in
                                ['127.0.0.1', '10.0.0.1', '169.254.169.254', '::1', '224.0.0.1', 'invalid'])
        self.assertEqual(catalog.parse_vpngate(text, {'DE'}), [])

    def test_unknown_country_and_missing_config_ignored(self):
        self.assertEqual(catalog.parse_vpngate(HEADER + 'a,8.8.8.8,XX,x\nb,1.1.1.1,DE,\n', {'DE'}), [])

    def test_conflicting_country_rejected(self):
        with self.assertRaises(ValueError):
            catalog.parse_vpngate(HEADER + 'a,8.8.8.8,DE,x\nb,8.8.8.8,US,x\n', {'DE', 'US'})

    def test_invalid_directory_rejected(self):
        for text in ['<html>challenge</html>', '*vpn_servers\n#HostName,IP\nx,8.8.8.8\n']:
            with self.assertRaises(ValueError):
                catalog.parse_vpngate(text, {'DE'})

    def test_size_and_row_limits(self):
        with patch.object(catalog, 'MAX_BYTES', 10):
            with self.assertRaises(ValueError):
                catalog.parse_vpngate(HEADER, {'DE'})
        with patch.object(catalog, 'MAX_ROWS', 1):
            with self.assertRaises(ValueError):
                catalog.parse_vpngate(HEADER + 'a,8.8.8.8,DE,x\nb,1.1.1.1,DE,x', {'DE'})

    def test_approval_cannot_turn_discovery_into_verified_exit(self):
        policy = copy.deepcopy(self.policy)
        policy['providers'][0]['shared_use_approved'] = True
        rows = catalog.parse_vpngate(HEADER + 'a,8.8.8.8,DE,x', {'DE'})
        result = catalog.build_catalog(policy, rows, [], now=1)
        self.assertFalse(any(c['selectable'] for c in result['countries']))

    def test_invalid_policy_rejected(self):
        for change in [{'catalog_ttl_seconds': 0}, {'target_countries': ['DE'] * 30}]:
            with self.assertRaises(ValueError):
                catalog.validate_policy(dict(self.policy, **change))

    def test_advertisements_are_deduplicated_and_never_promoted(self):
        result = catalog.build_catalog(self.policy, [], [], now=1000)
        sources = {'generated_at': 1000, 'sources': [
            {'source': name, 'status': 'fetched', 'advertised_endpoints':
             ['de20.vpnbook.com', 'de20.vpnbook.com', 'de220.vpnbook.com', 'evil.example']}
            for name in ['vpnbook-openvpn', 'vpnbook-wireguard']]}
        catalog.attach_advertisements(result, sources)
        germany = next(row for row in result['countries'] if row['country'] == 'DE')
        self.assertEqual(germany['advertised_endpoints'], 2)
        self.assertEqual(germany['advertised_providers'], 1)
        self.assertEqual(germany['discovered_servers'], 0)
        self.assertFalse(germany['selectable'])

    def test_stale_advertisements_are_not_counted(self):
        result = catalog.build_catalog(self.policy, [], [], now=2000)
        catalog.attach_advertisements(result, {'generated_at': 1, 'sources': [
            {'source': 'vpnbook-openvpn', 'status': 'fetched', 'advertised_endpoints': ['de20.vpnbook.com']}]})
        self.assertTrue(all(row['advertised_endpoints'] == 0 for row in result['countries']))

    def test_atomic_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            catalog.atomic_write(path, {'version': 1})
            catalog.atomic_write(path, {'version': 2})
            self.assertEqual(json.loads(path.read_text()), {'version': 2})
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_redirects_fail_closed(self):
        with self.assertRaises(ValueError):
            catalog.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://example.com')

    def test_failed_refresh_replaces_stale_output_and_returns_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog.json'
            path.write_text('{"stale":true}')
            with patch('sys.argv', ['catalog', '--live', '--output', str(path)]), patch.object(
                    catalog, 'fetch_directory', side_effect=OSError('secret')):
                self.assertEqual(catalog.main(), 1)
            output = json.loads(path.read_text())
            self.assertEqual(output['observations'], [])
            self.assertNotIn('secret', path.read_text())
            self.assertEqual(output['sources'][0]['status'], 'fetch_or_parse_failed')
