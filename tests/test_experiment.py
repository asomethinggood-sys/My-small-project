import unittest
from unittest.mock import patch
import subprocess
from scripts.experiment import cloudflared_command, probe, early_data_candidate


class ExperimentTests(unittest.TestCase):
    def test_transport_selection(self):
        for protocol in ('quic', 'http2', 'auto'):
            cmd = cloudflared_command(protocol, 20241)
            self.assertEqual(cmd[cmd.index('--protocol') + 1], protocol)
            self.assertIn('127.0.0.1:20241', cmd)
            self.assertIn('http://127.0.0.1:18888', cmd)
        with self.assertRaises(ValueError):
            cloudflared_command('quic; evil', 20241)

    def test_probe_requires_http_success_and_curl_success(self):
        for code, body, expected in [(0, '200', True), (0, '502', False), (28, '200', False)]:
            with patch('scripts.experiment.subprocess.run', return_value=subprocess.CompletedProcess([], code, body)) as run:
                self.assertEqual(probe('socks5h://127.0.0.1:10809'), expected)
                cmd = run.call_args.args[0]
                self.assertNotIn('--insecure', cmd)
                self.assertIn('socks5h://127.0.0.1:10809', cmd)

    def test_early_data_is_client_only_and_url_encoded(self):
        from urllib.parse import urlsplit, parse_qs
        client = {'outbounds': [{'streamSettings': {'wsSettings': {'path': '/abc'}}}]}
        ed, uri = early_data_candidate(client, 'vless://id@vpn.example.com:443?type=ws&path=%2Fabc#Test')
        self.assertEqual(client['outbounds'][0]['streamSettings']['wsSettings']['path'], '/abc')
        self.assertEqual(ed['outbounds'][0]['streamSettings']['wsSettings']['path'], '/abc?ed=2048')
        self.assertEqual(parse_qs(urlsplit(uri).query)['path'], ['/abc?ed=2048'])
        self.assertTrue(uri.endswith('#Test-early-data'))
