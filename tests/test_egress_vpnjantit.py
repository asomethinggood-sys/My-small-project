import json
import unittest

from scripts.egress_vpnjantit import official_slug, parse_directory


def card(country, slug, state='Available', free='FREE', transports='TCP/UDP'):
    return (f'<h2><b>{free} OpenVPN {country} 1</b></h2><span>{state}</span>'
            f'<li>{slug}.vpnjantit.com</li><li>Port 992,1194 ({transports})</li>'
            f'<a href="/download-openvpn.php?server={slug}">Download</a>'
            f'<a href="/create-free-account?server={slug}&amp;type=OpenVPN">Create</a>')


class JantitTests(unittest.TestCase):
    def test_country_counts_and_dedup_never_return_credentials(self):
        text = card('Germany','gr1') * 2 + card('France','fr1') + card('Japan','jp1')
        rows = parse_directory(text, {'DE','FR'})
        self.assertEqual(len(rows), 2)
        self.assertEqual({r['country'] for r in rows}, {'DE','FR'})
        self.assertTrue(all(r['advertised_tcp_udp'] for r in rows))
        self.assertTrue(all(r['status'] == 'discovered_unverified' for r in rows))
        self.assertNotIn('gr1', json.dumps(rows))

    def test_bad_endpoints_premium_and_unknown_are_ignored(self):
        text = (card('Germany','gr1',free='PREMIUM') + card('Other','other1')
                + card('Germany','evil1').replace('evil1.vpnjantit.com', 'evil.example'))
        # Recognizable free cards exist, but none pass the identity checks.
        self.assertEqual(parse_directory(text, {'DE'}), [])

    def test_conflicting_country_and_invalid_page_fail_closed(self):
        with self.assertRaises(ValueError): parse_directory('<html>challenge</html>', {'DE'})
        with self.assertRaises(ValueError): parse_directory(card('Germany','gr1') + card('France','gr1'), {'DE','FR'})

    def test_requires_matching_official_download_and_account_links(self):
        text = card('Germany','gr1').replace('server=gr1&amp;type=OpenVPN','server=gr2&amp;type=OpenVPN')
        self.assertEqual(parse_directory(text, {'DE'}), [])
        for href in ['http://www.vpnjantit.com/download-openvpn.php?server=gr1',
                     'https://evil.example/download-openvpn.php?server=gr1',
                     '/download-openvpn.php?server=gr1&server=gr2',
                     '/download-openvpn.php?server=../gr1']:
            self.assertIsNone(official_slug(href, '/download-openvpn.php'))

    def test_catalog_merges_provider_counts_without_selectability(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts import egress_catalog
        with tempfile.TemporaryDirectory() as root:
            fixture = Path(root) / 'directory.csv'
            fixture.write_text('*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\na,8.8.8.8,DE,x\n')
            output = Path(root) / 'out.json'
            with patch('sys.argv', ['catalog', '--fixture', str(fixture), '--vpnjantit-live', '--output', str(output)]), \
                 patch('scripts.egress_vpnjantit.fetch_directory', return_value=card('Germany', 'gr1')):
                self.assertEqual(egress_catalog.main(), 0)
            data = json.loads(output.read_text())
            country = next(row for row in data['countries'] if row['country'] == 'DE')
            self.assertEqual(country['discovered_servers'], 2)
            self.assertEqual(country['discovered_providers'], 2)
            self.assertFalse(country['selectable'])
            self.assertEqual(country['verified_servers'], 0)
            entry = next(e for e in country['exits'] if e['provider'] == 'vpnjantit')
            self.assertEqual(entry['advertised_endpoints'], 1)
            self.assertEqual(entry['advertised_tcp_and_udp_servers'], 1)
            self.assertEqual(country['advertised_tcp_and_udp_servers'], 1)

    def test_independent_failure_keeps_other_provider_and_nonzero_status(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from scripts import egress_catalog
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'out.json'
            with patch('sys.argv', ['catalog', '--live', '--vpnjantit-live', '--output', str(output)]), \
                 patch('scripts.egress_catalog.fetch_directory', side_effect=OSError('not logged')), \
                 patch('scripts.egress_vpnjantit.fetch_directory', return_value=card('Germany', 'gr1')):
                self.assertEqual(egress_catalog.main(), 1)
            data = json.loads(output.read_text())
            self.assertEqual([s['status'] for s in data['sources']], ['fetch_or_parse_failed', 'fetched'])
            self.assertEqual(len(data['observations']), 1)
            self.assertFalse(any(country['selectable'] for country in data['countries']))
            self.assertNotIn('not logged', output.read_text())

    def test_page_status_is_not_verification(self):
        item = parse_directory(card('Germany', 'gr1', state='Offline', transports='TCP'), {'DE'})[0]
        self.assertFalse(item['provider_reports_available'])
        self.assertFalse(item['advertised_tcp_udp'])
        self.assertEqual(item['status'], 'discovered_unverified')


if __name__ == '__main__': unittest.main()
