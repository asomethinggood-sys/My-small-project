"""Bounded bidirectional relay with backpressure and TCP half-close preservation."""
import selectors
import socket


def relay(left, right, alive):
    left.setblocking(False)
    right.setblocking(False)
    peers = {left: right, right: left}
    buffers = {left: bytearray(), right: bytearray()}
    reading = {left: True, right: True}
    writing = {left: True, right: True}
    while alive():
        with selectors.DefaultSelector() as selector:
            for source, peer in peers.items():
                events = 0
                if reading[source] and len(buffers[peer]) < 65536:
                    events |= selectors.EVENT_READ
                if buffers[source]:
                    events |= selectors.EVENT_WRITE
                if events:
                    selector.register(source, events)
            if not selector.get_map():
                return
            ready = selector.select(.1)
        for key, events in ready:
            source, peer = key.fileobj, peers[key.fileobj]
            if events & selectors.EVENT_READ:
                try:
                    data = source.recv(min(16384, 65536-len(buffers[peer])))
                    if data:
                        buffers[peer].extend(data)
                    else:
                        reading[source] = False
                except BlockingIOError:
                    pass
            if events & selectors.EVENT_WRITE:
                try:
                    sent = source.send(buffers[source])
                    del buffers[source][:sent]
                except BlockingIOError:
                    pass
        for destination, source in peers.items():
            if not reading[source] and not buffers[destination] and writing[destination]:
                destination.shutdown(socket.SHUT_WR)
                writing[destination] = False
