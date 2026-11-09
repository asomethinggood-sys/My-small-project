"""One-owner, 45-minute phone acceptance trial. Never a shared/public VPN service.

Uses the same isolated namespace and sanitized official personal-use OpenVPN
input as the existing bounded probe. Only a verified German exit is selectable.
Credentials are encrypted to the session recipient; no plaintext is published.
"""
import base64
import json
import os
from pathlib import Path
import re
import secrets
import signal
import subprocess
import sys
import threading
import time
import uuid

from scripts.egress_openvpn_probe import probe, run, ProbeError, DNS_UDP_PROBE, assess_responses
from scripts.egress_sessions import Sessions, Evidence
from scripts.egress_control import Controller
from scripts.egress_ingress import LocalIngressPlane
from scripts.egress_gateway import Gateway
from scripts.egress_supervisor import Supervisor
from scripts.egress_xray import configurations
from scripts.egress_path_probe import probe as probe_issued_route

ROOT = Path(__file__).resolve().parents[1]


def trial(namespace, upstream, initial):
    # Positive/negative/positive controls before making the pool selectable.
    upstream.send_signal(signal.SIGSTOP)
    try:
        run('ip', '-n', namespace, 'link', 'set', 'nyx-vpn', 'down')
        for command in [
            ['python3', '-c', DNS_UDP_PROBE],
            ['curl', '--ipv4', '--fail', '--silent', '--max-time', '3', '--noproxy', '*', 'https://api.ipify.org?format=json']]:
            try:
                run('ip', 'netns', 'exec', namespace, *command, timeout=6)
            except ProbeError:
                pass
            else:
                raise ProbeError('private_trial_negative_control_failed')
    finally:
        run('ip', '-n', namespace, 'link', 'set', 'nyx-vpn', 'up')
        # Bringing a link down removes its default route on some kernels.
        run('ip', '-n', namespace, 'route', 'replace', 'default', 'dev', 'nyx-vpn')
        upstream.send_signal(signal.SIGCONT)
    run('ip', 'netns', 'exec', namespace, 'python3', '-c', DNS_UDP_PROBE, timeout=6)
    token=uuid.uuid4().hex[:8]
    host_link='nyxt'+token
    temporary=Path(os.environ['RUNNER_TEMP'])/'nyx-private-runtime'
    temporary.mkdir(mode=0o700)
    children=[]; gateway=None; supervisor=None; created=False
    try:
        run('ip','link','add',host_link,'type','veth','peer','name','nyx-in','netns',namespace)
        created=True
        run('ip','addr','add','198.19.250.1/30','dev',host_link)
        run('ip','link','set',host_link,'up')
        run('ip','-n',namespace,'addr','add','198.19.250.2/30','dev','nyx-in')
        run('ip','-n',namespace,'link','set','nyx-in','up')
        identity=str(uuid.uuid4()); path='/'+uuid.uuid4().hex
        config,_=configurations('198.19.250.2',identity,path)
        private=temporary/'xray.json';private.touch(mode=0o600);private.write_text(json.dumps(config))
        children.append(subprocess.Popen(['ip','netns','exec',namespace,str(ROOT/'.runtime/bin/xray'),'run','-c',str(private)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        sessions=Sessions(max_pools=1)
        # Explicitly scoped to this one owner's personal acceptance test. This
        # is not an approval to redistribute the provider to multiple users.
        sessions.register('personal-de','DE','vpnbook','openvpn',True)
        plane=LocalIngressPlane({'personal-de':('198.19.250.2',18888)},max_leases=4)
        key=secrets.token_urlsafe(32);owner='phone_trial'
        # Separate internal diagnostics quota must not consume phone renewal slots.
        diagnostic_key=secrets.token_urlsafe(32)
        controller=Controller(sessions,plane,{owner:key,'route_diagnostic':diagnostic_key})
        gateway=Gateway(controller,'trial.invalid',{'personal-de':(identity,path)})
        threading.Thread(target=gateway.serve_forever,daemon=True).start()
        route_ready=False
        route_report={}
        def verify_route(cancel):
            report=probe_issued_route('https://'+gateway.public_host,'route_diagnostic',diagnostic_key,'DE',ROOT/'.runtime/bin/xray',cancel)
            print('::notice title=Phone-path exit evidence::'+json.dumps(report),flush=True)
            if not report['country_verified']:
                controller.pool_failed('personal-de')
                raise ProbeError('issued_route_country_mismatch')
            route_report.clear();route_report.update(report)
            return Evidence('DE',True,True,True,True,True,time.monotonic()+150)
        def health(cancel):
            if upstream.poll() is not None or any(child.poll() is not None for child in children):
                raise ProbeError('trial_component_stopped')
            if route_ready:
                return verify_route(cancel)
            run('ip','netns','exec',namespace,'python3','-c',DNS_UDP_PROBE,timeout=6)
            observations={}
            urls=['https://api.ipify.org?format=json','https://ifconfig.co/json','https://ipwho.is/','https://ipinfo.io/json']
            for index,url in enumerate(urls):
                if cancel.is_set():raise ProbeError('trial_probe_cancelled')
                try:
                    text=run('ip','netns','exec',namespace,'curl','--ipv4','--fail','--silent','--connect-timeout','3','--max-time','4','--max-filesize','32768','--proto','=https','--noproxy','*',url,timeout=5)
                    value=json.loads(text)
                    if not isinstance(value,dict):continue
                    observations[index]=value
                except (ProbeError,ValueError):pass
            if not assess_responses(observations)['country_verified']:raise ProbeError('exit_not_verified')
            return Evidence('DE',True,True,True,True,True,time.monotonic()+90)
        supervisor=Supervisor(controller,{'personal-de':health},interval=45,timeout=40)
        cf_log=temporary/'connector.log'
        with cf_log.open('w') as log:
            children.append(subprocess.Popen([str(ROOT/'.runtime/bin/cloudflared'),'tunnel','--no-autoupdate','--url',f'http://127.0.0.1:{gateway.server_address[1]}'],stdout=log,stderr=subprocess.STDOUT))
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            supervisor.tick()
            match=re.search(r'https://([a-z0-9-]+\.trycloudflare\.com)',cf_log.read_text())
            if match and sessions.pools['personal-de']['ready']:break
            if any(child.poll() is not None for child in children):raise ProbeError('trial_start_failed')
            time.sleep(.25)
        else:raise ProbeError('verified_trial_not_ready')
        gateway.public_host=match.group(1)
        # Do not hand out a country label based only on namespace traffic.
        # This must pass through the issued TLS/WS lease used by phone clients.
        verify_route(threading.Event())
        route_ready=True
        duration=2700
        provision=json.dumps({'countryService':'https://'+gateway.public_host,'countryUser':owner,'countryKey':key,'country':'DE','exit_ip':route_report['exit_ipv4'],'observed_countries':route_report['observed_countries'],'expires_at':int(time.time())+duration},separators=(',',':')).encode()
        encrypted=subprocess.run(['openssl','pkeyutl','-encrypt','-pubin','-inkey',str(ROOT/'config/trial-recipient.pub'),'-pkeyopt','rsa_padding_mode:oaep','-pkeyopt','rsa_oaep_md:sha256'],input=provision,capture_output=True,check=True).stdout
        ciphertext=base64.b64encode(encrypted).decode()
        # GitHub buffers check annotations until job completion. Publish only
        # ciphertext on the session branch so the owner can obtain it while the
        # private trial is still alive. No URL/key/profile is public plaintext.
        repository=os.environ['GITHUB_REPOSITORY']
        branch=os.environ['GITHUB_REF_NAME']
        if branch!='arena/f056ce38-my-small-project':raise ProbeError('trial_branch_rejected')
        endpoint=f'repos/{repository}/contents/trial-handoff.json'
        prior=subprocess.run(['gh','api',endpoint+'?ref='+branch],capture_output=True,text=True)
        body={'message':'Publish encrypted private trial handoff','branch':branch,
              'content':base64.b64encode(json.dumps({'run_id':os.environ['GITHUB_RUN_ID'],'ciphertext':ciphertext}).encode()).decode()}
        if prior.returncode==0:body['sha']=json.loads(prior.stdout)['sha']
        subprocess.run(['gh','api','--method','PUT',endpoint,'--input','-'],input=json.dumps(body),text=True,capture_output=True,check=True)
        print('::notice title=Private trial encrypted provisioning::'+ciphertext,flush=True)
        print('::notice title=Private live trial::One-owner Germany trial ready; real geography quorum and UDP checks passed. Automatic shutdown in 45 minutes. Other countries unavailable.',flush=True)
        end=time.monotonic()+duration
        while time.monotonic()<end:
            supervisor.tick()
            if upstream.poll() is not None or any(child.poll() is not None for child in children):break
            time.sleep(.25)
    finally:
        if supervisor:supervisor.close()
        if gateway:gateway.shutdown();gateway.server_close()
        for child in children:
            child.terminate()
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if created:run('ip','link','del',host_link)


def main():
    path=Path(os.environ['RUNNER_TEMP'])/'nyx-personal-upstream.json'
    try:
        envelope=json.loads(path.read_text());path.unlink()
        result=probe(envelope,private_trial=trial)
        print('::notice title=Private trial result::'+json.dumps(result),flush=True)
        return 0 if result.get('country_verified') and result.get('host_main_routes_unchanged') else 1
    except Exception:
        # No exception text: it can contain private provisioning/configuration.
        print('::error::Private trial failed closed; no credentials or routes published.',flush=True)
        return 1
    finally:path.unlink(missing_ok=True)


if __name__=='__main__':sys.exit(main())
