"""Bounded official-directory acquisition; advertisements never imply availability."""
import base64
import csv
import io

from scripts.egress_openvpn_probe import prepare


def candidates(text, targets, limit=3):
    if type(limit) is not int or not 1 <= limit <= 3:
        raise ValueError('Bounded candidate limit required')
    # Validate the entire snapshot before applying the per-country candidate
    # limit. Truncation and conflicting directory claims must fail closed.
    from scripts.egress_catalog import parse_vpngate
    parse_vpngate(text, targets)
    lines = text.splitlines()
    rows = csv.DictReader(io.StringIO('\n'.join([lines[1][1:]] + lines[2:])))
    seen = set()
    accepted = []
    for index, row in enumerate(rows):
        if index >= 10000 or len(accepted) >= limit:
            break
        if row.get('CountryShort') not in targets:
            continue
        envelope = {'provider': 'vpngate', 'country': row['CountryShort'],
                    'endpoint_ip': row.get('IP', ''),
                    'profile_base64': row.get('OpenVPN_ConfigData_Base64', ''),
                    # Inspect exactly the policy that will be used for the test.
                    'cipher_policy': 'cbc_sha256'}
        try:
            parsed = prepare(envelope)
        except (ValueError, UnicodeError):
            continue
        identity = (parsed['endpoint_ip'], parsed['endpoint_port'], parsed['transport'])
        if identity in seen:
            continue
        seen.add(identity)
        accepted.append(envelope)
    return accepted


def trial_country(message, targets):
    """Extract exactly one explicit target from a deliberate trial marker."""
    import re
    if not isinstance(message, str):
        raise ValueError('Explicit country trial marker required')
    matches = re.findall(r'\[private-country-trial:([A-Z]{2})\]', message)
    if message.count('[private-country-trial:') != 1 or len(matches) != 1 or matches[0] not in targets:
        raise ValueError('One supported country trial marker required')
    return matches[0]


def acquire(country, endpoint, path):
    """Acquire one explicitly selected official endpoint; no candidate rotation."""
    from scripts.egress_catalog import fetch_directory
    from pathlib import Path
    import json
    import ipaddress
    endpoint = str(ipaddress.IPv4Address(endpoint))
    text = fetch_directory()
    # Filter directory rows before applying the bounded parser. Do not create
    # a fabricated profile or substitute an endpoint absent from the directory.
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != '*vpn_servers':
        raise ValueError('Invalid official directory')
    rows = csv.DictReader(io.StringIO('\n'.join([lines[1].lstrip('#')] + lines[2:])))
    stream = io.StringIO()
    stream.write('*vpn_servers\n#')
    writer = csv.DictWriter(stream, fieldnames=rows.fieldnames)
    writer.writeheader()
    for index, row in enumerate(rows):
        if index >= 10000:break
        if row.get('IP') == endpoint and row.get('CountryShort') == country:
            writer.writerow(row)
    selected = candidates(stream.getvalue(), {country}, limit=1)
    if not selected:
        raise ValueError('Selected official candidate unavailable')
    destination = Path(path)
    with open(destination, 'x', opener=lambda name, flags: __import__('os').open(name, flags, 0o600)) as output:
        json.dump(selected[0] | {'cipher_policy': 'cbc_sha256'}, output)


def acquire_current(country, path):
    """One bounded startup batch from one current official directory snapshot."""
    import json
    import os
    from scripts.egress_catalog import fetch_directory
    selected = candidates(fetch_directory(), {country}, limit=3)
    if not selected:
        raise ValueError('Selected official candidate unavailable')
    with open(path, 'x', opener=lambda name, flags: os.open(name, flags, 0o600)) as output:
        json.dump({'candidates': [item | {'cipher_policy': 'cbc_sha256'} for item in selected]}, output)


def main():
    import argparse
    import json
    from pathlib import Path
    from scripts.egress_catalog import fetch_directory, validate_policy
    from scripts.egress_openvpn_probe import probe
    policy = json.loads(Path('config/egress.json').read_text())
    validate_policy(policy)
    parser = argparse.ArgumentParser(description='Bounded isolated VPNGate namespace probe; not a phone service')
    parser.add_argument('--country', required=True, choices=policy['target_countries'])
    parser.add_argument('--limit', type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    selected = candidates(fetch_directory(), {args.country}, limit=args.limit)
    print('::notice title=Bounded VPNGate inspection::' + json.dumps({
        'country': args.country, 'candidates': len(selected), 'phone_service': False,
        'scope': 'one_snapshot_not_provider_inventory'}), flush=True)
    verified = 0
    for envelope in selected:
        report = probe(envelope)
        verified += report.get('country_verified') is True
        # No profiles, keys, credentials or untrusted provider messages logged.
        print('::notice title=VPNGate isolated live probe::' + json.dumps(report), flush=True)
    print('::notice title=Bounded VPNGate outcome::' + json.dumps({
        'country': args.country, 'candidates_tested': len(selected),
        'namespace_verified': verified, 'issued_routes_tested': 0,
        'usable_service_pools': 0}), flush=True)


if __name__ == '__main__':
    main()
