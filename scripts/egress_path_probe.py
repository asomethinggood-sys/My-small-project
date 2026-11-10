"""Check an issued TLS country route, not the runner's ordinary/default egress.

Private profiles and API credentials stay in memory / mode-600 temporary files.
Published diagnostics contain only exit evidence and runner-origin timings.
"""
import json
import os
from pathlib import Path
import re
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
import urllib.error
from urllib.parse import urlsplit, parse_qs
import uuid

from scripts.egress_openvpn_probe import assess_responses


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Control-channel redirects rejected')


def client_config(service, lease, country, port):
    origin=urlsplit(service);profile=urlsplit(lease['profile'])
    options=parse_qs(profile.query)
    if (origin.scheme!='https' or origin.port not in (None,443) or origin.username
            or origin.password or origin.path not in ('','/') or origin.query or origin.fragment
            or not origin.hostname or not re.fullmatch(r'[a-z0-9.-]+',origin.hostname)):
        raise ValueError('HTTPS root required')
    token=lease['token'];generation=lease['generation'];ttl=lease['expires_in']
    if (lease['country']!=country or not re.fullmatch('[A-Z]{2}',country)
            or not re.fullmatch('[A-Za-z0-9_-]{43}',token)
            or type(generation) is not int or generation<1
            or type(ttl) is not int or not 1<=ttl<=300
            or profile.scheme!='vless' or profile.hostname!=origin.hostname
            or profile.port!=443 or profile.password is not None
            or options.get('security')!=['tls'] or options.get('type')!=['ws']
            or options.get('sni')!=[origin.hostname] or options.get('host')!=[origin.hostname]
            or options.get('path')!=[f'/s/{token}/{generation}']
            or type(port) is not int or not 1024<=port<=65535):
        raise ValueError('Issued route binding rejected')
    identity=str(uuid.UUID(profile.username))
    return {'log':{'loglevel':'none'},
            'inbounds':[{'listen':'127.0.0.1','port':port,'protocol':'socks','settings':{'auth':'noauth','udp':True}}],
            'outbounds':[{'protocol':'vless','settings':{'vnext':[{'address':origin.hostname,'port':443,'users':[{'id':identity,'encryption':'none'}]}]},
                          'streamSettings':{'network':'ws','security':'tls','tlsSettings':{'serverName':origin.hostname,'allowInsecure':False},
                                            'wsSettings':{'path':options['path'][0],'headers':{'Host':origin.hostname}}}}]}


def request(service, user, key, path, body):
    origin=urlsplit(service)
    if (origin.scheme!='https' or not origin.hostname or origin.port not in (None,443)
            or origin.username or origin.password or origin.path not in ('','/') or origin.query or origin.fragment):
        raise ValueError('HTTPS root required before sending credentials')
    req=urllib.request.Request(service.rstrip('/')+path,json.dumps(body).encode(),
        {'Authorization':'Bearer '+key,'X-Nyx-User':user,'Content-Type':'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=5) as response:
        payload=response.read(8193)
        if len(payload)>8192:raise ValueError('Oversized control response')
        return json.loads(payload)


def await_service(service, user, key, country, cancel):
    """Bounded read-only connector warmup; never retry lease creation."""
    origin=urlsplit(service)
    if (origin.scheme!='https' or not origin.hostname or origin.port not in (None,443)
            or origin.username or origin.password or origin.path not in ('','/') or origin.query or origin.fragment):
        raise ValueError('HTTPS root required before sending credentials')
    for attempt in range(8):
        if cancel.is_set():raise ValueError('Probe cancelled')
        try:
            req=urllib.request.Request(service.rstrip('/')+'/v1/availability',headers={'Authorization':'Bearer '+key,'X-Nyx-User':user})
            with urllib.request.build_opener(NoRedirect()).open(req,timeout=3) as response:
                payload=response.read(8193)
                if len(payload)>8192:raise ValueError('Oversized availability')
                value=json.loads(payload)
                if not any(row.get('country')==country for row in value.get('countries',[])):
                    raise ValueError('Requested country unavailable')
                return
        except urllib.error.HTTPError as error:
            if error.code not in (404,502,503,504) or attempt==7:raise
        except (urllib.error.URLError,OSError) as error:
            reason=getattr(error,'reason',error)
            print('::notice title=TLS readiness diagnostic::'+type(reason).__name__+'; errno='+str(getattr(reason,'errno',None)),flush=True)
            if attempt==7:raise
        cancel.wait(2)


def exact(stream, size):
    data=b''
    while len(data)<size:
        part=stream.recv(size-len(data))
        if not part:raise ValueError('Truncated SOCKS reply')
        data+=part
    return data


def udp_dns(port):
    with socket.create_connection(('127.0.0.1',port),timeout=5) as control, socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as udp:
        udp.settimeout(5);control.sendall(b'\x05\x01\x00')
        if exact(control,2)!=b'\x05\x00':raise ValueError('SOCKS authentication rejected')
        control.sendall(b'\x05\x03\x00\x01'+bytes(6))
        if exact(control,4)!=b'\x05\x00\x00\x01':raise ValueError('UDP association rejected')
        host=socket.inet_ntoa(exact(control,4));relay_port=struct.unpack('!H',exact(control,2))[0]
        if host not in ('0.0.0.0','127.0.0.1'):raise ValueError('Nonlocal relay rejected')
        identity=os.urandom(2)
        query=identity+struct.pack('!HHHHH',0x100,1,0,0,0)+bytes.fromhex('076578616d706c6503636f6d0000010001')
        header=b'\x00\x00\x00\x01'+socket.inet_aton('1.1.1.1')+struct.pack('!H',53)
        udp.sendto(header+query,('127.0.0.1',relay_port));data,peer=udp.recvfrom(4096)
        if peer!=('127.0.0.1',relay_port) or data[:10]!=header:raise ValueError('Wrong UDP response route')
        reply=data[10:]
        if len(reply)<12 or reply[:2]!=identity:raise ValueError('Wrong DNS transaction')
        flags,_,answers=struct.unpack('!HHH',reply[2:8])
        if not flags&0x8000 or flags&15 or not answers:raise ValueError('DNS answer rejected')


def probe(service, user, key, country, xray, cancel):
    lease=None;process=None;stage='https_service_readiness'
    try:
        await_service(service,user,key,country,cancel)
        stage='https_session_acquire'
        lease=request(service,user,key,'/v1/sessions',{'country':country,'require_udp':True})
        stage='validate_issued_profile'
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
        config=client_config(service,lease,country,port)
        with tempfile.TemporaryDirectory(prefix='nyx-route-check-') as directory:
            path=Path(directory)/'client.json';path.touch(mode=0o600);path.write_text(json.dumps(config))
            process=subprocess.Popen([str(xray),'run','-c',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            deadline=time.monotonic()+3
            while True:
                if process.poll() is not None or cancel.is_set():raise ValueError('Probe stopped')
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.2):break
                except OSError:
                    if time.monotonic()>=deadline:raise ValueError('Probe client did not start')
                    time.sleep(.05)
            stage='issued_route_udp_dns'
            udp_dns(port)
            stage='issued_route_https_geography'
            observations={};timings={}
            urls=['https://api.ipify.org?format=json','https://ifconfig.co/json','https://ipwho.is/','https://ipinfo.io/json','https://api.country.is/']
            for index,url in enumerate(urls):
                if cancel.is_set():raise ValueError('Probe cancelled')
                began=time.monotonic()
                result=subprocess.run(['curl','--ipv4','--fail','--silent','--connect-timeout','3','--max-time','4','--max-filesize','32768',
                    '--proto','=https','--noproxy','','--proxy',f'socks5h://127.0.0.1:{port}',url],capture_output=True,timeout=5,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin'})
                if result.returncode==0:
                    try:
                        value=json.loads(result.stdout)
                        if isinstance(value,dict) and isinstance(value.get('ip'),str):observations[index]=value
                        timings[str(index)]=round((time.monotonic()-began)*1000)
                    except ValueError:pass
            assessment=assess_responses(observations, expected_country=country, require_conflict_source=True)
            assessment.update(path='issued_tls_gateway_route',udp_dns_passed=True,runner_https_ms=timings)
            return assessment
    except Exception as error:
        # Only fixed stage/class identifiers, never exception text or URI/key.
        print('::error title=Issued-route probe::'+stage+'; '+type(error).__name__,flush=True)
        raise
    finally:
        if process is not None:
            process.terminate()
            try:process.wait(timeout=3)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        try:
            if lease is not None:request(service,user,key,'/v1/disconnect',{'token':lease['token']})
        except Exception:pass  # Server-side lease expiration remains enforced.
