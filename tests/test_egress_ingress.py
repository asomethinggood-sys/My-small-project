"""Real sockets, not mocked flows. Synthetic origins are explicitly not countries."""
import socket
import socketserver
import threading
import time
import unittest
from scripts.egress_control import Controller
from scripts.egress_ingress import LocalIngressPlane
from scripts.egress_sessions import Sessions, Evidence


class Echo(socketserver.BaseRequestHandler):
    def handle(self):
        try:
            while True:
                data = self.request.recv(16384)
                if not data:
                    break
                self.request.sendall(data)
        except OSError:
            pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


class IngressTests(unittest.TestCase):
    def setUp(self):
        self.origin = Server(('127.0.0.1', 0), Echo)
        threading.Thread(target=self.origin.serve_forever, daemon=True).start()
        self.sessions = Sessions()
        for pool, country in [('de', 'DE'), ('fr', 'FR')]:
            self.sessions.register(pool, country, 'fixture', 'wireguard', True)
            self.sessions.mark_ready(pool, Evidence(country, True, True, True, True, True, time.monotonic()+60),
                                     ticket=self.sessions.begin_probe(pool))
        self.plane = LocalIngressPlane({'de': self.origin.server_address, 'fr': self.origin.server_address})
        self.key = 'A' * 43
        self.control = Controller(self.sessions, self.plane, {'alice': self.key, 'bob': 'B'*43})
        self.sockets = []
    def tearDown(self):
        self.control.close()
        for sock in self.sockets:
            sock.close()
        self.origin.shutdown()
        self.origin.server_close()
    def connect(self, owner='alice', key=None, country='DE'):
        lease = self.control.connect(owner, key or self.key, country)
        sock = socket.create_connection(self.plane.endpoint(lease.token), timeout=2)
        sock.settimeout(2)
        self.sockets.append(sock)
        sock.sendall(b'positive control')
        self.assertEqual(sock.recv(100), b'positive control')
        return lease, sock
    def assert_closed(self, sock):
        try:
            data = sock.recv(1)
            self.assertEqual(data, b'')
        except (ConnectionResetError, BrokenPipeError):
            pass
    def test_revoke_closes_existing_flow_not_just_new_connections(self):
        lease, sock = self.connect()
        endpoint = self.plane.endpoint(lease.token)
        self.control.disconnect('alice', self.key, lease.token)
        self.assert_closed(sock)
        with self.assertRaises(OSError): socket.create_connection(endpoint, timeout=.3)
    def test_failure_does_not_close_other_users_pool(self):
        _, a = self.connect()
        _, b = self.connect('bob', 'B'*43, 'FR')
        self.control.pool_failed('de')
        self.assert_closed(a)
        b.sendall(b'still alive')
        self.assertEqual(b.recv(100), b'still alive')
    def test_transport_independently_enforces_expiry(self):
        # Deliberately do not call Controller.sweep; transport must self-expire.
        self.sessions.mark_ready('de', Evidence('DE', True, True, True, True, True, time.monotonic()+.5),
                                 ticket=self.sessions.begin_probe('de'))
        _, sock = self.connect()
        self.assert_closed(sock)
    def test_shutdown_closes_all_existing_flows(self):
        _, sock = self.connect()
        self.plane.fail_closed()
        self.assert_closed(sock)
        with self.assertRaises(ValueError): self.control.connect('bob', 'B'*43, 'FR')
    def test_large_payload_and_half_close(self):
        _, sock = self.connect()
        payload = b'nyx' * 50000
        # Concurrent reader avoids the client itself creating a backpressure deadlock.
        received = bytearray()
        def receive():
            while True:
                data = sock.recv(16384)
                if not data: break
                received.extend(data)
        thread = threading.Thread(target=receive)
        thread.start()
        sock.sendall(payload)
        sock.shutdown(socket.SHUT_WR)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(received, payload)
    def test_phone_parallel_flows_do_not_exhaust_four_connection_budget(self):
        lease, _ = self.connect()
        # Background push, DoH and browser sockets coexist on a real phone.
        for index in range(16):
            sock = socket.create_connection(self.plane.endpoint(lease.token), timeout=2)
            self.sockets.append(sock)
            sock.settimeout(2)
            payload = ('flow-%d' % index).encode()
            sock.sendall(payload)
            self.assertEqual(sock.recv(100), payload)
        self.control.disconnect('alice', self.key, lease.token)
        for sock in self.sockets: self.assert_closed(sock)

    def test_explicit_flow_budget_still_rejects_excess_connections(self):
        self.plane.max_flows = 1
        lease, first = self.connect()
        extra = socket.create_connection(self.plane.endpoint(lease.token), timeout=2)
        self.sockets.append(extra)
        extra.settimeout(2)
        self.assert_closed(extra)
        first.sendall(b'not displaced')
        self.assertEqual(first.recv(100), b'not displaced')

    def test_direct_gateway_stream_is_tracked_and_revoked(self):
        lease, _ = self.connect()
        client, incoming = socket.socketpair()
        self.sockets.extend([client, incoming])
        with self.plane.open_stream(lease.token, lease.generation, incoming) as outgoing:
            outgoing.sendall(b'one relay')
            self.assertEqual(outgoing.recv(100), b'one relay')
            self.assertEqual(self.plane.entries[lease.token]['active'], 2)
            self.control.disconnect('alice', self.key, lease.token)
            client.settimeout(2)
            self.assert_closed(client)
            self.assertEqual(outgoing.fileno(), -1)

    def test_direct_gateway_stream_uses_shared_quota_and_generation(self):
        lease, _ = self.connect()
        a, b = socket.socketpair(); self.sockets.extend([a,b])
        with self.assertRaises(ValueError):
            with self.plane.open_stream(lease.token, lease.generation+1, b): pass
        self.plane.max_flows = 1
        with self.assertRaises(ValueError):
            with self.plane.open_stream(lease.token, lease.generation, b): pass
        self.assertEqual(self.plane.entries[lease.token]['active'], 1)

    def test_public_or_privileged_destinations_rejected(self):
        for endpoint in [('8.8.8.8',18888),('127.0.0.1',22),('::1',18888)]:
            with self.assertRaises(ValueError): LocalIngressPlane({'x': endpoint})


if __name__ == '__main__': unittest.main()
