"""In-process, bounded country-pool/session control model; not a public API.

Only a trusted tunnel supervisor may supply probe evidence. This module does not
install networking rules: the data-plane kill switch remains a deployment gate.
Tokens must never enter public catalogs/logs. A production API additionally needs
caller authentication, quotas, TLS, rate limits and persistent generation control.
"""
from dataclasses import dataclass
import re
import secrets
import threading
import time


@dataclass(frozen=True)
class Evidence:
    country: str
    tcp: bool
    udp: bool
    dns: bool
    ipv6_safe: bool
    tunnel_drop_blocked: bool
    expires_at: float


class Sessions:
    def __init__(self, max_pools=4, max_sessions=128, clock=time.monotonic):
        if max_pools < 1 or max_sessions < 1:
            raise ValueError('Positive capacity required')
        self.max_pools, self.max_sessions = max_pools, max_sessions
        self.clock = clock
        self.pools, self.sessions = {}, {}
        self.lock = threading.RLock()

    def _prune(self):
        now = self.clock()
        for pool in self.pools.values():
            if pool['evidence'] and pool['evidence'].expires_at <= now:
                pool['ready'] = False
        self.sessions = {token: session for token, session in self.sessions.items()
                         if session['expires_at'] > now and self.pools[session['pool']]['ready']}

    def register(self, pool_id, country, provider, protocol, shared_use_approved=False):
        with self.lock:
            if shared_use_approved is not True:
                raise ValueError('Shared-use approval required')
            if not re.fullmatch('[A-Z]{2}', country) or any(
                    not re.fullmatch('[a-z0-9_-]{1,48}', v) for v in [pool_id, provider, protocol]):
                raise ValueError('Invalid pool identity')
            if pool_id in self.pools or len(self.pools) >= self.max_pools:
                raise ValueError('Duplicate pool or pool capacity reached')
            self.pools[pool_id] = dict(country=country, provider=provider, protocol=protocol,
                                       ready=False, evidence=None, probe_ticket=None)

    def begin_probe(self, pool_id):
        with self.lock:
            ticket = secrets.token_urlsafe(32)
            self.pools[pool_id]['probe_ticket'] = ticket
            return ticket

    def mark_ready(self, pool_id, evidence, *, ticket):
        with self.lock:
            pool = self.pools[pool_id]
            if (not isinstance(ticket, str) or pool['probe_ticket'] is None
                    or not secrets.compare_digest(ticket, pool['probe_ticket'])):
                raise ValueError('Stale or invalid probe result')
            pool['probe_ticket'] = None
            if (evidence.country != pool['country'] or any(type(flag) is not bool for flag in [
                    evidence.tcp, evidence.udp, evidence.dns, evidence.ipv6_safe, evidence.tunnel_drop_blocked])
                    or not all([evidence.tcp, evidence.dns, evidence.ipv6_safe, evidence.tunnel_drop_blocked])
                    or not self.clock() < evidence.expires_at <= self.clock() + 300):
                self.fail(pool_id)
                raise ValueError('Fresh full-path safety evidence required')
            pool.update(ready=True, evidence=evidence)

    def issue(self, country, require_udp=True):
        with self.lock:
            if type(require_udp) is not bool:
                raise ValueError('UDP requirement must be boolean')
            self._prune()
            if len(self.sessions) >= self.max_sessions:
                raise ValueError('Session capacity reached')
            for pool_id, pool in self.pools.items():
                if (pool['country'] == country and pool['ready']
                        and (not require_udp or pool['evidence'].udp)):
                    token = secrets.token_urlsafe(32)
                    self.sessions[token] = {'pool': pool_id,
                                            'expires_at': pool['evidence'].expires_at}
                    return token
            raise ValueError('No verified eligible exit; no default fallback')

    def resolve(self, token):
        with self.lock:
            self._prune()
            if token not in self.sessions:
                raise ValueError('Unknown, expired or revoked session')
            return self.sessions[token]['pool']

    def fail(self, pool_id):
        with self.lock:
            self.pools[pool_id]['ready'] = False
            self.pools[pool_id]['probe_ticket'] = None
            self._prune()

    def remove(self, pool_id):
        with self.lock:
            self.fail(pool_id)
            del self.pools[pool_id]
