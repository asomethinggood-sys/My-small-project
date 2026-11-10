import fcntl
import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import egress_catalog, egress_refresh


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now


class Stop:
    def __init__(self, clock): self.clock = clock; self.stopped = False
    def is_set(self): return self.stopped
    def wait(self, seconds): self.clock.now += seconds


class RefreshTests(unittest.TestCase):
    def test_cadence_and_finite_duration_no_catchup_burst(self):
        clock = Clock(); stop = Stop(clock); started = []
        def refresh():
            started.append(clock.now)
            if len(started) == 1: clock.now += 80
            return True
        with redirect_stdout(io.StringIO()):
            self.assertEqual(egress_refresh.loop(refresh, stop, 60, 250, clock=clock), 0)
        self.assertEqual(started, [0, 140, 200])
        self.assertEqual(clock.now, 250)

    def test_failure_and_termination_are_reported_without_exception_text(self):
        clock = Clock(); stop = Stop(clock)
        def refresh():
            stop.stopped = True
            raise ValueError('secret')
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(egress_refresh.loop(refresh, stop, 300, 21600, clock=clock), 1)
        self.assertNotIn('secret', output.getvalue())
        self.assertIn('partial_or_failed', output.getvalue())

    def test_bounds_and_one_shot_timeout(self):
        for interval, duration in [(59, 60), (300, 21601), (3601, 5), (60, 0)]:
            with self.assertRaises(ValueError): egress_refresh.loop(lambda: True, Stop(Clock()), interval, duration)
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('secret', 60)):
            self.assertFalse(egress_refresh.refresh_once(Path('out')))

    def test_existing_writer_is_not_disrupted(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'catalog.json'
            with open(str(output) + '.lock', 'w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                process = subprocess.run([sys.executable, '-m', 'scripts.egress_refresh', '--once', '--output', str(output)],
                                         capture_output=True, text=True, timeout=5)
            self.assertEqual(process.returncode, 1)
            self.assertIn('already_running', process.stdout)
            self.assertFalse(output.exists())

    def test_provider_fetches_really_overlap_and_are_isolated(self):
        barrier = threading.Barrier(2)
        def gate():
            barrier.wait(timeout=2)
            return '*vpn_servers\n#HostName,IP,CountryShort,OpenVPN_ConfigData_Base64\na,8.8.8.8,DE,x\n'
        def jantit():
            barrier.wait(timeout=2)
            raise OSError('private response')
        with patch('scripts.egress_catalog.fetch_directory', gate), patch('scripts.egress_vpnjantit.fetch_directory', jantit):
            rows, sources, failed = egress_catalog.collect_sources({'DE'}, live=True, vpnjantit_live=True)
        self.assertTrue(failed)
        self.assertEqual(len(rows), 1)
        self.assertEqual(sources[0]['status'], 'fetched')
        self.assertEqual(sources[1]['status'], 'fetch_or_parse_failed')
        self.assertNotIn('private response', json.dumps(sources))


if __name__ == '__main__': unittest.main()
