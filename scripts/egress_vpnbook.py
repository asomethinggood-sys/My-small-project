#!/usr/bin/env python3
"""Bounded official German OpenVPN bundle inspection, no connection/publication.

Never persists credentials, archives, configuration bodies or keys. No CAPTCHA or
WireGuard generator interaction. Provider sharing policy is still a deployment gate.
"""
import io
import json
from pathlib import Path
import re
import socket
import sys
import urllib.parse
import urllib.request
import zipfile
from html.parser import HTMLParser

from scripts.egress_config import global_ip
from scripts.egress_openvpn import sanitize
from scripts.egress_sources import SameSiteRedirect

PAGE = 'https://www.vpnbook.com/freevpn/openvpn'
LIMIT = 2 * 1024 * 1024


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.words = [], []
        self.routes = set()
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for field in ('href', 'src', 'action'):
            value = attributes.get(field, '')
            parts = urllib.parse.urlsplit(urllib.parse.urljoin(PAGE, value))
            if (value and parts.hostname == 'www.vpnbook.com' and parts.scheme == 'https'
                    and re.fullmatch(r'/[A-Za-z0-9_./-]{0,160}', parts.path)
                    and any(term in parts.path.lower() for term in ('openvpn', 'download', 'config', '.js'))):
                query_keys = sorted(key for key in urllib.parse.parse_qs(parts.query)
                                    if re.fullmatch('[A-Za-z0-9_-]{1,32}', key))
                self.routes.add(parts.path + ('?keys=' + ','.join(query_keys) if query_keys else ''))
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag == 'a':
            href = dict(attrs).get('href', '')
            url = urllib.parse.urljoin(PAGE, href)
            parts = urllib.parse.urlsplit(url)
            if (parts.scheme == 'https' and parts.hostname == 'www.vpnbook.com'
                    and not parts.username and not parts.password
                    and parts.path.lower().endswith('.zip') and 'de' in parts.path.lower()):
                self.links.append(url)

    def handle_endtag(self, tag):
        if tag in ('script', 'style') and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.words.append(data)


def fetch(url):
    opener = urllib.request.build_opener(SameSiteRedirect())
    with opener.open(urllib.request.Request(url, headers={'User-Agent': 'Nyx-Repository-Research/1.0'}), timeout=20) as response:
        body = response.read(LIMIT + 1)
    if len(body) > LIMIT:
        raise ValueError('Source exceeds size budget')
    return body


def profile_metadata(config):
    # Never tokenize PEM/key bodies as directive names: even a short base64
    # prefix is sensitive. Export a closed vocabulary of names, not raw tokens.
    known = {'client', 'dev', 'proto', 'remote', 'resolv-retry', 'nobind',
             'persist-key', 'persist-tun', 'remote-cert-tls', 'verb', 'auth-user-pass',
             'auth', 'cipher', 'data-ciphers', 'tls-version-min', 'key-direction',
             'explicit-exit-notify', 'comp-lzo', 'compress', 'route', 'redirect-gateway',
             'auth-nocache', 'mute-replay-warnings', 'sndbuf', 'rcvbuf', 'pull',
             'fast-io', 'reneg-sec', 'route-method', 'route-delay', 'up', 'down',
             'script-security', 'plugin', 'config', 'verify-x509-name', 'setenv'}
    names, blocks, current = set(), set(), None
    for raw in config.splitlines():
        line = raw.strip()
        if current:
            if line == '</' + current + '>':
                current = None
            continue
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('<') and not line.startswith('</'):
            current = line[1:-1]
            blocks.add(current if current in {'ca', 'cert', 'key', 'tls-auth', 'tls-crypt'} else 'other')
            continue
        name = line.split()[0]
        names.add(name if name in known else 'other')
    return {'directive_names': sorted(names), 'inline_blocks': sorted(blocks)}


def inspect_bundle(blob):
    report = {'status': 'bundle_downloaded', 'connectable': False, 'connection_tested': False}
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        entries = archive.infolist()
        if len(entries) > 32 or sum(item.file_size for item in entries) > LIMIT:
            raise ValueError('Archive size budget exceeded')
        candidates = [item for item in entries if item.filename.lower().endswith('.ovpn')
                      and 'udp' in item.filename.lower() and item.file_size <= 128 * 1024]
        if not candidates:
            report['status'] = 'no_udp_profile'
            return report
        # Read one member in memory. Never extract provider-controlled paths.
        config = archive.read(sorted(candidates, key=lambda item: item.filename)[0]).decode('utf-8-sig')
        report.update(profile_metadata(config))
        remote = re.search(r'^[ \t]*remote[ \t]+([A-Za-z0-9.-]+)[ \t]+(\d+)[ \t]*$', config, re.M)
        if not remote:
            report['status'] = 'unsupported_remote_syntax'
            return report
        hostname = remote[1]
        if not re.fullmatch(r'de\d+\.vpnbook\.com', hostname.lower()):
            # A public numeric address is accepted only as an advertised, unverified exit.
            try:
                address = str(global_ip(hostname))
            except ValueError:
                report['status'] = 'unexpected_endpoint'
                return report
        else:
            addresses = sorted({str(global_ip(item[4][0])) for item in
                                socket.getaddrinfo(hostname, int(remote[2]), socket.AF_INET, socket.SOCK_DGRAM)})
            if not addresses:
                report['status'] = 'endpoint_resolution_failed'
                return report
            address = addresses[0]
        config = config[:remote.start()] + f'remote {address} {remote[2]}' + config[remote.end():]
        try:
            parsed = sanitize(config)
        except ValueError as error:
            # Sanitizer messages are fixed categories, not config values.
            report.update(status='rejected_by_security_policy', reason=str(error))
            return report
        report.update(status='sanitized_unverified', transport=parsed['transport'],
                      credentials_required=parsed['credentials_required'])
        return report


def inspect_profile(blob):
    if len(blob) > 128 * 1024:
        raise ValueError('Profile size budget exceeded')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('profile-udp.ovpn', blob)
    return inspect_bundle(buffer.getvalue())


def main():
    if sys.argv[1:] in (['--profile-stdin'], ['--bundle-stdin']):
        try:
            limit = 128 * 1024 if sys.argv[1] == '--profile-stdin' else LIMIT
            blob = sys.stdin.buffer.read(limit + 1)
            if len(blob) > limit:
                raise ValueError('Download size budget exceeded')
            result = inspect_profile(blob) if sys.argv[1] == '--profile-stdin' else inspect_bundle(blob)
        except (OSError, ValueError, zipfile.BadZipFile):
            result = {'status': 'download_validation_error', 'connection_tested': False}
        print(json.dumps(result))
        return
    report = {'provider': 'vpnbook', 'type': 'openvpn', 'advertised_country': 'DE',
              'shared_use_approved': False, 'connection_tested': False}
    try:
        page = Page()
        page.feed(fetch(PAGE).decode('utf-8', errors='replace'))
        text = ' '.join(' '.join(page.words).split())
        username = re.search(r'\bUsername\s*:\s*(vpnbook)\b', text, re.I)
        password = re.search(r'\bPassword\s*:\s*([A-Za-z0-9_-]{4,64})\b', text, re.I)
        report['public_credentials_detected'] = bool(username and password)
        links = sorted(set(page.links))
        report['german_bundle_links'] = len(links)
        report['download_page_routes'] = sorted(page.routes)[:20]
        if links:
            report.update(inspect_bundle(fetch(links[0])))
        else:
            report['status'] = 'no_supported_german_bundle_link'
            # Inspect bounded public frontend code for documented-page download
            # routes; do not call discovered APIs or execute JavaScript.
            routes = set()
            budget = 4 * 1024 * 1024
            for path in sorted(page.routes)[:12]:
                if not path.endswith('.js') or not path.startswith('/_next/static/'):
                    continue
                code = fetch('https://www.vpnbook.com' + path)
                budget -= len(code)
                if budget < 0:
                    break
                text = code.decode('utf-8', errors='replace')
                routes.update(re.findall(r'/api/[A-Za-z0-9_/-]{1,100}', text))
            report['frontend_api_routes'] = sorted(routes)[:20]
    except (OSError, ValueError, zipfile.BadZipFile):
        report['status'] = 'source_or_validation_error'
    destination = Path('.runtime/egress/vpnbook-inspection.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print('::notice title=Nyx VPNBook inspection::' + report['status']
          + '; public credentials detected=' + str(report.get('public_credentials_detected', False))
          + '; German bundle links=' + str(report.get('german_bundle_links', 0)))
    if 'reason' in report:
        print('::notice title=Nyx VPNBook policy::' + report['reason'])
    for route in report.get('frontend_api_routes', []):
        print('::notice title=Nyx VPNBook frontend API route::' + route)
    for route in report.get('download_page_routes', []):
        print('::notice title=Nyx VPNBook route::' + route)


if __name__ == '__main__':
    main()
