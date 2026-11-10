#!/usr/bin/env python3
"""Bounded, sanitized inspection of one official VPNGate directory snapshot.

Counts are observations of a changing directory, never availability. No profiles,
addresses, credentials or endpoint identifiers are written. No tunnel is started.
"""
import argparse
import csv
import io
import ipaddress
import json
from pathlib import Path

from scripts.egress_catalog import fetch_directory, parse_vpngate, validate_policy
from scripts.egress_openvpn_probe import prepare


def inspect(text, targets, per_country=3, total=60):
    if type(per_country) is not int or not 1 <= per_country <= 5:
        raise ValueError('Per-country inspection budget must be between 1 and 5')
    if type(total) is not int or not 1 <= total <= 100:
        raise ValueError('Total inspection budget must be between 1 and 100')
    # The full snapshot is parsed first, so exceeding the row/byte budget or a
    # conflicting selected-country label is an error, not a truncated count.
    observations = parse_vpngate(text, set(targets))
    result = {country: {'advertised_unique_ingress_ips': 0, 'inspected_unique_ingress_ips': 0,
                        'accepted_profiles': {'tcp': 0, 'udp': 0}, 'rejected_profiles': 0}
              for country in targets}
    for item in observations:
        result[item['country']]['advertised_unique_ingress_ips'] += 1
    lines = text.splitlines()
    reader = csv.DictReader(io.StringIO('\n'.join([lines[1][1:]] + lines[2:])))
    seen = set()
    inspected = 0
    for row in reader:
        country = row.get('CountryShort', '')
        if country not in result or not row.get('OpenVPN_ConfigData_Base64'):
            continue
        try:
            address = ipaddress.ip_address(row.get('IP', ''))
        except ValueError:
            continue
        if not address.is_global or address.is_multicast:
            continue
        identity = str(address)
        if identity in seen:
            continue
        seen.add(identity)
        counts = result[country]
        if inspected >= total or counts['inspected_unique_ingress_ips'] >= per_country:
            continue
        inspected += 1
        counts['inspected_unique_ingress_ips'] += 1
        try:
            parsed = prepare({'provider': 'vpngate', 'country': country,
                              'endpoint_ip': identity,
                              'profile_base64': row['OpenVPN_ConfigData_Base64'],
                              'cipher_policy': 'cbc_sha256'})
            counts['accepted_profiles'][parsed['transport']] += 1
        except (ValueError, UnicodeError):
            counts['rejected_profiles'] += 1
    return {'scope': 'one_snapshot_not_provider_inventory',
            'provider': 'vpngate', 'protocol': 'openvpn',
            'inspection_policy': 'explicit_aes_128_cbc_hmac_sha256',
            'per_country_limit': per_country, 'total_limit': total,
            'inspected_total': inspected, 'connection_tested': False,
            'udp_capability_tested': False, 'verified_exits': 0,
            'countries': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--live', action='store_true')
    source.add_argument('--fixture', type=Path)
    parser.add_argument('--policy', type=Path, default=Path('config/egress.json'))
    args = parser.parse_args()
    policy = json.loads(args.policy.read_text())
    validate_policy(policy)
    text = fetch_directory() if args.live else args.fixture.read_text(encoding='utf-8-sig')
    print(json.dumps(inspect(text, policy['target_countries']), indent=2))


if __name__ == '__main__':
    main()
