import unittest

from scripts.egress_openvpn_probe import assess_responses, bind_explicit_country


class ExactCountryEvidenceTests(unittest.TestCase):
    def observations(self):
        return {0: {'ip': '8.8.8.8'},
                1: {'ip': '8.8.8.8', 'country_iso': 'JP'},
                4: {'ip': '8.8.8.8', 'country': 'JP'}}

    def test_self_location_is_not_explicit_evidence(self):
        observations = self.observations()
        bind_explicit_country(observations, 'JP', None)
        self.assertIn(5, observations)
        self.assertNotIn(4, observations)
        self.assertFalse(assess_responses(observations, 'JP', require_conflict_source=True)['country_verified'])

    def test_lookup_is_bound_to_quorum_ip_and_conflict_is_preserved(self):
        observations = self.observations()
        seen = []
        def lookup(ip):
            seen.append(ip)
            return {'ip': ip, 'country': 'JP'}
        bind_explicit_country(observations, 'JP', lookup)
        self.assertEqual(seen, ['8.8.8.8'])
        self.assertTrue(assess_responses(observations, 'JP', require_conflict_source=True)['country_verified'])
        observations[5]['country'] = 'FR'
        self.assertFalse(assess_responses(observations, 'JP', require_conflict_source=True)['country_verified'])

    def test_mismatched_ip_and_failed_lookup_do_not_authorize(self):
        for lookup in [lambda _: {'ip': '1.1.1.1', 'country': 'JP'},
                       lambda _: (_ for _ in ()).throw(OSError())]:
            observations = self.observations()
            bind_explicit_country(observations, 'JP', lookup)
            self.assertFalse(assess_responses(observations, 'JP', require_conflict_source=True)['country_verified'])

    def test_conflicting_tunnel_ips_skip_lookup(self):
        observations = self.observations()
        observations[1]['ip'] = '1.1.1.1'
        seen = []
        bind_explicit_country(observations, 'JP', lambda ip: seen.append(ip))
        self.assertEqual(seen, [])
        self.assertFalse(assess_responses(observations, 'JP', require_conflict_source=True)['country_verified'])

    def test_explicit_lookup_is_not_a_second_tunnel_ip(self):
        observations = {1: {'ip': '8.8.8.8', 'country_iso': 'JP'},
                        4: {'ip': '8.8.8.8', 'country': 'JP'}}
        self.assertFalse(assess_responses(observations, 'JP', require_conflict_source=True)['country_verified'])

    def test_two_country_is_lookups_are_one_country_source(self):
        observations = {0: {'ip': '8.8.8.8'},
                        4: {'ip': '8.8.8.8', 'country': 'JP'},
                        5: {'ip': '8.8.8.8', 'country': 'JP'}}
        self.assertFalse(assess_responses(observations, 'JP', require_conflict_source=True)['country_verified'])


if __name__ == '__main__':
    unittest.main()
