import base64
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlsplit, parse_qs
from scripts.generate import generate
from scripts.measure import summarize


class GenerateTests(unittest.TestCase):
    def test_roundtrip_and_stability(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = generate('vpn.example.com', tmp)
            self.assertEqual(state, generate('vpn.example.com', tmp))
            d = Path(tmp)
            uri = (d / 'candidate-uri.txt').read_text().strip()
            u = urlsplit(uri)
            q = parse_qs(u.query)
            self.assertEqual(u.username, state['uuid'])
            self.assertEqual(u.port, 443)
            self.assertEqual(q['path'], [state['path']])
            self.assertEqual(q['sni'], [u.hostname])
            self.assertEqual(q['security'], ['tls'])
            self.assertEqual(base64.b64decode((d / 'candidate-subscription.txt').read_text()).decode(), uri)
            server = json.loads((d / 'xray.json').read_text())
            self.assertEqual(server['inbounds'][0]['listen'], '127.0.0.1')
            self.assertIn(state['path'], (d / 'Caddyfile').read_text())
            self.assertFalse((d / 'verified-uri.txt').exists())
            self.assertEqual((d / 'identity.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                generate('other.example.com', tmp)

    def test_reject_injection_and_non_hosts(self):
        for host in ['127.0.0.1', 'localhost', 'https://a.com', 'a.com:443', '*.a.com',
                     'a.com\n}', '-bad.example.com', 'a..com', 'a.com/evil']:
            with self.subTest(host=host), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    generate(host, tmp)

    def test_stats(self):
        self.assertEqual(summarize([.1, .2, .3]), {'median_ms': 200.0, 'p95_ms': 300.0})
        self.assertEqual(summarize([]), {})
