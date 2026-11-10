"""Bounded official-directory acquisition; advertisements never imply availability."""
import base64
import csv
import io

from scripts.egress_openvpn_probe import prepare


def candidates(text, targets, limit=3):
    if type(limit) is not int or not 1 <= limit <= 3:
        raise ValueError('Bounded candidate limit required')
    lines = text.splitlines()
    if len(lines) < 2 or lines[0].strip() != '*vpn_servers' or not lines[1].startswith('#HostName,'):
        raise ValueError('Invalid official directory')
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
                    'profile_base64': row.get('OpenVPN_ConfigData_Base64', '')}
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


def main():
    import json
    from scripts.egress_catalog import fetch_directory
    from scripts.egress_openvpn_probe import probe
    targets = set(json.load(open('config/egress.json'))['target_countries'])
    selected = candidates(fetch_directory(), targets)
    print('::notice title=Bounded VPNGate inspection::' + json.dumps({'candidates': len(selected), 'phone_service': False}), flush=True)
    for envelope in selected:
        # Explicit compatibility experiment, not an automatic failure fallback.
        envelope = envelope | {'cipher_policy': 'cbc_sha256'}
        report = probe(envelope)
        # No profiles, keys, credentials or untrusted provider messages logged.
        print('::notice title=VPNGate isolated live probe::' + json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
