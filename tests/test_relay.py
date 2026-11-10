import importlib.util
import json
from pathlib import Path
import re
import unittest
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('update_relay', ROOT / 'scripts/update-relay.py')
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class RelayTests(unittest.TestCase):
    def test_update_payload_has_bounded_lease_and_validated_backend(self):
        data = updater.payload('a-b.trycloudflare.com', now=1000)
        self.assertEqual(data['host'], 'a-b.trycloudflare.com')
        self.assertEqual(data['expiresAt'], (1000 + 21300) * 1000)
        for host in ['localhost', 'https://a.trycloudflare.com', 'a.trycloudflare.com.evil.org',
                     'a.trycloudflare.com:443', 'a.trycloudflare.com/path', 'a@b.trycloudflare.com']:
            with self.assertRaises(ValueError):
                updater.payload(host)

    def test_public_identity_and_worker_path_are_consistent(self):
        profile = json.loads((ROOT / 'worker/profile.json').read_text())
        uuid.UUID(profile['uuid'])
        self.assertRegex(profile['path'], r'^/[0-9a-f]{32}$')
        self.assertEqual(profile['host'], 'bih.asomethinggood.workers.dev')
        worker = (ROOT / 'worker/worker.mjs').read_text()
        self.assertEqual(re.search(r"const WS_PATH = '([^']+)';", worker)[1], profile['path'])
        self.assertNotIn('token', profile)
