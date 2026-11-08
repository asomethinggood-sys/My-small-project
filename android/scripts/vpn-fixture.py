#!/usr/bin/env python3
"""Ephemeral CI-only server. No production subscription or release is changed."""
import base64, hashlib, http.server, json, os, pathlib, re, subprocess, threading, time, uuid, urllib.request, zipfile
root = pathlib.Path(os.environ['RUNNER_TEMP']) / 'continuum-fixture'
root.mkdir(exist_ok=True)
def download(url, name):
    path=root/name
    urllib.request.urlretrieve(url, path)
    return path
archive=download('https://github.com/XTLS/Xray-core/releases/download/v26.10.31/Xray-linux-64.zip','xray.zip')
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='e4bd9119f50ae7c41658b1abd0679ae06f98bd864a2907ff33f2f2cf7081b214'
with zipfile.ZipFile(archive) as z: z.extract('xray',root)
(root/'xray').chmod(0o755)
cf=download('https://github.com/cloudflare/cloudflared/releases/download/2026.2.0/cloudflared-linux-amd64','cloudflared')
cf.chmod(0o755)
class Marker(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body=b'continuum-vpn-path-ok'
        self.send_response(200); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self,*args): pass
threading.Thread(target=http.server.HTTPServer(('127.0.0.1',18780),Marker).serve_forever,daemon=True).start()
identity=str(uuid.uuid4()); password=uuid.uuid4().hex
inbounds=[]
for index, protocol in enumerate(['vless','vmess','trojan']):
    client={'password':password} if protocol=='trojan' else {'id':identity}
    settings={'clients':[client]}
    if protocol=='vless': settings['decryption']='none'
    inbounds.append({'listen':'127.0.0.1','port':18888+index,'protocol':protocol,'settings':settings,'streamSettings':{'network':'ws','wsSettings':{'path':'/fixture'}}})
inbounds.append({'listen':'0.0.0.0','port':18891,'protocol':'shadowsocks','settings':{'method':'aes-128-gcm','password':password,'network':'tcp,udp'}})
# Xray 26 blocks private destinations by default. Only the marker outbound may reach
# this exact loopback service; do not weaken the general Internet outbound.
marker={'redirect':'127.0.0.1:18780','finalRules':[{'action':'allow','ip':['127.0.0.1/32'],'port':'18780'}]}
config={'log':{'loglevel':'warning'},'inbounds':inbounds,'outbounds':[{'tag':'internet','protocol':'freedom'},{'tag':'marker','protocol':'freedom','settings':marker}], 'routing':{'rules':[{'type':'field','ip':['198.18.0.42/32'],'outboundTag':'marker'}]}}
(root/'config.json').write_text(json.dumps(config))
processes=[subprocess.Popen([str(root/'xray'),'run','-c',str(root/'config.json')],stdout=open(root/'xray.log','w'),stderr=subprocess.STDOUT)]
try:
    logs=[]
    for index in range(3):
        log=root/f'cloudflared-{index}.log'; logs.append(log)
        processes.append(subprocess.Popen([str(cf),'tunnel','--no-autoupdate','--url',f'http://127.0.0.1:{18888+index}'],stdout=open(log,'w'),stderr=subprocess.STDOUT))
    profiles=['ss://'+base64.urlsafe_b64encode(('aes-128-gcm:'+password).encode()).decode().rstrip('=')+'@10.0.2.2:18891#Fixture']
    for index, protocol in enumerate(['vless','vmess','trojan']):
        deadline=time.monotonic()+100
        while True:
            match=re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)',logs[index].read_text())
            if match: break
            if time.monotonic()>deadline: raise RuntimeError('Temporary TLS fixture unavailable')
            time.sleep(1)
        host=match.group(1)
        if protocol=='vmess':
            data={'v':'2','add':host,'port':443,'id':identity,'aid':0,'net':'ws','type':'none','path':'/fixture','host':host,'tls':'tls','sni':host}
            profiles.append('vmess://'+base64.b64encode(json.dumps(data).encode()).decode())
        else:
            profiles.append(f'{protocol}://{password if protocol=="trojan" else identity}@{host}:443?security=tls&type=ws&path=%2Ffixture')
    (root/'profiles.json').write_text(json.dumps(profiles))
    print('FIXTURE_READY',flush=True)
    while all(p.poll() is None for p in processes): time.sleep(2)
    raise RuntimeError('Fixture process exited')
finally:
    for p in processes: p.terminate()
