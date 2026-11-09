#!/usr/bin/env python3
"""One bounded HTTPS metadata fetch per official source. No provisioning/connects."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

SOURCES = {
    'vpnbook-openvpn': 'https://www.vpnbook.com/freevpn/openvpn',
    'vpnbook-wireguard': 'https://www.vpnbook.com/freevpn/wireguard-vpn',
    'warp': 'https://developers.cloudflare.com/warp-client/known-issues-and-faq/',
    'psiphon': 'https://api.github.com/repos/Psiphon-Labs/psiphon-tunnel-core',
    'proton-wireguard': 'https://protonvpn.com/support/wireguard-configurations',
    'riseup': 'https://riseup.net/en/vpn',
}
LIMIT = 2 * 1024 * 1024


class SameSiteRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if new.scheme != 'https' or new.hostname != old.hostname or new.username or new.password:
            raise ValueError('Unexpected provider redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(source, url):
    started = time.monotonic()
    result = {'source': source, 'url': url, 'status': 'unavailable',
              'connection_tested': False, 'provisioning_tested': False}
    try:
        opener = urllib.request.build_opener(SameSiteRedirect())
        request = urllib.request.Request(url, headers={'User-Agent': 'Nyx-Repository-Research/1.0'})
        with opener.open(request, timeout=20) as response:
            body = response.read(LIMIT + 1)
            if len(body) > LIMIT:
                raise ValueError('Response size budget exceeded')
            result.update(status='fetched', http_status=response.status,
                          bytes=len(body), body_sha256=hashlib.sha256(body).hexdigest())
        if source.startswith('vpnbook-'):
            # Advertising only, not DNS/IP verification, credentials or configs.
            text = body.decode('utf-8', errors='replace')
            endpoints = sorted(set(re.findall(r'\b(?:de|fr|us|ca|uk|gb)\d+\.vpnbook\.com\b', text.lower())))
            result['advertised_endpoints'] = endpoints[:100]
            result['advertised_countries'] = sorted({('GB' if e[:2] == 'uk' else e[:2].upper()) for e in endpoints})
    except urllib.error.HTTPError as error:
        result.update(status='http_error', http_status=error.code)
    except (OSError, ValueError, urllib.error.URLError):
        result['status'] = 'transport_or_validation_error'
    result['elapsed_ms'] = round((time.monotonic() - started) * 1000)
    return result


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch, source, url) for source, url in SOURCES.items()]
        results = [future.result() for future in futures]
    path = Path('.runtime/egress/sources.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'generated_at': int(time.time()), 'sources': results}, indent=2) + '\n')
    for result in results:
        print(result['source'] + ': ' + result['status'])
    # Fetch failures are observations; no source is silently promoted to usable.
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
