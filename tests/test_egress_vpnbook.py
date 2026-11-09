import io
import ssl
import unittest
from unittest.mock import patch
import zipfile
from scripts.egress_vpnbook import Page, inspect_bundle


def bundle(text, name='../../udp53.ovpn'):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr(name, text)
    return stream.getvalue()


class VPNBookInspectionTests(unittest.TestCase):
    def test_only_official_https_german_archives(self):
        page = Page()
        page.feed('''<a href="/free-openvpn-account/VPNBook-DE20.zip">DE</a>
        <a href="http://www.vpnbook.com/DE20.zip">bad</a>
        <a href="https://evil.example/DE20.zip">bad</a>
        <script>Username: fake Password: secret</script>''')
        self.assertEqual(len(page.links), 1)
        self.assertNotIn('secret', ''.join(page.words))

    def test_reads_without_extracting_and_rebuilds_remote_without_joining_lines(self):
        cert = ssl.DER_cert_to_PEM_cert(ssl.create_default_context().get_ca_certs(binary_form=True)[0])
        text = ('client\ndev tun\nremote de20.vpnbook.com 25000\nproto udp\n'
                'auth-user-pass\n<ca>\n' + cert + '</ca>\n')
        with patch('scripts.egress_vpnbook.socket.getaddrinfo', return_value=[(2, 2, 17, '', ('8.8.8.8', 25000))]):
            result = inspect_bundle(bundle(text))
        self.assertEqual(result['status'], 'sanitized_unverified')
        self.assertFalse(result['connectable'])
        self.assertNotIn('config', result)
        self.assertNotIn('8.8.8.8', str(result))

    def test_rejects_unrelated_endpoint_without_resolution(self):
        with patch('scripts.egress_vpnbook.socket.getaddrinfo') as resolve:
            result = inspect_bundle(bundle('remote evil.example 1234\n'))
        self.assertEqual(result['status'], 'unexpected_endpoint')
        resolve.assert_not_called()

    def test_rejects_oversized_archive_budget(self):
        with patch('scripts.egress_vpnbook.LIMIT', 10):
            with self.assertRaises(ValueError):
                inspect_bundle(bundle('x' * 20))

    def test_reports_unsupported_transport_bundle(self):
        result = inspect_bundle(bundle('client', name='tcp443.ovpn'))
        self.assertEqual(result['status'], 'no_udp_profile')
