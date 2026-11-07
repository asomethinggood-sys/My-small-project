#!/usr/bin/env python3
"""Point the Worker at an already-probed Quick Tunnel. Never logs the token."""
import argparse
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request


def payload(host, now=None):
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com', host) or len(host) > 253:
        raise ValueError('Expected a Quick Tunnel hostname, not a URL or IP')
    now = time.time() if now is None else now
    # Five-minute margin for clock skew versus the Worker's six-hour maximum.
    return {'host': host, 'expiresAt': int((now + 5 * 3600 + 55 * 60) * 1000)}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('backend')
    args = p.parse_args()
    token = os.environ.get('RELAY_UPDATE_TOKEN', '')
    if len(token) < 32 or '\n' in token or '\r' in token:
        raise SystemExit('Set RELAY_UPDATE_TOKEN to the shared secret (at least 32 characters)')
    profile = json.loads((Path(__file__).resolve().parents[1] / 'worker/profile.json').read_text())
    req = urllib.request.Request(f"https://{profile['host']}/__route",
        data=json.dumps(payload(args.backend)).encode(), method='POST',
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'})
    # Do not leak the bearer secret by following redirects to another endpoint.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=30) as result:
            if result.status != 200:
                raise SystemExit('Relay update rejected; no config may be published')
    except urllib.error.HTTPError as exc:
        raise SystemExit(f'Relay update HTTP {exc.code}; check Worker code, binding and shared secret') from None
    except urllib.error.URLError:
        raise SystemExit('Relay update connection failed; no config may be published') from None
    print('Route accepted. This is NOT proof of proxy connectivity; run the full VLESS check next.')
