import unittest
from scripts.egress_sources import SameSiteRedirect
from scripts.egress_xray import configurations
import urllib.request


class SourceBoundaryTests(unittest.TestCase):
    def test_rejects_cross_site_and_insecure_redirects(self):
        request = urllib.request.Request('https://www.vpnbook.com/freevpn/openvpn')
        for url in ['http://www.vpnbook.com/a', 'https://other.example/a',
                    'https://user:pass@www.vpnbook.com/a']:
            with self.assertRaises(ValueError):
                SameSiteRedirect().redirect_request(request, None, 302, '', {}, url)

    def test_same_site_redirect_allowed(self):
        request = urllib.request.Request('https://www.vpnbook.com/a')
        result = SameSiteRedirect().redirect_request(request, None, 302, '', {}, 'https://www.vpnbook.com/b')
        self.assertEqual(result.full_url, 'https://www.vpnbook.com/b')


class XrayPoolConfigTests(unittest.TestCase):
    def test_internal_ingress_and_udp_enabled(self):
        server, client = configurations('198.19.7.2', '12345678-1234-4234-8234-123456789abc', '/' + 'a' * 32)
        self.assertEqual(server['inbounds'][0]['listen'], '198.19.7.2')
        self.assertEqual(server['inbounds'][0]['port'], 18888)
        self.assertTrue(client['inbounds'][0]['settings']['udp'])
        self.assertEqual(server['outbounds'][0]['protocol'], 'freedom')
        self.assertEqual(client['inbounds'][0]['listen'], '127.0.0.1')

    def test_rejects_bad_identity_and_paths(self):
        for identity, path in [('bad', '/' + 'a'*32),
                               ('12345678-1234-4234-8234-123456789abc', '/user/path')]:
            with self.assertRaises(ValueError):
                configurations('198.19.7.2', identity, path)
