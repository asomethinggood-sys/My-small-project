"""Six minute UDP flow and segmented media checks over actual Windows TUN.
Not a claim of Discord service/YouTube CDN acceptance or Tehran performance.
"""
import concurrent.futures
import socket
import time
import urllib.request


def voice():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        sock.connect(('198.18.0.10', 23080))
        start = time.monotonic()
        count = 0
        while time.monotonic() - start < 360:
            data = count.to_bytes(8, 'big') + bytes(range(256)) * 4
            sock.send(data)
            assert sock.recv(4096) == data, 'UDP flow corrupted or lost'
            count += 1
            time.sleep(.1)
        print(f'::notice title=Long-lived voice transport::Single UDP socket survived 360 seconds, {count} exact echoed packets', flush=True)


def media():
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    payload = bytes(range(256)) * 2048
    for _ in range(10):
        for start in range(0, len(payload), 65536):
            end = start + 65535
            req = urllib.request.Request('http://198.18.0.10:23080/media', headers={'Range': f'bytes={start}-{end}'})
            with client.open(req, timeout=15) as r:
                assert r.status == 206 and r.read() == payload[start:end+1]
        time.sleep(2)
    print('::notice title=Media transfer::80 byte-exact HTTP 206 segments passed concurrently with UDP', flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(voice), executor.submit(media)]
    for future in futures:
        future.result()
