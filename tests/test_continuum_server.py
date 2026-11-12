import unittest
from scripts.continuum_server import configuration


class ContinuumServerTests(unittest.TestCase):
    def test_wire_identity_preserved_and_dns_cached(self):
        identity = 'f2222222-2222-4222-8222-222222222222'
        config = configuration(identity, '/fixture')
        inbound = config['inbounds'][0]
        self.assertEqual(inbound['listen'], '127.0.0.1')
        self.assertEqual(inbound['settings']['clients'], [{'id': identity}])
        self.assertEqual(inbound['streamSettings']['wsSettings']['path'], '/fixture')
        self.assertEqual(config['outbounds'][0]['settings']['targetStrategy'], 'UseIPv4')
        self.assertFalse(config['dns']['disableCache'])
        self.assertTrue(config['dns']['enableParallelQuery'])
        self.assertEqual(len(config['dns']['servers']), 2)
        self.assertTrue(all(s['address'].startswith('https+local://') for s in config['dns']['servers']))
        self.assertTrue(all(s['timeoutMs'] == 3000 for s in config['dns']['servers']))
        self.assertNotIn('finalRules', config['outbounds'][0]['settings'])
        self.assertEqual(config['outbounds'][0]['protocol'], 'freedom')

    def test_invalid_identity_path_and_port_rejected(self):
        identity = 'f2222222-2222-4222-8222-222222222222'
        for args in [('bad', '/fixture', 18888), (identity, '/x\nup evil', 18888),
                     (identity, '/x?ed=2048', 18888), (identity, '/x', 80),
                     (identity, '/x', True)]:
            with self.assertRaises(ValueError):configuration(*args)
