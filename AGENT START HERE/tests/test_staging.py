"""Offline-only tests. Never connect, publish, dispatch, or start a subprocess."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import urllib.parse
import yaml

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location('beta_worker', HERE / 'server/run_slot.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
spec2 = importlib.util.spec_from_file_location('overlay', HERE / 'apply_overlay.py')
overlay = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(overlay)


class StagingTests(unittest.TestCase):
    def test_ten_distinct_manual_slots(self):
        slots = set()
        for index in range(1, 11):
            file = HERE / f'workflows/continuum-beta-{index:02d}.yml'
            doc = yaml.load(file.read_text(), Loader=yaml.BaseLoader)
            self.assertEqual(doc['on'], 'workflow_dispatch')
            self.assertEqual(doc['jobs']['slot']['uses'], './.github/workflows/continuum-beta-slot.yml')
            self.assertEqual(int(doc['jobs']['slot']['with']['slot']), index)
            slots.add(index)
            self.assertFalse((ROOT / '.github/workflows' / file.name).exists())
        self.assertEqual(len(slots), 10)

    def test_build_cannot_dispatch_servers(self):
        doc = yaml.load((HERE / 'workflows/continuum-beta-build.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertEqual(doc['on'], 'workflow_dispatch')
        self.assertEqual(doc['permissions'], {'contents': 'read'})
        text = (HERE / 'workflows/continuum-beta-build.yml').read_text()
        self.assertNotIn('gh workflow run', text)
        self.assertNotIn('gh release create', text)

    def test_worker_has_timeout_serialization_and_off_switch(self):
        doc = yaml.load((HERE / 'workflows/continuum-beta-slot.yml').read_text(), Loader=yaml.BaseLoader)
        job = doc['jobs']['serve']
        self.assertLess(int(job['timeout-minutes']), 360)
        self.assertIn('ENABLE_CONTINUUM_BETA', job['if'])
        self.assertIn('inputs.slot', job['concurrency']['group'])
        self.assertEqual(job['concurrency']['cancel-in-progress'], 'false')
        self.assertEqual(set(doc['on']), {'workflow_call'})
        self.assertIn('gh workflow run', job['steps'][1]['run'])
        self.assertEqual(job['steps'][-1]['if'], 'failure()')
        self.assertEqual(job['steps'][-1]['run'], 'sleep 300')
        self.assertEqual(sum(step.get('run', '').count('gh workflow run') for step in job['steps']), 1)

    def test_document_contract(self):
        d = worker.document(1, '12345-1', 'owned-fixture.trycloudflare.com', 'f2222222-2222-4222-8222-222222222222', '/fixture', 1000, 2000)
        self.assertEqual(d['slot'], 1)
        self.assertEqual(d['expires_at'], 2000)
        uri = urllib.parse.urlsplit(d['uri'])
        q = urllib.parse.parse_qs(uri.query)
        self.assertEqual(uri.port, 443)
        self.assertEqual(q['security'], ['tls'])
        self.assertEqual(q['type'], ['ws'])
        self.assertEqual(q['path'], ['/fixture'])

    def test_reject_bad_publications(self):
        base = [1, '12345-1', 'owned-fixture.trycloudflare.com', 'f2222222-2222-4222-8222-222222222222', '/fixture', 1000, 2000]
        for index, value in [(0,0),(0,11),(2,'private.example'),(3,'bad-uuid'),(4,'/../x'),(6,999),(6,30000)]:
            args = base.copy(); args[index] = value
            with self.assertRaises(ValueError):
                worker.document(*args)

    def test_no_experiment_deadline(self):
        for now in [1000, 86400 * 7, 86400 * 365, 86400 * 365 * 20]:
            for slot in range(1, 11):
                self.assertEqual(worker.rotation_end(slot, now) - now, (240 + slot * 6) * 60)
        text = (HERE / 'server/run_slot.py').read_text()
        self.assertNotIn('BETA_EXPIRES_AT', text)
        self.assertNotIn('remote_expiry', text)
        self.assertIn('if not enabled():', text)
        for slot in [0, 11]:
            with self.assertRaises(ValueError):worker.rotation_end(slot, 1000)

    def test_overlay_matches_unmodified_base(self):
        files = overlay.plan()
        self.assertGreaterEqual(len(files),10)
        for _, target in files:
            self.assertTrue(target.is_relative_to(ROOT / 'android'))

    def test_no_fake_published_slots(self):
        self.assertEqual(list(HERE.rglob('slot.json')), [])
        self.assertEqual(list(HERE.rglob('*.apk')), [])

    def test_labels_and_latency_never_use_uri(self):
        source = (HERE / 'overlay/android/app/src/main/java/app/continuum/BetaServerDialog.java').read_text()
        self.assertIn('BetaCatalog.label(slot)', source)
        self.assertIn('Not checked', source)
        self.assertIn('Not responding', source)
        self.assertNotIn('.setText(entry.uri)', source)
        self.assertNotIn('.setText(result.entry.uri)', source)


if __name__ == '__main__':
    unittest.main()
