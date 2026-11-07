#!/usr/bin/env python3
"""Run on the Tehran client. Curl timings are HTTP timings, NOT ICMP/proxy RTT."""
import argparse
import csv
from datetime import datetime, timezone
import math
import statistics
import subprocess
import time


def summarize(values):
    values = sorted(values)
    return {'median_ms': round(statistics.median(values) * 1000, 1),
            'p95_ms': round(values[math.ceil(len(values) * .95) - 1] * 1000, 1)} if values else {}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label', required=True, help='e.g. Tehran-ISP-US-tunnel-evening')
    p.add_argument('--url', required=True, help='Same small HTTPS URL for every candidate')
    p.add_argument('--proxy', help='socks5h://127.0.0.1:10808; omit for direct or Android VPN-mode test')
    p.add_argument('--count', type=int, default=30)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.count < 1 or not args.url.startswith('https://'):
        p.error('positive count and HTTPS URL required')
    totals = []
    with open(args.output, 'x', newline='') as f:
        w = csv.writer(f)
        w.writerow(['utc', 'label', 'url', 'proxy', 'exit', 'http', 'dns_s', 'connect_s',
                    'tls_s', 'ttfb_s', 'total_s', 'bytes', 'bytes_per_s', 'error'])
        for _ in range(args.count):
            cmd = ['curl', '--silent', '--show-error', '--output', '/dev/null',
                   '--connect-timeout', '10', '--max-time', '20', '--write-out',
                   '%{http_code},%{time_namelookup},%{time_connect},%{time_appconnect},%{time_starttransfer},%{time_total},%{size_download},%{speed_download}']
            cmd += ['--proxy', args.proxy, '--noproxy', ''] if args.proxy else ['--noproxy', '*']
            result = subprocess.run(cmd + [args.url], capture_output=True, text=True)
            fields = result.stdout.split(',')
            w.writerow([datetime.now(timezone.utc).isoformat(), args.label, args.url,
                        args.proxy or 'OS route (record VPN state)', result.returncode, *fields, result.stderr.strip()])
            f.flush()
            if result.returncode == 0 and len(fields) == 8 and 200 <= int(fields[0]) < 300:
                totals.append(float(fields[5]))
            time.sleep(1)
    print({'samples': args.count, 'successes': len(totals), 'failures': args.count - len(totals),
           'cold_HTTP_total': summarize(totals)})
    print('Location is user-supplied, not verified. With SOCKS, connect_s is to the LOCAL proxy.')


if __name__ == '__main__':
    main()
