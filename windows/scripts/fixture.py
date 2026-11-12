"""Local CI-only HTTP/UDP echo fixture. No public service or real credentials."""
import hashlib
import http.server
import socket
import threading

PAYLOAD = bytes(range(256)) * 2048

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def reply(self, body):
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_GET(self):
        self.reply(PAYLOAD if self.path == '/download' else b'continuum-windows-route-fixture')
    def do_POST(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 1024 * 1024:
            self.send_error(413)
            return
        self.reply(hashlib.sha256(self.rfile.read(length)).hexdigest().encode())
    def log_message(self, *args):
        pass

def udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 23080))
        while True:
            data, peer = sock.recvfrom(65536)
            sock.sendto(data, peer)

threading.Thread(target=udp, daemon=True).start()
http.server.ThreadingHTTPServer(('127.0.0.1', 23080), Handler).serve_forever()
