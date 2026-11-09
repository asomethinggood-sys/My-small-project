import socket
import threading
import time
import unittest
from scripts.egress_stream import relay


class StreamTests(unittest.TestCase):
    def test_request_half_close_must_not_discard_delayed_response(self):
        client, left = socket.socketpair()
        right, origin = socket.socketpair()
        sockets = [client, left, right, origin]
        for sock in sockets: sock.settimeout(3)
        payload = b'response-after-request-eof-' * 10000
        errors = []
        def server():
            try:
                request = bytearray()
                while True:
                    part = origin.recv(8192)
                    if not part: break
                    request.extend(part)
                if request != b'complete request': raise AssertionError('Request truncated')
                origin.sendall(payload)
                origin.shutdown(socket.SHUT_WR)
            except Exception as error: errors.append(error)
        def forward():
            try:
                deadline = time.monotonic()+5
                relay(left,right,lambda:time.monotonic()<deadline)
            except Exception as error: errors.append(error)
        workers = [threading.Thread(target=server),threading.Thread(target=forward)]
        try:
            for worker in workers: worker.start()
            client.sendall(b'complete request');client.shutdown(socket.SHUT_WR)
            received=bytearray()
            while True:
                data=client.recv(16384)
                if not data: break
                received.extend(data)
            for worker in workers: worker.join(3)
            self.assertFalse(any(w.is_alive() for w in workers))
            self.assertEqual(errors,[])
            self.assertEqual(received,payload)
        finally:
            for sock in sockets: sock.close()
            for worker in workers: worker.join(3)

    def test_expiry_stops_relay_without_waiting_for_eof(self):
        a,b=socket.socketpair();c,d=socket.socketpair()
        try:
            deadline=time.monotonic()+.1
            relay(b,c,lambda:time.monotonic()<deadline)
            self.assertLess(time.monotonic()-deadline,.5)
        finally:
            for sock in [a,b,c,d]:sock.close()


if __name__=='__main__':unittest.main()
