"""Private per-lease TCP ingress with real flow teardown and deadline enforcement.

Loopback-only endpoints for a trusted authenticated TLS frontend, never a public
proxy. Destinations are operator-provisioned isolated Xray pool ingress addresses;
opaque TCP can carry VLESS/WebSocket framing. This does not provision providers,
terminate TLS, authenticate HTTP requests, or prove UDP/country connectivity.
"""
from contextlib import contextmanager
import ipaddress
import selectors
import socket
import threading
import time


class LocalIngressPlane:
    def __init__(self, destinations, clock=time.monotonic, max_leases=32, max_flows=64):
        if not 1 <= max_leases <= 128 or not 1 <= max_flows <= 256:
            raise ValueError('Invalid ingress budget')
        self.destinations = dict(destinations)
        for host, port in self.destinations.values():
            ip = ipaddress.ip_address(host)
            if (ip.version != 4 or not (ip in ipaddress.ip_network('198.19.0.0/16') or str(ip) == '127.0.0.1')
                    or type(port) is not int or not 1024 <= port <= 65535):
                raise ValueError('Private provisioned pool ingress required')
        self.clock, self.max_leases, self.max_flows = clock, max_leases, max_flows
        self.lock = threading.RLock()
        self.entries = {}
        self.blocked = False

    @staticmethod
    def _close(sock):
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()

    def install(self, lease):
        with self.lock:
            if (self.blocked or lease.pool not in self.destinations or lease.token in self.entries
                    or len(self.entries) >= self.max_leases or lease.expires_at <= self.clock()):
                raise ValueError('Ingress unavailable')
            listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                listener.bind(('127.0.0.1', 0))
                listener.listen(self.max_flows)
                listener.settimeout(.1)
                entry = dict(listener=listener, sockets=set(), active=0, lease=lease,
                             stop=threading.Event(), endpoint=listener.getsockname())
                self.entries[lease.token] = entry
                thread = threading.Thread(target=self._accept, args=(lease.token, entry), daemon=True)
                entry['thread'] = thread
                thread.start()
            except Exception:
                self.entries.pop(lease.token, None)
                self._close(listener)
                raise

    def endpoint(self, token):
        with self.lock:
            entry = self.entries.get(token)
            if self.blocked or entry is None or entry['lease'].expires_at <= self.clock():
                raise ValueError('Ingress unavailable')
            return entry['endpoint']

    @contextmanager
    def open_stream(self, token, generation, incoming):
        """Tracked direct gateway stream: no second loopback TCP relay/thread.

        The lease listener remains for compatible adapters and independently
        enforces expiration. Both paths share quotas and revocation bookkeeping.
        """
        with self.lock:
            entry = self.entries.get(token)
            if (self.blocked or entry is None or entry['stop'].is_set()
                    or entry['lease'].generation != generation
                    or self.clock() >= entry['lease'].expires_at
                    or entry['active'] >= self.max_flows):
                raise ValueError('Ingress unavailable')
            outgoing = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            entry['sockets'].update((incoming, outgoing))
            entry['active'] += 1
        try:
            outgoing.settimeout(3)
            outgoing.connect(self.destinations[entry['lease'].pool])
            with self.lock:
                if entry['stop'].is_set() or self.clock() >= entry['lease'].expires_at:
                    raise ValueError('Ingress expired during connection')
            yield outgoing
        finally:
            with self.lock:
                for sock in (incoming, outgoing):
                    entry['sockets'].discard(sock)
                    self._close(sock)
                entry['active'] -= 1

    def _accept(self, token, entry):
        try:
            while not entry['stop'].is_set():
                if self.clock() >= entry['lease'].expires_at:
                    break
                try:
                    incoming, _ = entry['listener'].accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with self.lock:
                    if entry['stop'].is_set() or entry['lease'].expires_at <= self.clock() or entry['active'] >= self.max_flows:
                        self._close(incoming)
                        continue
                    entry['sockets'].add(incoming)
                    entry['active'] += 1
                    threading.Thread(target=self._flow, args=(entry, incoming), daemon=True).start()
        finally:
            with self.lock:
                if self.entries.get(token) is entry:
                    self.revoke(token)

    def _flow(self, entry, incoming):
        outgoing = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            with self.lock:
                if entry['stop'].is_set():
                    return
                entry['sockets'].add(outgoing)
            outgoing.settimeout(2)
            outgoing.connect(self.destinations[entry['lease'].pool])
            incoming.setblocking(False)
            outgoing.setblocking(False)
            buffers = {incoming: bytearray(), outgoing: bytearray()}
            peers = {incoming: outgoing, outgoing: incoming}
            read_open = {incoming: True, outgoing: True}
            write_open = {incoming: True, outgoing: True}
            while not entry['stop'].is_set() and self.clock() < entry['lease'].expires_at:
                with selectors.DefaultSelector() as selector:
                    for sock, peer in peers.items():
                        events = 0
                        if read_open[sock] and len(buffers[peer]) < 65536:
                            events |= selectors.EVENT_READ
                        if buffers[sock]:
                            events |= selectors.EVENT_WRITE
                        if events:
                            selector.register(sock, events)
                    if not selector.get_map():
                        break
                    ready = selector.select(.1)
                for key, events in ready:
                    sock = key.fileobj
                    peer = peers[sock]
                    if events & selectors.EVENT_READ:
                        try:
                            data = sock.recv(min(16384, 65536-len(buffers[peer])))
                            if data:
                                buffers[peer].extend(data)
                            else:
                                read_open[sock] = False
                        except BlockingIOError:
                            pass
                    if events & selectors.EVENT_WRITE:
                        try:
                            sent = sock.send(buffers[sock])
                            del buffers[sock][:sent]
                        except BlockingIOError:
                            pass
                # Preserve half-close semantics: drain before forwarding EOF.
                for sock, peer in peers.items():
                    if not read_open[peer] and not buffers[sock] and write_open[sock]:
                        sock.shutdown(socket.SHUT_WR)
                        write_open[sock] = False
        except (OSError, ValueError):
            # No addresses, identities or data in logs.
            pass
        finally:
            with self.lock:
                for sock in (incoming, outgoing):
                    entry['sockets'].discard(sock)
                    self._close(sock)
                entry['active'] -= 1

    def revoke(self, token):
        with self.lock:
            entry = self.entries.pop(token, None)
            if entry is None:
                return
            entry['stop'].set()
            self._close(entry['listener'])
            for sock in list(entry['sockets']):
                self._close(sock)

    def fail_closed(self):
        with self.lock:
            self.blocked = True
            for token in list(self.entries):
                self.revoke(token)
