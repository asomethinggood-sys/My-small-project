import copy
import json
from pathlib import Path
import unittest
from scripts.egress_batch import validate_plan, summarize, REQUIRED_FLAGS


class CandidateStabilityTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(Path('config/egress-experiment.json').read_text())
        self.candidate = self.plan['candidates'][0]

    def sample(self, number=1):
        return {'candidate_id': self.candidate['id'], 'round': number, 'execution': 'completed',
                'finished_at': 1000, 'report': {
                    'status': 'download_received_unverified', 'candidate_id': self.candidate['id'],
                    'server': self.candidate['server'], 'port': self.candidate['port'],
                    'live_probe': dict({flag: True for flag in REQUIRED_FLAGS},
                                       candidate_id=self.candidate['id'], endpoint_port=self.candidate['port'],
                                       status='german_exit_observed', observed_countries=['DE', 'DE'])}}

    def row(self, samples, now=1000):
        return summarize(self.plan, samples, now)['candidates'][0]

    def test_one_success_is_not_stable(self):
        row = self.row([self.sample()])
        self.assertEqual(row['successful_samples'], 1)
        self.assertFalse(row['stable_in_bounded_test'])

    def test_two_consecutive_successes_still_do_not_publish(self):
        row = self.row([self.sample(1), self.sample(2)])
        self.assertTrue(row['stable_in_bounded_test'])
        self.assertFalse(row['selectable'])
        self.assertFalse(row['shared_use_approved'])

    def test_failures_are_kept_and_break_streak(self):
        second = self.sample(2)
        second['report']['live_probe']['status'] = 'exit_unverified_or_wrong_country'
        second['report']['live_probe']['country_verified'] = False
        row = self.row([self.sample(1), second])
        self.assertEqual(row['samples'], 2)
        self.assertEqual(row['successful_samples'], 1)
        self.assertEqual(row['consecutive_successes'], 0)
        self.assertFalse(row['stable_in_bounded_test'])

    def test_duplicate_round_cannot_inflate_successes(self):
        row = self.row([self.sample(1), self.sample(1)])
        self.assertFalse(row['stable_in_bounded_test'])

    def test_stale_or_future_samples_do_not_pass(self):
        for now in [1, 2000]:
            self.assertFalse(self.row([self.sample(1), self.sample(2)], now)['stable_in_bounded_test'])

    def test_every_safety_flag_must_be_boolean_true(self):
        for flag in REQUIRED_FLAGS:
            for value in [False, 'true', 1, None]:
                with self.subTest(flag=flag, value=value):
                    second = self.sample(2)
                    second['report']['live_probe'][flag] = value
                    self.assertFalse(self.row([self.sample(1), second])['stable_in_bounded_test'])

    def test_wrong_server_port_or_country_rejected(self):
        for location, key, value in [('report', 'server', 'de220'), ('report', 'port', 25000),
                                     ('probe', 'candidate_id', 'vpnbook-de220-udp53'),
                                     ('probe', 'endpoint_port', 25000),
                                     ('probe', 'observed_countries', ['DE', 'US'])]:
            second = self.sample(2)
            target = second['report'] if location == 'report' else second['report']['live_probe']
            target[key] = value
            self.assertFalse(self.row([self.sample(1), second])['stable_in_bounded_test'])

    def test_experiment_cannot_expand_budget_or_arbitrary_endpoints(self):
        for change in [{'rounds': 3}, {'sample_timeout_seconds': 999}, {'minimum_consecutive_successes': 1}]:
            with self.assertRaises(ValueError):
                validate_plan(dict(self.plan, **change))
        plan = copy.deepcopy(self.plan)
        plan['candidates'][0]['server'] = 'attacker.example'
        with self.assertRaises(ValueError):
            validate_plan(plan)
