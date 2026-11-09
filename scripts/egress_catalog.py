#!/usr/bin/env python3
"""Bounded metadata discovery only. Never connect, execute configs or publish profiles."""
import argparse
import csv
import hashlib
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
import time
import urllib.request

MAX_BYTES = 8 * 1024 * 1024
MAX_ROWS = 10000
DIRECTORY_URL = 'https://www.vpngate.net/api/iphone/'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Directory redirect refused')


def fetch_directory():
    # Fixed official HTTPS destination; no user-supplied URLs or HTTP downgrade.
    opener = urllib.request.build_opener(NoRedirect())
    with opener.open(DIRECTORY_URL, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Directory HTTP failure')
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError('Directory exceeds size budget')
    return data.decode('utf-8-sig', errors='strict')


def validate_policy(policy):
    countries = policy['target_countries']
    if (policy.get('schema_version') != 1 or not isinstance(countries, list)
            or len(countries) != 30 or len(set(countries)) != 30
            or any(not re.fullmatch('[A-Z]{2}', c) for c in countries)):
        raise ValueError('Expected 30 distinct country codes')
    ttl = policy['catalog_ttl_seconds']
    if type(ttl) is not int or not 60 <= ttl <= 3600:
        raise ValueError('Invalid catalog TTL')
    providers = policy['providers']
    ids = [p['id'] for p in providers]
    if len(set(ids)) != len(ids) or 'vpngate' not in ids:
        raise ValueError('Invalid provider registry')
    for provider in providers:
        if (not re.fullmatch('[a-z][a-z0-9_-]{0,31}', provider['id'])
                or type(provider['shared_use_approved']) is not bool):
            raise ValueError('Invalid provider policy')


def parse_vpngate(text, countries):
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Directory exceeds size budget')
    lines = text.splitlines()
    if not lines or lines[0].strip() != '*vpn_servers':
        raise ValueError('Not a VPN Gate CSV directory')
    if len(lines) < 3 or not lines[1].startswith('#HostName,'):
        raise ValueError('Missing directory header')
    reader = csv.DictReader(io.StringIO('\n'.join([lines[1][1:]] + lines[2:])))
    required = {'IP', 'CountryShort', 'OpenVPN_ConfigData_Base64'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Missing required directory columns')
    found = {}
    for index, row in enumerate(reader):
        if index >= MAX_ROWS:
            raise ValueError('Directory exceeds row budget')
        if row.get('HostName') == '*':
            break
        country = row.get('CountryShort', '')
        if country not in countries or not row.get('OpenVPN_ConfigData_Base64'):
            continue
        try:
            address = ipaddress.ip_address(row.get('IP', ''))
        except ValueError:
            continue
        if not address.is_global or address.is_multicast:
            continue
        # Server counts are unique provider/IPs, not protocols, configs or host aliases.
        key = str(address)
        if key in found and found[key]['country'] != country:
            raise ValueError('Conflicting country labels for one server')
        found[key] = {
            'id': hashlib.sha256(('vpngate:' + key).encode()).hexdigest()[:24],
            'provider': 'vpngate', 'country': country,
            'status': 'discovered_unverified', 'protocol': 'openvpn',
        }
    # Intentionally discard addresses, credentials, raw configs and provider metrics.
    return sorted(found.values(), key=lambda item: (item['country'], item['id']))


def build_catalog(policy, observations, sources, now=None):
    validate_policy(policy)
    now = int(time.time()) if now is None else now
    rows = []
    for country in policy['target_countries']:
        candidates = [o for o in observations if o['country'] == country]
        rows.append({
            'country': country,
            'discovered_servers': len(candidates),
            'discovered_providers': len({o['provider'] for o in candidates}),
            # Discovery NEVER promotes an endpoint to usable, even if policy is approved.
            'verified_servers': 0, 'verified_providers': 0,
            'selectable': False,
            'status': 'unverified' if candidates else 'unavailable',
        })
    return {
        'schema_version': 1, 'purpose': 'research_metadata_not_connection_profiles',
        'generated_at': now, 'expires_at': now + policy['catalog_ttl_seconds'],
        'countries': rows, 'providers': policy['providers'],
        'sources': sources, 'observations': observations,
        'routing_implemented': False,
    }


def attach_advertisements(catalog, source_report):
    """Keep provider advertisements separate from discovered/verified servers."""
    now = catalog['generated_at']
    timestamp = source_report.get('generated_at', 0)
    fresh = (type(timestamp) is int and now - 900 <= timestamp <= now + 60)
    advertised = set()
    if fresh:
        for source in source_report.get('sources', []):
            kind = {'vpnbook-openvpn': 'openvpn', 'vpnbook-wireguard': 'wireguard'}.get(source.get('source'))
            if not kind or source.get('status') != 'fetched':
                continue
            for endpoint in source.get('advertised_endpoints', []):
                if not isinstance(endpoint, str):
                    continue
                match = re.fullmatch(r'(de|fr|us|ca|uk|gb)[0-9]{1,4}\.vpnbook\.com', endpoint)
                if match:
                    country = 'GB' if match[1] == 'uk' else match[1].upper()
                    advertised.add((country, 'vpnbook', kind, endpoint))
    for row in catalog['countries']:
        candidates = [item for item in advertised if item[0] == row['country']]
        row['advertised_endpoints'] = len({(item[1], item[3]) for item in candidates})
        row['advertised_providers'] = len({item[1] for item in candidates})
        for entry in row.get('exits', []):
            entry['advertised_endpoints'] = len({item[3] for item in candidates
                                                 if item[1] == entry['provider'] and item[2] == entry['type']})
    return catalog


def atomic_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.catalog-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', default='config/egress.json')
    parser.add_argument('--adapters', default='config/egress-adapters.json')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--live', action='store_true')
    source.add_argument('--fixture', type=Path)
    parser.add_argument('--output', default='.runtime/egress/catalog.json')
    args = parser.parse_args()
    policy = json.loads(Path(args.policy).read_text())
    validate_policy(policy)
    observations, sources = [], []
    failed = False
    if args.live or args.fixture:
        try:
            text = fetch_directory() if args.live else args.fixture.read_text()
            observations = parse_vpngate(text, set(policy['target_countries']))
            sources.append({'provider': 'vpngate', 'status': 'fetched',
                            'mode': 'live' if args.live else 'fixture'})
        except (OSError, ValueError, csv.Error):
            # Do not leak raw responses/configs in diagnostics or retain stale candidates.
            sources.append({'provider': 'vpngate', 'status': 'fetch_or_parse_failed'})
            failed = True
    else:
        sources.append({'provider': 'vpngate', 'status': 'not_fetched'})
    result = build_catalog(policy, observations, sources)
    registry = json.loads(Path(args.adapters).read_text())
    result['adapters'] = registry['adapters']
    # Per-provider/protocol breakdown does not imply working connections.
    for country in result['countries']:
        country['exits'] = [dict(
            adapter=adapter['id'], provider=adapter['provider'], type=adapter['type'],
            discovered_servers=sum(1 for item in observations
                                   if item['country'] == country['country']
                                   and item['provider'] == adapter['provider']
                                   and item['protocol'] == adapter['type']),
            verified_servers=0, selectable=False, udp=adapter['udp'])
            for adapter in registry['adapters']]
    source_path = Path('.runtime/egress/sources.json')
    source_report = json.loads(source_path.read_text()) if source_path.exists() else {}
    attach_advertisements(result, source_report)
    atomic_write(args.output, result)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
