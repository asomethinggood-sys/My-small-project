"""Private HTTP/WebSocket gateway for a trusted TLS-terminating connector.

No automatic deployment. Bind loopback only; never expose plaintext public APIs.
The default WS route is separate from scoped country leases. Every country path
requires an unguessable issued lease plus its generation; VLESS authentication
still happens in the isolated pool. Access logs are disabled to protect tokens.
"""
import http.server
import ipaddress
import json
import math
import re
import socket
import threading
import time
import uuid
from urllib.parse import quote, urlencode
from scripts.egress_control import Denied
from scripts.egress_stream import relay


class Gateway(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, controller, public_host, profiles, default_route=None, port=0):
        if not re.fullmatch(r'(?:[a-z0-9-]+\.)+[a-z]{2,}', public_host):
            raise ValueError('Trusted public TLS hostname required')
        self.controller, self.public_host = controller, public_host
        self.profiles = {}
        for pool, profile in profiles.items():
            identity, path = profile
            identity = str(uuid.UUID(identity))
            if not re.fullmatch('/[a-f0-9]{32}', path):
                raise ValueError('Fixed upstream WS path required')
            self.profiles[pool] = (identity, path)
        self.default_route = default_route
        if default_route:
            path, host, upstream_port = default_route
            if (not re.fullmatch('/[a-zA-Z0-9_-]{1,64}', path) or host != '127.0.0.1'
                    or type(upstream_port) is not int or not 1024 <= upstream_port <= 65535):
                raise ValueError('Private default ingress required')
        self.slots = threading.BoundedSemaphore(128)
        super().__init__(('127.0.0.1', port), Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        # Never print request paths, credentials or profiles on failure.
        pass


class Handler(http.server.BaseHTTPRequestHandler):
    rbufsize = 0
    server_version = 'Nyx'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_):
        pass

    def _reply(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def _identity(self):
        if len(self.headers.get_all('Authorization', [])) != 1 or len(self.headers.get_all('X-Nyx-User', [])) != 1:
            raise Denied('Authentication required')
        authorization = self.headers['Authorization']
        if not authorization.startswith('Bearer '):
            raise Denied('Authentication required')
        owner, key = self.headers['X-Nyx-User'], authorization[7:]
        self.server.controller._authenticate(owner, key)
        return owner, key

    def _body(self):
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            raise ValueError('Explicit bounded body required')
        length = self.headers['Content-Length']
        if not re.fullmatch('[0-9]{1,4}', length) or not 0 < int(length) <= 2048:
            raise ValueError('Invalid body length')
        if self.headers.get('Content-Type') != 'application/json':
            raise ValueError('JSON required')
        data = self.rfile.read(int(length))
        if len(data) != int(length):
            raise ValueError('Incomplete body')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('Duplicate field')
                result[key] = value
            return result
        result = json.loads(data, object_pairs_hook=unique)
        if not isinstance(result, dict):
            raise ValueError('Object required')
        return result

    def do_POST(self):
        if sum(len(k)+len(v) for k,v in self.headers.items()) > 16384:
            return self._reply(431, {'error': 'headers_too_large'})
        try:
            owner, key = self._identity()
        except Denied:
            return self._reply(401, {'error': 'authentication_required'})
        try:
            body = self._body()
            controller = self.server.controller
            if self.path == '/v1/sessions':
                if set(body) != {'country', 'require_udp'} or type(body['require_udp']) is not bool:
                    raise ValueError('Invalid fields')
                lease = controller.connect(owner, key, body['country'], body['require_udp'])
                try:
                    identity, _ = self.server.profiles[lease.pool]
                    path = f'/s/{lease.token}/{lease.generation}'
                    params = urlencode({'encryption': 'none', 'security': 'tls', 'sni': self.server.public_host,
                                        'type': 'ws', 'host': self.server.public_host, 'path': path}, quote_via=quote)
                    profile = f'vless://{identity}@{self.server.public_host}:443?{params}#Nyx-{body["country"]}'
                    ttl = max(0, math.floor(lease.expires_at-controller.sessions.clock()))
                    if ttl <= 0:
                        raise ValueError('Expired during installation')
                except Exception:
                    controller.disconnect(owner, key, lease.token)
                    raise ValueError('Profile unavailable') from None
                return self._reply(201, {'token': lease.token, 'generation': lease.generation,
                                         'country': body['country'], 'expires_in': ttl, 'profile': profile})
            if self.path == '/v1/disconnect':
                if set(body) != {'token'} or not isinstance(body['token'], str):
                    raise ValueError('Invalid fields')
                controller.disconnect(owner, key, body['token'])
                return self._reply(200, {'disconnected': True})
            return self._reply(404, {'error': 'not_found'})
        except (ValueError, KeyError, TypeError):
            return self._reply(409, {'error': 'request_unavailable_no_fallback'})

    def do_GET(self):
        if self.path == '/v1/availability':
            try:
                owner, _ = self._identity()
            except Denied:
                return self._reply(401, {'error': 'authentication_required'})
            controller = self.server.controller
            with controller.lock:
                try:
                    controller._limit(owner)
                    controller.sweep()
                except ValueError:
                    return self._reply(429, {'error': 'request_budget_exceeded'})
                countries = {}
                if controller.healthy:
                    with controller.sessions.lock:
                        controller.sessions._prune()
                        now = controller.sessions.clock()
                        for pool_id, pool in controller.sessions.pools.items():
                            evidence = pool['evidence']
                            if not pool['ready'] or pool_id not in self.server.profiles or not evidence or not evidence.udp:
                                continue
                            ttl = math.floor(evidence.expires_at-now)
                            if ttl < 10:
                                continue
                            row = countries.setdefault(pool['country'], {'country': pool['country'], 'pool_count': 0,
                                       'providers': set(), 'protocols': set(), 'expires_in': 300, 'udp': True})
                            row['pool_count'] += 1
                            row['providers'].add(pool['provider'])
                            row['protocols'].add(pool['protocol'])
                            row['expires_in'] = min(row['expires_in'], ttl)
                for row in countries.values():
                    row['provider_count'] = len(row['providers'])
                    row['providers'] = sorted(row['providers'])
                    row['protocols'] = sorted(row['protocols'])
                return self._reply(200, {'schema_version': 1, 'purpose': 'authenticated_live_availability',
                                         'countries': list(countries.values())})
        if (self.headers.get('Upgrade', '').lower() != 'websocket'
                or 'upgrade' not in [v.strip().lower() for v in self.headers.get('Connection', '').split(',')]
                or self.headers.get('Transfer-Encoding') or self.headers.get('Content-Length') not in (None, '0')):
            return self._reply(400, {'error': 'websocket_required'})
        if sum(len(k)+len(v) for k,v in self.headers.items()) > 16384:
            return self._reply(431, {'error': 'headers_too_large'})
        controller = self.server.controller
        try:
            if self.server.default_route and self.path == self.server.default_route[0]:
                path, host, port = self.server.default_route
                endpoint, deadline = (host, port), float('inf')
            else:
                match = re.fullmatch(r'/s/([A-Za-z0-9_-]{43})/([1-9][0-9]{0,18})', self.path)
                if not match:
                    raise ValueError('Route unavailable')
                token, generation = match[1], int(match[2])
                with controller.lock:
                    controller.sweep()
                    lease = controller.leases.get(token)
                    if not controller.healthy or lease is None or lease.generation != generation:
                        raise ValueError('Route unavailable')
                    pool = controller.sessions.resolve(token)
                    endpoint = controller.plane.endpoint(token)
                    path = self.server.profiles[pool][1]
                    deadline = lease.expires_at
        except (ValueError, KeyError):
            return self._reply(403, {'error': 'route_unavailable'})
        # Only the fixed WS handshake headers are sent upstream. API credentials
        # and arbitrary proxy headers never reach an upstream provider.
        headers = [f'GET {path} HTTP/1.1', 'Host: localhost', 'Upgrade: websocket', 'Connection: Upgrade']
        for name in ('Sec-WebSocket-Key', 'Sec-WebSocket-Version', 'Sec-WebSocket-Protocol'):
            values = self.headers.get_all(name, [])
            if len(values) > 1 or (values and ('\r' in values[0] or '\n' in values[0])):
                return self._reply(400, {'error': 'invalid_handshake'})
            if values:
                headers.append(name + ': ' + values[0])
        self.close_connection = True
        try:
            with socket.create_connection(endpoint, timeout=3) as upstream:
                upstream.settimeout(3)
                self.connection.settimeout(3)
                upstream.sendall(('\r\n'.join(headers)+'\r\n\r\n').encode('ascii'))
                relay(self.connection, upstream, lambda: controller.sessions.clock() < deadline)
        except (OSError, ValueError):
            pass
