"""Refresh sanitized discovery metadata on a bounded cadence, not VPN routes.

Run on infrastructure you control; a supervisor may restart the finite process.
The output expires even if this process or a provider stops responding.
"""
import argparse
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time


def loop(refresh, stop, interval, duration, *, clock=time.monotonic):
    if type(interval) is not int or not 60 <= interval <= 3600:
        raise ValueError('Refresh interval must be 60–3600 seconds')
    if type(duration) is not int or not 1 <= duration <= 21600:
        raise ValueError('Process duration must be 1–21600 seconds')
    end = clock() + duration
    failures = 0
    while not stop.is_set() and clock() < end:
        started = clock()
        try:
            ok = refresh()
        except Exception:
            ok = False  # Exceptions can include private provider response data.
        if not ok:
            failures += 1
        print('catalog refresh: ' + ('complete' if ok else 'partial_or_failed'), flush=True)
        # No catch-up burst if a provider was slow. Never overlap requests.
        delay = min(max(0, started + interval - clock()), max(0, end - clock()))
        if delay <= 0 and clock() < end:
            delay = min(interval, end - clock())
        if delay > 0:
            stop.wait(delay)
    return 1 if failures else 0


def refresh_once(output):
    try:
        result = subprocess.run([sys.executable, '-m', 'scripts.egress_catalog', '--live',
                                 '--vpnjantit-live', '--output', str(output)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                timeout=60, check=False)
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='.runtime/egress/catalog.json')
    parser.add_argument('--interval', type=int, default=300)
    parser.add_argument('--duration', type=int, default=21600)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    if not 60 <= args.interval <= 3600 or not 1 <= args.duration <= 21600:
        parser.error('interval must be 60–3600 and duration 1–21600 seconds')
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Lock the output across separate invocations on the same filesystem.
    fd = os.open(str(path) + '.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('catalog refresh: already_running', flush=True)
            return 1
        if args.once:
            ok = refresh_once(path)
            print('catalog refresh: ' + ('complete' if ok else 'partial_or_failed'), flush=True)
            return 0 if ok else 1
        stop = threading.Event()
        def shutdown(*_): stop.set()
        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)
        return loop(lambda: refresh_once(path), stop, args.interval, args.duration)


if __name__ == '__main__': raise SystemExit(main())
