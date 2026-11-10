import threading
import time
import unittest

from scripts.egress_control import Controller
from scripts.egress_sessions import Evidence, Sessions
from scripts.egress_supervisor import Supervisor


class Plane:
    def __init__(self): self.active = set(); self.blocked = False
    def install(self, lease): self.active.add(lease.token)
    def revoke(self, token): self.active.discard(token)
    def fail_closed(self): self.active.clear(); self.blocked = True


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.sessions = Sessions(clock=lambda: self.now)
        for pool in ['de', 'fr']:
            self.sessions.register(pool, pool.upper(), 'test_fixture', 'wireguard', True)
        self.plane = Plane()
        self.controller = Controller(self.sessions, self.plane, {'alice': 'A'*43, 'bob': 'B'*43})
        self.supervisor = None
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        if self.supervisor: self.supervisor.close()

    def evidence(self, country, lifetime=60):
        return Evidence(country, True, True, True, True, True, self.now+lifetime)

    def setup_probes(self, de=None, fr=None):
        self.supervisor = Supervisor(self.controller, {
            'de': de or (lambda cancel: self.evidence('DE')),
            'fr': fr or (lambda cancel: self.evidence('FR'))}, interval=10, timeout=3)
        return self.supervisor

    def drain(self, count=2):
        deadline = time.monotonic()+3
        while self.supervisor.results.qsize() < count and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertGreaterEqual(self.supervisor.results.qsize(), count)
        self.supervisor.tick()

    def test_successful_health_issues_only_measured_pool(self):
        supervisor = self.setup_probes(); supervisor.tick(); self.drain()
        lease = self.controller.connect('alice', 'A'*43, 'DE')
        self.assertIn(lease.token, self.plane.active)
        self.assertEqual(supervisor.states, {'de': 'healthy', 'fr': 'healthy'})

    def test_one_pool_failure_revokes_only_its_existing_sessions(self):
        fail = threading.Event()
        def probe(cancel):
            if fail.is_set(): raise OSError('private provider credential must not escape')
            return self.evidence('DE')
        supervisor = self.setup_probes(de=probe); supervisor.tick(); self.drain()
        de = self.controller.connect('alice', 'A'*43, 'DE')
        fr = self.controller.connect('bob', 'B'*43, 'FR')
        fail.set(); self.now += 10; supervisor.tick(); self.drain()
        self.assertNotIn(de.token, self.plane.active)
        self.assertIn(fr.token, self.plane.active)
        self.assertEqual(supervisor.states['de'], 'probe_failed')
        with self.assertRaises(ValueError): self.sessions.issue('DE')

    def test_timeout_cancels_worker_and_never_accepts_its_late_success(self):
        calls = []
        def blocked(cancel):
            calls.append(cancel)
            self.release.wait(3)
            return self.evidence('DE')
        supervisor = self.setup_probes(de=blocked); supervisor.tick(); self.drain(1)
        self.now += 4; supervisor.tick()
        self.assertTrue(calls[0].is_set())
        self.assertEqual(supervisor.states['de'], 'probe_timeout')
        self.now += 30
        for _ in range(20): supervisor.tick()
        self.assertEqual(len(calls), 1, 'Hung workers must not be multiplied')
        self.release.set()
        self.drain(1)  # the late DE result; FR may already have been drained
        self.assertFalse(self.sessions.pools['de']['ready'])

    def test_expired_evidence_is_revoked_while_probe_is_blocked(self):
        block = threading.Event()
        def probe(cancel):
            if block.is_set(): self.release.wait(3)
            return self.evidence('DE', 12)
        supervisor = self.setup_probes(de=probe); supervisor.tick(); self.drain()
        lease = self.controller.connect('alice', 'A'*43, 'DE')
        block.set(); self.now += 10; supervisor.tick()
        self.now += 2; supervisor.tick()
        self.assertNotIn(lease.token, self.plane.active)

    def test_wrong_country_and_expired_evidence_rejected(self):
        supervisor = self.setup_probes(de=lambda c: self.evidence('FR'), fr=lambda c: self.evidence('FR', -1))
        supervisor.tick(); self.drain()
        self.assertEqual(supervisor.states, {'de': 'evidence_rejected', 'fr': 'evidence_rejected'})
        self.assertFalse(any(p['ready'] for p in self.sessions.pools.values()))

    def test_shutdown_revokes_and_prevents_restarting(self):
        supervisor = self.setup_probes(); supervisor.tick(); self.drain()
        self.controller.connect('alice', 'A'*43, 'DE')
        supervisor.close(); supervisor.tick()
        self.assertTrue(self.plane.blocked)
        self.assertFalse(self.plane.active)
        with self.assertRaises(ValueError): self.controller.connect('bob', 'B'*43, 'FR')

    def test_invalid_scheduling_and_unprovisioned_probes_rejected(self):
        probes = {pool: lambda c: None for pool in ['de', 'fr']}
        for settings in [{'interval': 0}, {'interval': float('nan')}, {'timeout': 40}]:
            with self.assertRaises(ValueError): Supervisor(self.controller, probes, **settings)
        with self.assertRaises(ValueError): Supervisor(self.controller, {'unknown': lambda c: None})

    def test_stopped_owner_loop_cleans_up_without_starting_workers(self):
        supervisor = self.setup_probes()
        stopped = threading.Event(); stopped.set()
        supervisor.run(stopped, max_seconds=1)
        self.assertTrue(self.plane.blocked)
        self.assertFalse(supervisor.pending)
