"""Actual SOCKS -> VLESS/WS -> namespace Xray -> WireGuard fixture path."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from scripts.egress_xray import configurations

HTTP = '''import socket
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(('1.1.1.1',18082));s.listen(8)
while True:
 c,a=s.accept();c.settimeout(2)
 try:
  c.recv(4096)
  c.sendall(b'HTTP/1.1 200 OK\\r\\nContent-Length: 18\\r\\nConnection: close\\r\\n\\r\\nnyx-encrypted-path')
 except OSError: pass
 c.close()
'''
WAIT = '''import socket,sys,time
for i in range(100):
 try:
  s=socket.create_connection((sys.argv[1],int(sys.argv[2])),timeout=.1);s.close();sys.exit(0)
 except OSError: time.sleep(.1)
sys.exit(1)
'''
UDP_PROBE = '''import socket,struct
s=socket.create_connection(('127.0.0.1',10809),timeout=5);s.settimeout(5)
def read(n):
 data=b''
 while len(data)<n:
  chunk=s.recv(n-len(data))
  if not chunk: raise RuntimeError('short SOCKS reply')
  data+=chunk
 return data
s.sendall(bytes([5,1,0]));assert read(2)==bytes([5,0])
s.sendall(bytes([5,3,0,1,0,0,0,0,0,0]))
header=read(4);assert header[:2]==bytes([5,0]) and header[3]==1
address=socket.inet_ntoa(read(4));port=struct.unpack('!H',read(2))[0]
if address=='0.0.0.0': address='127.0.0.1'
u=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);u.settimeout(5)
query=struct.pack('!HHHHHH',1234,0x100,1,0,0,0)+bytes([4])+b'test'+bytes([7])+b'invalid'+bytes([0])+struct.pack('!HH',1,1)
packet=bytes([0,0,0,1,1,1,1,1])+struct.pack('!H',53)+query
u.sendto(packet,(address,port));response=u.recv(2048)
assert response[:4]==bytes([0,0,0,1])
data=response[10:]
assert data[:2]==query[:2] and data[-4:]==bytes([198,51,100,1])
print('udp-vless-wireguard-ok')
u.close();s.close()
'''


def test_xray(binary, pool, control, peer):
    processes = []
    def run(ns, *args):
        return subprocess.run(['ip', 'netns', 'exec', ns, *args],
                              check=True, text=True, capture_output=True, timeout=20)
    with tempfile.TemporaryDirectory(prefix='nyx-xray-') as directory:
        try:
            server, client = configurations(pool.payload_ip, str(uuid.uuid4()), '/' + uuid.uuid4().hex)
            unauthorized = json.loads(json.dumps(client))
            unauthorized['inbounds'][0]['port'] = 10810
            unauthorized['outbounds'][0]['settings']['vnext'][0]['users'][0]['id'] = str(uuid.uuid4())
            for name, config in [('server', server), ('client', client), ('unauthorized', unauthorized)]:
                path = Path(directory) / (name + '.json')
                path.write_text(json.dumps(config))
                path.chmod(0o600)
                subprocess.run([binary, 'run', '-test', '-c', str(path)],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            for ns, command in [
                    (peer, [sys.executable, '-c', HTTP]),
                    (pool.namespace, [binary, 'run', '-c', str(Path(directory) / 'server.json')]),
                    (control, [binary, 'run', '-c', str(Path(directory) / 'client.json')]),
                    (control, [binary, 'run', '-c', str(Path(directory) / 'unauthorized.json')])]:
                processes.append(subprocess.Popen(['ip', 'netns', 'exec', ns, *command],
                                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            run(peer, sys.executable, '-c', WAIT, '1.1.1.1', '18082')
            run(control, sys.executable, '-c', WAIT, pool.payload_ip, '18888')
            run(control, sys.executable, '-c', WAIT, '127.0.0.1', '10809')
            response = run(control, 'curl', '--fail', '--silent', '--show-error', '--max-time', '10',
                           '--noproxy', '', '--proxy', 'socks5h://127.0.0.1:10809', 'http://1.1.1.1:18082/')
            assert response.stdout == 'nyx-encrypted-path'
            response = run(control, sys.executable, '-c', UDP_PROBE)
            assert response.stdout.strip() == 'udp-vless-wireguard-ok'
            run(control, sys.executable, '-c', WAIT, '127.0.0.1', '10810')
            unauthorized = subprocess.run(['ip', 'netns', 'exec', control, 'curl', '--fail', '--silent',
                                           '--max-time', '2', '--noproxy', '', '--proxy',
                                           'socks5h://127.0.0.1:10810', 'http://1.1.1.1:18082/'],
                                          capture_output=True, timeout=5)
            assert unauthorized.returncode != 0
            lease_result = run(control, sys.executable, str(Path(__file__).with_name('egress_lease_kernel.py').resolve()),
                               binary, str(Path(directory) / 'client.json'))
            assert 'authenticated-lease-tcp-udp-and-revocation-passed' in lease_result.stdout
            # With the interface down, existing ingress still cannot escape directly.
            run(pool.namespace, 'ip', 'link', 'set', 'nyx-vpn', 'down')
            failed = subprocess.run(['ip', 'netns', 'exec', control, 'curl', '--fail', '--silent',
                                     '--max-time', '2', '--noproxy', '', '--proxy',
                                     'socks5h://127.0.0.1:10809', 'http://1.1.1.1:18082/'],
                                    capture_output=True, timeout=5)
            assert failed.returncode != 0
            run(pool.namespace, 'ip', 'link', 'set', 'nyx-vpn', 'up')
            response = run(control, 'curl', '--fail', '--silent', '--show-error', '--max-time', '10',
                           '--noproxy', '', '--proxy', 'socks5h://127.0.0.1:10809', 'http://1.1.1.1:18082/')
            assert response.stdout == 'nyx-encrypted-path'
            return ['Authenticated per-user lease carries TCP and framed UDP through Xray/WireGuard; revocation blocks requests (synthetic local geography)',
                    'Xray VLESS/WS carries TCP and UDP through real local WireGuard',
                    'Incorrect VLESS identity cannot access the pool',
                    'Tunnel-down blocks Xray requests; new requests recover after tunnel-up']
        finally:
            for process in reversed(processes):
                process.terminate()
            for process in reversed(processes):
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
