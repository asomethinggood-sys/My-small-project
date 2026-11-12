"""Local CI-only HTTP/UDP echo fixture. No public service or real credentials."""
import http.server
import socket
import threading

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'continuum-windows-route-fixture'
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def log_message(self, *args):
        pass

def udp():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(('127.0.0.1', 23080))
        while True:
            data, peer = sock.recvfrom(65536)
            sock.sendto(data, peer)

threading.Thread(target=udp, daemon=True).start()
http.server.HTTPServer(('127.0.0.1', 23080), Handler).serve_forever()
