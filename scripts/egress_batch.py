#!/usr/bin/env python3
"""Bounded sequential comparison on one runner, retaining every failed sample.

A stability result is research evidence only. It neither grants sharing permission
nor publishes a profile, starts a permanent service, or makes catalog rows usable.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from scripts.egress_catalog import atomic_write


REQUIRED_FLAGS = ('country_verified', 'independent_ip_agreement', 'udp_dns_passed',
                  'https_and_dns_passed', 'tunnel_drop_blocked', 'host_main_routes_unchanged')


def validate_plan(plan):
    if plan.get('schema_version') != 1 or plan.get('purpose') != 'bounded_private_provider_comparison':
        raise ValueError('Unsupported experiment purpose')
    if type(plan.get('rounds')) is not int or not 1 <= plan['rounds'] <= 2:
        raise ValueError('At most two rounds permitted')
    if plan.get('minimum_consecutive_successes') != 2:
        raise ValueError('Two consecutive successes required')
    if type(plan.get('sample_timeout_seconds')) is not int or not 60 <= plan['sample_timeout_seconds'] <= 210:
        raise ValueError('Invalid sample deadline')
    candidates = plan.get('candidates', [])
    if not 1 <= len(candidates) <= 3 or len({candidate['id'] for candidate in candidates}) != len(candidates):
        raise ValueError('One to three distinct candidates required')
    for candidate in candidates:
        if (candidate.get('provider') != 'vpnbook' or candidate.get('country') != 'DE'
                or candidate.get('server') not in ('de20', 'de220')
                or type(candidate.get('port')) is not int or candidate['port'] not in (53, 25000)
                or candidate['id'] != f"vpnbook-{candidate['server']}-udp{candidate['port']}"):
            raise ValueError('Candidate outside approved experiment scope')


def successful(sample, candidate, now):
    report = sample.get('report', {})
    probe = report.get('live_probe', {})
    stamp = sample.get('finished_at')
    countries = probe.get('observed_countries', [])
    return (sample.get('execution') == 'completed'
            and type(stamp) is int and now - 900 <= stamp <= now + 30
            and report.get('status') == 'download_received_unverified'
            and report.get('candidate_id') == candidate['id']
            and report.get('server') == candidate['server']
            and report.get('port') == candidate['port']
            and probe.get('candidate_id') == candidate['id']
            and probe.get('endpoint_port') == candidate['port']
            and probe.get('status') == 'german_exit_observed'
            and isinstance(countries, list) and len(countries) >= 2
            and all(code == candidate['country'] for code in countries)
            and all(probe.get(flag) is True for flag in REQUIRED_FLAGS))


def summarize(plan, samples, now=None):
    validate_plan(plan)
    now = int(time.time()) if now is None else now
    rows = []
    for candidate in plan['candidates']:
        relevant = [sample for sample in samples if sample.get('candidate_id') == candidate['id']]
        # A duplicate or missing round is not extra evidence. Preserve all rows,
        # but invalidate the gate rather than cherry-picking successful ones.
        rounds = [sample.get('round') for sample in relevant]
        expected = list(range(1, plan['rounds'] + 1))
        complete = sorted(rounds) == expected and len(rounds) == len(set(rounds))
        ordered = sorted(relevant, key=lambda sample: sample.get('round', 0))
        successes = [successful(sample, candidate, now) for sample in ordered]
        streak = 0
        for passed in successes:
            streak = streak + 1 if passed else 0
        stable = complete and streak >= plan['minimum_consecutive_successes']
        failures = [sample.get('report', {}).get('live_probe', {}).get('status', sample.get('execution', 'unknown'))
                    for sample, passed in zip(ordered, successes) if not passed]
        rows.append({'candidate_id': candidate['id'], 'country': candidate['country'],
                     'provider': candidate['provider'], 'server': candidate['server'], 'port': candidate['port'],
                     'samples': len(relevant), 'successful_samples': sum(successes), 'failure_statuses': failures,
                     'consecutive_successes': streak, 'stable_in_bounded_test': stable,
                     'selectable': False, 'shared_use_approved': False})
    return {'schema_version': 1, 'generated_at': now, 'expires_at': now + 900,
            'kind': 'bounded_research_not_active_exit_catalog', 'candidates': rows,
            'publication_permitted': False, 'samples': samples}


def execute(plan, output, browser_command=None):
    validate_plan(plan)
    command = browser_command or ['node', 'scripts/egress_vpnbook_browser.mjs']
    samples = []
    deadline = time.monotonic() + 900
    report_path = Path('.runtime/egress/vpnbook-browser.json')
    stop = False
    for round_number in range(1, plan['rounds'] + 1):
        for candidate in plan['candidates']:
            if stop or time.monotonic() >= deadline:
                stop = True
                sample = {'candidate_id': candidate['id'], 'round': round_number,
                          'execution': 'not_run_budget_exhausted', 'finished_at': int(time.time())}
            else:
                report_path.unlink(missing_ok=True)
                env = {key: value for key, value in os.environ.items()
                       if key in ('PATH', 'HOME', 'LANG', 'LC_ALL', 'PLAYWRIGHT_BROWSERS_PATH')}
                env.update(NYX_PROVIDER_PROBE='true', NYX_VPNBOOK_SERVER=candidate['server'],
                           NYX_VPNBOOK_PORT=str(candidate['port']))
                sample = {'candidate_id': candidate['id'], 'round': round_number}
                started = time.monotonic()
                try:
                    # Output is already allowlisted by the browser probe; no keys/configs.
                    completed = subprocess.run(command, env=env, timeout=min(plan['sample_timeout_seconds'],
                                                max(1, deadline - time.monotonic())), check=False)
                    sample['execution'] = 'completed' if completed.returncode == 0 else 'process_failed'
                    if completed.returncode == 0 and report_path.exists() and report_path.stat().st_size <= 128 * 1024:
                        sample['report'] = json.loads(report_path.read_text())
                    elif completed.returncode == 0:
                        sample['execution'] = 'report_missing_or_oversized'
                except subprocess.TimeoutExpired:
                    sample['execution'] = 'sample_timeout'
                    # Do not start another provider connection after uncertain cleanup.
                    stop = True
                except (OSError, ValueError):
                    sample['execution'] = 'execution_or_report_failed'
                sample['elapsed_ms'] = round((time.monotonic() - started) * 1000)
                sample['finished_at'] = int(time.time())
            samples.append(sample)
            atomic_write(output, summarize(plan, samples))
    result = summarize(plan, samples)
    atomic_write(output, result)
    for row in result['candidates']:
        print('::notice title=Nyx candidate stability::' + row['candidate_id'] +
              f"; samples={row['samples']}; successes={row['successful_samples']}; " +
              f"consecutive={row['consecutive_successes']}; stable={row['stable_in_bounded_test']}; selectable=false",
              flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default='config/egress-experiment.json')
    parser.add_argument('--output', default='.runtime/egress/comparison.json')
    args = parser.parse_args()
    execute(json.loads(Path(args.plan).read_text()), args.output)


if __name__ == '__main__':
    main()
