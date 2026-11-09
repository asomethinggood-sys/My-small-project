import unittest
from scripts.egress_control import Controller, Denied
from scripts.egress_sessions import Sessions, Evidence


class Plane:
    def __init__(self):
        self.routes = {}
        self.install_failure = self.revoke_failure = False
        self.blocked = False
    def install(self, lease):
        self.routes[lease.token] = lease.pool
        if self.install_failure:
            raise RuntimeError('partial installation')
    def revoke(self, token):
        if self.revoke_failure:
            raise RuntimeError('partial revocation')
        self.routes.pop(token, None)
    def fail_closed(self):
        self.blocked = True
        self.routes.clear()


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.sessions = Sessions(clock=lambda: self.now)
        for pool, country in [('de', 'DE'), ('fr', 'FR')]:
            self.sessions.register(pool, country, 'fixture', 'wireguard', True)
            self.sessions.mark_ready(pool, Evidence(country, True, True, True, True, True, 200),
                                     ticket=self.sessions.begin_probe(pool))
        self.plane = Plane()
        self.a, self.b = 'A' * 43, 'B' * 43
        self.control = Controller(self.sessions, self.plane, {'alice': self.a, 'bob': self.b})
    def test_separate_users_and_countries(self):
        a = self.control.connect('alice', self.a, 'DE')
        b = self.control.connect('bob', self.b, 'FR')
        self.assertEqual(self.control.resolve('alice', self.a, a.token, a.generation), 'de')
        with self.assertRaises(Denied): self.control.resolve('bob', self.b, a.token, a.generation)
        with self.assertRaises(Denied): self.control.disconnect('bob', self.b, a.token)
        self.control.disconnect('alice', self.a, a.token)
        self.assertEqual(self.plane.routes, {b.token: 'fr'})
    def test_auth_and_missing_country_no_fallback(self):
        for owner, key in [('alice', self.b), ('unknown', self.a)]:
            with self.assertRaises(Denied): self.control.connect(owner, key, 'DE')
        with self.assertRaises(ValueError): self.control.connect('alice', self.a, 'US')
        self.assertEqual(self.plane.routes, {})
    def test_expiry_removes_actual_route(self):
        lease = self.control.connect('alice', self.a, 'DE')
        self.now = 201
        self.control.sweep()
        self.assertEqual(self.plane.routes, {})
        with self.assertRaises(Denied): self.control.resolve('alice', self.a, lease.token, lease.generation)
    def test_pool_failure_only_revokes_affected_users(self):
        self.control.connect('alice', self.a, 'DE')
        b = self.control.connect('bob', self.b, 'FR')
        self.control.pool_failed('de')
        self.assertEqual(self.plane.routes, {b.token: 'fr'})
    def test_install_failure_rolls_back_partial_route(self):
        self.plane.install_failure = True
        with self.assertRaises(Denied): self.control.connect('alice', self.a, 'DE')
        self.assertEqual(self.plane.routes, {})
        self.assertEqual(self.sessions.sessions, {})
    def test_revocation_failure_closes_plane_and_prevents_reuse(self):
        lease = self.control.connect('alice', self.a, 'DE')
        self.plane.revoke_failure = True
        with self.assertRaises(Denied): self.control.disconnect('alice', self.a, lease.token)
        self.assertTrue(self.plane.blocked)
        with self.assertRaises(Denied): self.control.connect('bob', self.b, 'FR')
    def test_quota_and_generation_binding(self):
        lease = self.control.connect('alice', self.a, 'DE')
        self.control.connect('alice', self.a, 'DE')
        with self.assertRaises(Denied): self.control.connect('alice', self.a, 'DE')
        with self.assertRaises(Denied): self.control.resolve('alice', self.a, lease.token, lease.generation + 1)
    def test_rate_limit_never_blocks_disconnect(self):
        self.control.rate = 1
        lease = self.control.connect('alice', self.a, 'DE')
        with self.assertRaises(Denied): self.control.connect('alice', self.a, 'DE')
        self.control.disconnect('alice', self.a, lease.token)
        self.now += 60
        self.control.connect('alice', self.a, 'DE')
    def test_shutdown_closes_all_flows(self):
        self.control.connect('alice', self.a, 'DE')
        self.control.close()
        self.assertTrue(self.plane.blocked)
        self.assertEqual(self.sessions.sessions, {})
    def test_rejects_weak_and_duplicate_credentials(self):
        for keys in [{'a': 'short'}, {'a': self.a, 'b': self.a}]:
            with self.assertRaises(ValueError): Controller(self.sessions, self.plane, keys)


if __name__ == '__main__': unittest.main()
