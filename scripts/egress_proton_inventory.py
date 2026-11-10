"""Bounded Proton public directory observation, not account authorization.

The endpoint may require authorization or change without notice. Never retry a
denied response or use this metadata to bypass free-plan selection restrictions.
"""
import ipaddress
import json
import re
import urllib.request

from scripts.egress_catalog import NoRedirect

URL = 'https://api.protonmail.ch/vpn/logicals'
LIMIT = 32 * 1024 * 1024
MAX_LOGICAL = 100000


def fetch_directory():
    request = urllib.request.Request(URL, headers={'User-Agent': 'Nyx-Repository-Research/1.0'})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        if response.status != 200: raise ValueError('Directory HTTP failure')
        data = response.read(LIMIT + 1)
    if len(data) > LIMIT: raise ValueError('Directory exceeds size budget')
    return json.loads(data)


def inspect(value, targets):
    if not isinstance(value, dict) or not isinstance(value.get('LogicalServers'), list):
        raise ValueError('Unsupported Proton directory schema')
    rows = value['LogicalServers']
    if len(rows) > MAX_LOGICAL: raise ValueError('Directory exceeds row budget')
    logical, endpoints = {}, {}
    for row in rows:
        if not isinstance(row, dict): raise ValueError('Invalid logical server')
        country, entry, tier, status, identity = (row.get('ExitCountry'), row.get('EntryCountry'),
                                                   row.get('Tier'), row.get('Status'), row.get('ID'))
        if country not in targets or entry != country: continue
        if (not isinstance(identity, str) or not 1 <= len(identity) <= 128
                or type(tier) is not int or tier < 0 or type(status) is not int or status not in (0, 1)):
            raise ValueError('Invalid logical identity')
        prior = logical.get(identity)
        item = (country, tier == 0, status == 1)
        if prior is not None and prior != item: raise ValueError('Conflicting logical identity')
        logical[identity] = item
        physical = row.get('Servers')
        if not isinstance(physical, list) or len(physical) > 512:
            raise ValueError('Invalid endpoint list')
        for server in physical:
            if not isinstance(server, dict): raise ValueError('Invalid endpoint')
            try: ip = ipaddress.ip_address(server.get('EntryIP', ''))
            except ValueError: continue
            if not ip.is_global or ip.is_multicast: continue
            address = str(ip)
            if address in endpoints and endpoints[address] != country:
                raise ValueError('Conflicting endpoint geography')
            endpoints[address] = country
    result = {}
    for country in targets:
        values = [value for value in logical.values() if value[0] == country]
        result[country] = {'logical_servers': len(values), 'free_tier_logical_servers': sum(v[1] for v in values),
                           'advertised_online_logical_servers': sum(v[2] for v in values),
                           'unique_ingress_ips': sum(v == country for v in endpoints.values())}
    return {'provider': 'proton', 'scope': 'one_public_directory_response',
            'logical_servers': len(logical), 'unique_ingress_ips': len(endpoints),
            'countries': result, 'protocols_verified': False, 'udp_capability_tested': False,
            'verified_exits': 0, 'usable_service_pools': 0}


def main():
    from pathlib import Path
    from scripts.egress_catalog import validate_policy
    policy = json.loads(Path('config/egress.json').read_text())
    validate_policy(policy)
    try:
        result = inspect(fetch_directory(), set(policy['target_countries']))
        print('::notice title=Proton directory counts::' + json.dumps(result, sort_keys=True), flush=True)
        return 0
    except Exception as error:
        # Exception text can include source data or endpoints. Do not retry a denial.
        print('::warning title=Proton directory unavailable::' + type(error).__name__, flush=True)
        return 1


if __name__ == '__main__': raise SystemExit(main())
