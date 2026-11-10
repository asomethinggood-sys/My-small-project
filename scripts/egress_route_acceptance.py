"""One finite personal issued-route diagnostic, without phone provisioning.

The only retry is a bounded startup attempt against a fresh candidate for the
same country. Once the authenticated-route callback is entered, no candidate is
substituted, irrespective of whether that callback succeeds or fails.
"""
import argparse
import json
from pathlib import Path

from scripts.egress_catalog import fetch_directory, validate_policy
from scripts.egress_openvpn_probe import probe
from scripts.egress_phone_trial import trial
from scripts.egress_vpngate import candidates


def test_snapshot(country, text, *, run_probe=probe):
    policy = json.loads(Path('config/egress.json').read_text())
    validate_policy(policy)
    if country not in policy['target_countries']:
        raise ValueError('Unsupported target country')
    selected = candidates(text, {country}, limit=2)
    outcome = {'country': country, 'candidates_selected': len(selected),
               'candidates_tested': 0, 'issued_route_passed': False,
               'phone_settings_issued': False, 'usable_service_pools': 0}
    for envelope in selected:
        entered = False
        def acceptance(namespace, upstream, initial):
            nonlocal entered
            entered = True
            return trial(namespace, upstream, initial, acceptance_only=True)
        report = run_probe(envelope, private_trial=acceptance)
        outcome['candidates_tested'] += 1
        route = report.get('issued_route_evidence', {})
        outcome['issued_route_passed'] = (report.get('country_verified') is True
            and report.get('host_main_routes_unchanged') is True
            and report.get('tunnel_drop_blocked') is True
            and route.get('country_verified') is True
            and route.get('udp_dns_passed') is True)
        # This report contains only the probe's allowlisted metadata, never the
        # candidate envelope, downloaded config, credentials or issued lease.
        print('::notice title=Bounded route candidate::' + json.dumps(report), flush=True)
        if entered or report.get('failed_stage') == 'private_phone_trial':
            break
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--country', required=True)
    args = parser.parse_args()
    try:
        outcome = test_snapshot(args.country, fetch_directory())
        print('::notice title=Issued route outcome::' + json.dumps(outcome), flush=True)
        return 0 if outcome['issued_route_passed'] else 1
    except Exception as error:
        # Provider responses and subprocess errors can contain private input.
        print('::error title=Issued route outcome::Diagnostic failed closed; ' + type(error).__name__, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
