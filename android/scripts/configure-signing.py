"""Install CI signing material only in the ephemeral runner temp directory."""
import base64
import os
import secrets
import subprocess
from pathlib import Path
names=['CONTINUUM_SIGNING_KEY_B64','CONTINUUM_STORE_PASSWORD','CONTINUUM_KEY_ALIAS','CONTINUUM_KEY_PASSWORD']
values={name:os.environ.get(name,'') for name in names}
if not any(values.values()):
    # Do not sign a non-debuggable release with Android's generic debug key.
    # This is still an ephemeral candidate key, not stable update signing.
    password=secrets.token_urlsafe(32)
    print('::add-mask::'+password)
    key=Path(os.environ['RUNNER_TEMP'])/'nyx-candidate-release.p12'
    old_umask=os.umask(0o077)
    try:
        subprocess.run(['keytool','-genkeypair','-keystore',str(key),'-storetype','PKCS12',
                        '-storepass:env','NYX_CANDIDATE_PASSWORD','-keypass:env','NYX_CANDIDATE_PASSWORD',
                        '-alias','nyx-candidate','-keyalg','RSA','-keysize','3072','-validity','3650',
                        '-dname','CN=Nyx VPN Candidate,O=Nyx Development','-noprompt'],
                       check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                       env={**os.environ,'NYX_CANDIDATE_PASSWORD':password})
    finally:
        os.umask(old_umask)
    key.chmod(0o600)
    with open(os.environ['GITHUB_ENV'],'a') as env:
        env.write(f'CONTINUUM_KEYSTORE_PATH={key}\nCONTINUUM_STORE_PASSWORD={password}\nCONTINUUM_KEY_ALIAS=nyx-candidate\nCONTINUUM_KEY_PASSWORD={password}\nNYX_SIGNING_MODE=ephemeral_release_key\n')
    print('::warning::Dedicated release certificate generated for this candidate only. Stable signing is NOT provisioned; future updates may require reinstall.')
else:
    if not all(values.values()):raise SystemExit('Incomplete signing configuration; no key values were logged.')
    if any('\n' in values[n] or '\r' in values[n] for n in names[1:]):raise SystemExit('Signing passwords/alias must be single-line values.')
    key=Path(os.environ['RUNNER_TEMP'])/'continuum-release.jks'
    fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:out.write(base64.b64decode(values[names[0]],validate=True))
    with open(os.environ['GITHUB_ENV'],'a') as env:
        env.write(f'CONTINUUM_KEYSTORE_PATH={key}\nNYX_SIGNING_MODE=provisioned_release_key\n')
        for name in names[1:]:env.write(f'{name}={values[name]}\n')
    print('Private signing material configured in runner temp; not in workspace or artifacts.')
