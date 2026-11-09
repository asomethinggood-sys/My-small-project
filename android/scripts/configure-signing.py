"""Install CI signing material only in the ephemeral runner temp directory."""
import base64
import os
from pathlib import Path
names=['CONTINUUM_SIGNING_KEY_B64','CONTINUUM_STORE_PASSWORD','CONTINUUM_KEY_ALIAS','CONTINUUM_KEY_PASSWORD']
values={name:os.environ.get(name,'') for name in names}
if not any(values.values()):
    print('::warning::Stable signing secrets are not configured; this remains a disposable preview certificate.')
else:
    if not all(values.values()):raise SystemExit('Incomplete signing configuration; no key values were logged.')
    if any('\n' in values[n] or '\r' in values[n] for n in names[1:]):raise SystemExit('Signing passwords/alias must be single-line values.')
    key=Path(os.environ['RUNNER_TEMP'])/'continuum-release.jks'
    fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as out:out.write(base64.b64decode(values[names[0]],validate=True))
    with open(os.environ['GITHUB_ENV'],'a') as env:
        env.write(f'CONTINUUM_KEYSTORE_PATH={key}\n')
        for name in names[1:]:env.write(f'{name}={values[name]}\n')
    print('Private signing material configured in runner temp; not in workspace or artifacts.')
