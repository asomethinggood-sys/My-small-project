#!/usr/bin/env python3
"""Expose allowlisted nonsecret research results in logs/Actions annotations."""
import json
import os
from pathlib import Path
import re


def main():
    lines = ['# Nyx live source observations', '',
             'Metadata only. No provider tunnel or country is verified.', '']
    directory = Path('.runtime/egress')
    source_path = directory / 'sources.json'
    if source_path.exists():
        for item in json.loads(source_path.read_text()).get('sources', []):
            source, status = item.get('source', ''), item.get('status', '')
            if re.fullmatch('[a-z0-9-]+', source) and re.fullmatch('[a-z_]+', status):
                text = f'{source}: {status}; HTTP {int(item.get("http_status", 0))}'
                countries = [c for c in item.get('advertised_countries', []) if re.fullmatch('[A-Z]{2}', c)]
                if countries:
                    text += '; advertised countries ' + ','.join(countries)
                print('::notice title=Nyx source::' + text)
                lines.append('- ' + text)
    path = directory / 'catalog.json'
    if path.exists():
        catalog = json.loads(path.read_text())
        lines += ['', '| Country | Discovered servers | Providers | Verified exits |',
                  '|---|---:|---:|---:|']
        for country in catalog['countries']:
            code = country['country']
            if not re.fullmatch('[A-Z]{2}', code):
                raise ValueError('Invalid country in report')
            count = int(country['discovered_servers'])
            providers = int(country['discovered_providers'])
            lines.append(f'| {code} | {count} | {providers} | 0 |')
            if count:
                print(f'::notice title=Nyx discovery::{code}: {count} discovered servers, {providers} providers, 0 verified exits')
    else:
        lines.append('Directory catalog missing; no discovery result available.')
    text = '\n'.join(lines) + '\n'
    print(text)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(text)


if __name__ == '__main__':
    main()
