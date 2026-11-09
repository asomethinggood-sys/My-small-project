import http.client
import http.server
import json
import socket
import threading
import time
import unittest
import uuid
from urllib.parse import urlparse, parse_qs
from scripts.egress_control import Controller
from scripts.egress_gateway import Gateway
from scripts.egress_ingress import LocalIngressPlane
from scripts.egress_sessions import Sessions, Evidence


class GatewayTests(unittest.TestCase):
    def setUp(self):
        sessions = Sessions()
        sessions.register('de', 'DE', 'fixture', 'wireguard', True)
        sessions.mark_ready('de', Evidence('DE', True, True, True, True, True, time.monotonic()+60),
                            ticket=sessions.begin_probe('de'))
        self.key = 'A'*43
        self.plane = LocalIngressPlane({'de': ('127.0.0.1', 18888)})
        self.control = Controller(sessions, self.plane, {'alice': self.key, 'bob': 'B'*43})
        self.gateway = Gateway(self.control, 'fixture.example', {'de': (str(uuid.uuid4()), '/'+'a'*32)})
        self.thread = threading.Thread(target=self.gateway.serve_forever, daemon=True)
        self.thread.start()
    def tearDown(self):
        self.control.close()
        self.gateway.shutdown()
        self.gateway.server_close()
        self.thread.join(2)
    def post(self, path, body, key=None, owner='alice'):
        client = http.client.HTTPConnection(*self.gateway.server_address, timeout=3)
        data = json.dumps(body)
        client.request('POST', path, data, {'Authorization': 'Bearer '+(key or self.key), 'X-Nyx-User': owner, 'Content-Type': 'application/json'})
        response = client.getresponse()
        result = response.status, json.loads(response.read())
        self.assertEqual(response.getheader('Cache-Control'), 'no-store')
        client.close()
        return result
    def test_issue_real_tls_profile_and_disconnect(self):
        status, lease = self.post('/v1/sessions', {'country':'DE','require_udp':True})
        self.assertEqual(status,201)
        profile = urlparse(lease['profile'])
        self.assertEqual(profile.hostname, 'fixture.example')
        options = parse_qs(profile.query)
        self.assertEqual(options['security'],['tls'])
        self.assertEqual(options['path'],[f'/s/{lease["token"]}/{lease["generation"]}'])
        self.assertLessEqual(lease['expires_in'],60)
        status, _ = self.post('/v1/disconnect', {'token':lease['token']},key='B'*43,owner='bob')
        self.assertEqual(status,409)
        self.assertEqual(self.control.sessions.resolve(lease['token']),'de')
        self.assertEqual(self.post('/v1/disconnect',{'token':lease['token']})[0],200)
        self.assertEqual(self.control.leases,{})
    def test_bad_auth_and_unavailable_country_never_fall_back(self):
        self.assertEqual(self.post('/v1/sessions',{'country':'DE','require_udp':True},key='wrong')[0],401)
        self.assertEqual(self.post('/v1/sessions',{'country':'FR','require_udp':True})[0],409)
        self.assertEqual(self.control.leases,{})
    def test_rejects_nonboolean_udp_and_extra_fields(self):
        for body in [{'country':'DE','require_udp':'true'}, {'country':'DE','require_udp':True,'endpoint':'evil'}]:
            self.assertEqual(self.post('/v1/sessions',body)[0],409)
        self.assertEqual(self.control.leases,{})
    def test_unknown_or_stale_websocket_token_rejected(self):
        client=http.client.HTTPConnection(*self.gateway.server_address,timeout=3)
        client.request('GET','/s/'+'X'*43+'/1',headers={'Upgrade':'websocket','Connection':'Upgrade'})
        response=client.getresponse()
        self.assertEqual(response.status,403)
        response.read();client.close()
    def test_duplicate_json_and_chunked_body_rejected(self):
        for body,extra in [('"country":"FR",',{}),('',{'Transfer-Encoding':'chunked'})]:
            client=http.client.HTTPConnection(*self.gateway.server_address,timeout=3)
            raw='{'+body+'"country":"DE","require_udp":true}'
            client.request('POST','/v1/sessions',raw,headers={'Authorization':'Bearer '+self.key,'X-Nyx-User':'alice','Content-Type':'application/json',**extra})
            response=client.getresponse();self.assertEqual(response.status,409);response.read();client.close()
    def test_default_route_survives_country_disconnect(self):
        class Echo(http.server.BaseHTTPRequestHandler):
            rbufsize=0
            def log_message(self,*args): pass
            def do_GET(self):
                self.send_response(101);self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.end_headers()
                self.connection.settimeout(2)
                try:
                    while True:
                        data=self.connection.recv(4096)
                        if not data:break
                        self.connection.sendall(data)
                except OSError:pass
        origin=http.server.ThreadingHTTPServer(('127.0.0.1',0),Echo)
        origin.daemon_threads=True
        worker=threading.Thread(target=origin.serve_forever,daemon=True);worker.start()
        self.plane.destinations['de']=origin.server_address
        self.gateway.default_route=('/default',*origin.server_address)
        def connect(path):
            sock=socket.create_connection(self.gateway.server_address,timeout=3)
            sock.sendall(f'GET {path} HTTP/1.1\r\nHost: fixture.example\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n'.encode())
            header=b''
            while not header.endswith(b'\r\n\r\n'):header+=sock.recv(1)
            self.assertIn(b'101',header)
            sock.sendall(b'control');self.assertEqual(sock.recv(7),b'control')
            return sock
        default=country=None
        try:
            default=connect('/default')
            status,lease=self.post('/v1/sessions',{'country':'DE','require_udp':True});self.assertEqual(status,201)
            country=connect(f'/s/{lease["token"]}/{lease["generation"]}')
            self.assertEqual(self.post('/v1/disconnect',{'token':lease['token']})[0],200)
            self.assertEqual(country.recv(1),b'')
            default.sendall(b'unaffected');self.assertEqual(default.recv(10),b'unaffected')
        finally:
            if country:country.close()
            if default:default.close()
            origin.shutdown();origin.server_close();worker.join(2)
    def test_gateway_only_listens_on_loopback(self):
        self.assertEqual(self.gateway.server_address[0],'127.0.0.1')
        with self.assertRaises(ValueError):Gateway(self.control,'http://evil',{})


if __name__=='__main__':unittest.main()
