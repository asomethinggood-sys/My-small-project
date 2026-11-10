import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class MeasureTests(unittest.TestCase):
    def test_mock_success_and_failure_are_preserved(self):
        script = Path(__file__).resolve().parents[1] / 'scripts/measure.py'
        for status, code in [('204', 0), ('000', 28)]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                d = Path(tmp)
                mock = d / 'curl'
                mock.write_text(f'#!/bin/sh\nprintf "{status},0.001,0.002,0.003,0.004,0.150,0,0"\nexit {code}\n')
                mock.chmod(0o700)
                output = d / 'results.csv'
                run = subprocess.run([sys.executable, str(script), '--label', 'MOCK-not-Tehran',
                    '--url', 'https://example.com/', '--count', '1', '--output', str(output)],
                    env={**os.environ, 'PATH': tmp + ':' + os.environ['PATH']},
                    capture_output=True, text=True, check=True)
                with output.open() as f:
                    row = list(csv.DictReader(f))[0]
                self.assertEqual(row['exit'], str(code))
                self.assertEqual(row['http'], status)
                self.assertIn("'failures': " + str(int(code != 0)), run.stdout)
                self.assertIn('150.0' if code == 0 else "'cold_HTTP_total': {}", run.stdout)
