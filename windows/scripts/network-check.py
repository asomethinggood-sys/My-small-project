"""Measure fixture transfers and actual TUN DNS, not user/Tehran latency."""
import hashlib
import json
import socket
import struct
import sys
import time
import urllib.request


def dns(kind, *, tcp=False, timeout=12):
    query = struct.pack('!HHHHHH', 0x4381, 0x100, 1, 0, 0, 0)
    query += bytes.fromhex('076578616d706c6503636f6d00') + struct.pack('!HH', kind, 1)
    start = time.perf_counter()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.connect(('198.18.0.2', 53))
        if tcp:
            sock.sendall(struct.pack('!H', len(query)) + query)
            def exact(count):
                data = b''
                while len(data) < count:
                    chunk = sock.recv(count - len(data))
                    if not chunk:raise RuntimeError('Truncated DNS response')
                    data += chunk
                return data
            length = struct.unpack('!H', exact(2))[0]
            data = exact(length)
        else:
            sock.send(query); data = sock.recv(4096)
    assert len(data) >= 12 and data[:2] == query[:2]
    flags, _, answers = struct.unpack('!HHH', data[2:8])
    assert flags & 0x8000 and flags & 15 == 0
    assert answers > 0 if kind == 1 else answers == 0
    return round((time.perf_counter() - start) * 1000, 2)


def main():
    if '--baseline-drop' in sys.argv:
        try:dns(65, timeout=1.5)
        except socket.timeout:
            print('::notice title=Reproduced old Windows DNS defect::HTTPS type 65 timed out at 1500 ms under legacy nonIPQuery=drop')
            return
        raise RuntimeError('Old policy unexpectedly responded')
    report = {}
    for kind, name in [(65, 'https_record_ms'), (64, 'svcb_record_ms'), (1, 'a_cold_ms'), (1, 'a_cached_ms'), (28, 'aaaa_empty_ms')]:
        report[name] = dns(kind)
    report['tcp_dns_ms'] = dns(1, tcp=True)
    assert report['https_record_ms'] < 1500 and report['svcb_record_ms'] < 1500
    if '--dns-only' in sys.argv:
        # The unreachable primary has a four-second budget. It must not delay
        # either the healthy answer or a subsequent secondary-cache hit.
        assert report['a_cold_ms'] < 2500, 'Healthy resolver waited behind failed primary'
        assert report['a_cached_ms'] < 1000, 'Cached answer waited behind failed primary'
    if '--dns-only' not in sys.argv:
        client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        start = time.perf_counter()
        with client.open('http://198.18.0.10:23080/download', timeout=15) as response:body = response.read()
        assert body == bytes(range(256)) * 2048
        report['download_512k_ms'] = round((time.perf_counter() - start) * 1000, 2)
        upload = bytes(range(256)) * 256
        start = time.perf_counter()
        with client.open(urllib.request.Request('http://198.18.0.10:23080/upload', data=upload), timeout=15) as response:
            assert response.read().decode() == hashlib.sha256(upload).hexdigest()
        report['upload_64k_ms'] = round((time.perf_counter() - start) * 1000, 2)
    title = 'Forced primary DoH failure with verified secondary' if '--dns-only' in sys.argv else 'Windows TUN DNS and transfer fixture'
    print('::notice title=' + title + '::' + json.dumps(report), flush=True)


if __name__ == '__main__':main()
