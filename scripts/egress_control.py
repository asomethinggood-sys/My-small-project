"""Authenticated, bounded session controller for a single owning supervisor.

No network listener or default-route changes. A TLS API can delegate authenticated
requests here; transport authentication is still required. The data-plane adapter
must implement install/revoke (including closure of existing flows) and fail_closed.
No provider is registered/approved by this module. Secrets never enter catalogs.
"""
from dataclasses import dataclass
import hashlib
import re
import secrets
import threading


class Denied(ValueError):
    pass


@dataclass(frozen=True)
class Lease:
    owner: str
    token: str
    pool: str
    expires_at: float
    generation: int


class Controller:
    def __init__(self, sessions, plane, credentials, per_user=2, requests_per_minute=12):
        if not 1 <= per_user <= 8 or not 1 <= requests_per_minute <= 120:
            raise ValueError('Invalid quota')
        if not 1 <= len(credentials) <= 128:
            raise ValueError('Bounded credential registry required')
        self.credentials = {}
        for owner, credential in credentials.items():
            if (not re.fullmatch('[a-z0-9_-]{1,48}', owner)
                    or not isinstance(credential, str) or not re.fullmatch('[A-Za-z0-9_-]{43,128}', credential)):
                raise ValueError('Strong provisioned credential required')
            digest = hashlib.sha256(credential.encode()).digest()
            if digest in self.credentials.values():
                raise ValueError('Credentials must be unique')
            self.credentials[owner] = digest
        self.sessions, self.plane = sessions, plane
        self.per_user, self.rate = per_user, requests_per_minute
        self.leases, self.windows, self.generations = {}, {}, {}
        self.lock = threading.RLock()
        self.healthy = True

    def _authenticate(self, owner, credential):
        if not isinstance(owner, str) or not isinstance(credential, str) or len(credential) > 128:
            raise Denied('Authentication required')
        digest = hashlib.sha256(credential.encode()).digest()
        expected = self.credentials.get(owner, bytes(32))
        valid = secrets.compare_digest(digest, expected)
        if owner not in self.credentials or not valid:
            raise Denied('Authentication required')

    def _limit(self, owner):
        now = self.sessions.clock()
        start, count = self.windows.get(owner, (now, 0))
        if now < start or now - start >= 60:
            start, count = now, 0
        if count >= self.rate:
            raise Denied('Request budget exceeded')
        self.windows[owner] = (start, count + 1)

    def _revoke(self, token):
        # Never report revocation as complete if the transport could still work.
        try:
            self.plane.revoke(token)
        except Exception:
            self.healthy = False
            try:
                self.plane.fail_closed()
            finally:
                raise Denied('Data plane unavailable; operator recovery required') from None
        self.leases.pop(token, None)
        with self.sessions.lock:
            self.sessions.sessions.pop(token, None)

    def sweep(self):
        """Supervisor must call periodically, including when there are no requests."""
        with self.lock:
            for token in list(self.leases):
                try:
                    self.sessions.resolve(token)
                except ValueError:
                    self._revoke(token)

    def connect(self, owner, credential, country, require_udp=True):
        with self.lock:
            self._authenticate(owner, credential)
            self._limit(owner)
            if not self.healthy:
                raise Denied('Data plane unavailable')
            if not isinstance(country, str) or not re.fullmatch('[A-Z]{2}', country):
                raise Denied('Country required; no default fallback')
            self.sweep()
            if sum(lease.owner == owner for lease in self.leases.values()) >= self.per_user:
                raise Denied('Session quota reached')
            token = self.sessions.issue(country, require_udp)
            pool = self.sessions.resolve(token)
            generation = self.generations.get(owner, 0) + 1
            self.generations[owner] = generation
            with self.sessions.lock:
                expiry = self.sessions.sessions[token]['expires_at']
            lease = Lease(owner, token, pool, expiry, generation)
            self.leases[token] = lease
            try:
                # Install can partially succeed; failure must also revoke.
                self.plane.install(lease)
            except Exception:
                self._revoke(token)
                raise Denied('Could not install isolated route') from None
            return lease

    def disconnect(self, owner, credential, token):
        with self.lock:
            self._authenticate(owner, credential)
            # Disconnect is never rate-limited. Do not expose another user's state.
            lease = self.leases.get(token)
            if lease is None or lease.owner != owner:
                raise Denied('Session unavailable')
            self._revoke(token)

    def resolve(self, owner, credential, token, generation):
        with self.lock:
            self._authenticate(owner, credential)
            if not self.healthy:
                raise Denied('Data plane unavailable')
            self.sweep()
            lease = self.leases.get(token)
            if lease is None or lease.owner != owner or lease.generation != generation:
                raise Denied('Session unavailable')
            return self.sessions.resolve(token)

    def pool_failed(self, pool):
        with self.lock:
            self.sessions.fail(pool)
            self.sweep()

    def close(self):
        with self.lock:
            self.healthy = False
            # Global fail-closed first, including flows not in our bookkeeping.
            self.plane.fail_closed()
            for token in list(self.leases):
                self._revoke(token)
