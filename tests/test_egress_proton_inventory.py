import json
import unittest

from scripts.egress_proton_inventory import inspect


def row(ident, ip, country='DE', entry=None, tier=0, status=1):
    return {'ID': ident, 'ExitCountry': country, 'EntryCountry': entry or country,
            'Tier': tier, 'Status': status, 'Servers': [{'EntryIP': ip}]}


class ProtonInventoryTests(unittest.TestCase):
    def test_logical_servers_and_unique_ips_are_distinct(self):
        payload = {'LogicalServers': [row('one', '8.8.8.8'), row('two', '8.8.8.8', tier=1),
                                      row('three', '1.1.1.1', 'FR'), row('multi', '9.9.9.9', 'FR', entry='US')]}
        result = inspect(payload, {'DE','FR'})
        self.assertEqual(result['logical_servers'], 3)
        self.assertEqual(result['unique_ingress_ips'], 2)
        self.assertEqual(result['countries']['DE']['free_tier_logical_servers'], 1)
        self.assertEqual(result['verified_exits'], 0)
        self.assertFalse(result['udp_capability_tested'])
        for secret in ['8.8.8.8', '1.1.1.1']:
            self.assertNotIn(secret, json.dumps(result))

    def test_rejects_conflicts_and_schema_errors(self):
        for payload in [{}, {'LogicalServers': 'bad'},
                        {'LogicalServers': [row('one', '8.8.8.8'), row('one', '1.1.1.1', 'FR')]},
                        {'LogicalServers': [row('one', '8.8.8.8'), row('two', '8.8.8.8', 'FR')]}]:
            with self.assertRaises(ValueError): inspect(payload, {'DE','FR'})


if __name__ == '__main__': unittest.main()
