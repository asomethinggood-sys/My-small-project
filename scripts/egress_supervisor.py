"""Bounded health scheduling for already-provisioned, approved country pools.

Probe callbacks are trusted adapters, not user code or public catalog JSON. They
must measure the full path and return Evidence using the controller's monotonic
clock. This scheduler does not grant provider approval or manufacture geography.
One worker per pool prevents a hung adapter from spawning replacement threads.
Adapters must enforce their own I/O deadlines and honor the cancellation event.
"""
from dataclasses import dataclass, field
import math
import queue
import threading

from scripts.egress_sessions import Evidence


@dataclass
class Attempt:
    ticket: str = field(repr=False)
    deadline: float
    cancel: threading.Event = field(default_factory=threading.Event)
    timed_out: bool = False


class Supervisor:
    def __init__(self, controller, probes, interval=30, timeout=10):
        if (not isinstance(interval, (int, float)) or not math.isfinite(interval)
                or not 1 <= interval <= 120 or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or not 0 < timeout <= interval):
            raise ValueError('Bounded health cadence required')
        if (not 1 <= len(probes) <= 32 or set(probes) != set(controller.sessions.pools)
                or not all(callable(probe) for probe in probes.values())):
            raise ValueError('One trusted probe per provisioned pool required')
        self.controller, self.probes = controller, dict(probes)
        self.interval, self.timeout = interval, timeout
        self.clock = controller.sessions.clock
        self.pending, self.next_due, self.states = {}, {}, {}
        self.results = queue.SimpleQueue()
        self.lock = threading.RLock()
        self.closed = False

    def _probe(self, pool, attempt):
        result = None
        try:
            result = self.probes[pool](attempt.cancel)
        except Exception:
            # Provider errors may include private endpoints or credentials.
            pass
        self.results.put((pool, attempt, result))

    def _fail(self, pool, state):
        self.controller.pool_failed(pool)
        self.states[pool] = state

    def tick(self):
        """Non-blocking maintenance, called at least once per second by owner."""
        with self.lock:
            if self.closed:
                return
            try:
                now = self.clock()
                # Revoke expired evidence/leases even if every probe is blocked.
                self.controller.sweep()
                while True:
                    try:
                        pool, attempt, evidence = self.results.get_nowait()
                    except queue.Empty:
                        break
                    if self.pending.get(pool) is not attempt:
                        continue
                    del self.pending[pool]
                    if attempt.cancel.is_set() or now >= attempt.deadline:
                        self._fail(pool, 'probe_timeout')
                    elif not isinstance(evidence, Evidence):
                        self._fail(pool, 'probe_failed')
                    else:
                        try:
                            # Same lock order as API operations: controller then sessions.
                            with self.controller.lock:
                                self.controller.sessions.mark_ready(pool, evidence, ticket=attempt.ticket)
                        except ValueError:
                            self._fail(pool, 'evidence_rejected')
                        else:
                            self.states[pool] = 'healthy'
                for pool, attempt in self.pending.items():
                    if now >= attempt.deadline and not attempt.timed_out:
                        attempt.timed_out = True
                        attempt.cancel.set()
                        self._fail(pool, 'probe_timeout')
                for pool in self.probes:
                    if pool in self.pending or now < self.next_due.get(pool, 0):
                        continue
                    ticket = self.controller.sessions.begin_probe(pool)
                    attempt = Attempt(ticket, now+self.timeout)
                    self.pending[pool] = attempt
                    self.next_due[pool] = now+self.interval
                    threading.Thread(target=self._probe, args=(pool, attempt), daemon=True,
                                     name='nyx-pool-health').start()
            except Exception:
                # Revocation/maintenance failures cannot leave a nominally healthy API.
                self.close()
                raise RuntimeError('Supervisor unavailable; operator recovery required') from None

    def run(self, stop, max_seconds=900):
        """Finite owner loop; no indefinite hosted-runner service mode."""
        if type(max_seconds) is not int or not 1 <= max_seconds <= 21600:
            raise ValueError('Bounded supervisor lifetime required')
        end = self.clock()+max_seconds
        try:
            while not stop.is_set() and self.clock() < end:
                self.tick()
                stop.wait(.25)
        finally:
            self.close()

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            for attempt in self.pending.values():
                attempt.cancel.set()
            self.controller.close()
