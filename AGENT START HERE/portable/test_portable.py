import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

HERE = Path(__file__).resolve().parent

def load(name):
    spec=importlib.util.spec_from_file_location('portable_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

control=load('control');exporter=load('export')

class PortableTests(unittest.TestCase):
    def setUp(self):
        self.state={'schema':1,'enabled':False,'phase':'building','generation':'42-1'}
        self.calls=[]
        self.env=patch.dict(os.environ,{'CONTROL_GENERATION':'42-1','WORKFLOW_REF':'main','GITHUB_REPOSITORY':'destination/example','GITHUB_SHA':'fixture'})
        self.env.start()
    def tearDown(self):self.env.stop()
    def read(self):return dict(self.state)
    def write(self,value):self.state=dict(value)
    def gh(self,*args):self.calls.append(args);return '[]'
    def invoke(self,command,gh=None):
        with patch.object(control,'read',self.read),patch.object(control,'write',self.write),patch.object(control,'gh',gh or self.gh),contextlib.redirect_stdout(io.StringIO()):control.main(command)
    def test_activate_dispatches_ten_exact_workflows(self):
        self.invoke('activate');self.assertTrue(self.state['enabled']);self.assertEqual(len(self.calls),10)
        self.assertEqual([c[2] for c in self.calls],[f'continuum-beta-{i:02d}.yml' for i in range(1,11)])
    def test_stop_during_build_cannot_be_undone(self):
        self.state.update(phase='stopped',generation='stop-43',enabled=False)
        with self.assertRaises(ValueError):self.invoke('activate')
        self.assertFalse(self.state['enabled']);self.assertEqual(self.calls,[])
    def test_partial_activation_fails_closed(self):
        def fail(*args):
            self.calls.append(args)
            if len(self.calls)==3:raise subprocess.CalledProcessError(1,'gh')
            return ''
        with self.assertRaises(subprocess.CalledProcessError):self.invoke('activate',fail)
        self.assertFalse(self.state['enabled']);self.assertEqual(self.state['phase'],'activation-failed')
    def test_stop_disables_before_any_cancellation(self):
        def check(*args):self.assertFalse(self.state['enabled']);return '[]'
        self.state['enabled']=True;self.invoke('stop',check);self.assertEqual(self.state['phase'],'stopped')
    def test_private_destination_rejected(self):
        with patch.object(control,'gh',return_value=json.dumps({'private':True,'default_branch':'main'})):
            with self.assertRaises(ValueError):control.preflight()
    def test_nondefault_destination_rejected(self):
        with patch.object(control,'gh',return_value=json.dumps({'private':False,'default_branch':'other'})):
            with self.assertRaises(ValueError):control.preflight()
    def test_export_is_complete_manual_and_destination_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'ready';count=exporter.export(root);self.assertGreater(count,100)
            workflows=list((root/'.github/workflows').glob('*.yml'));self.assertEqual(len(workflows),14)
            for file in workflows:
                doc=yaml.load(file.read_text(),Loader=yaml.BaseLoader)
                events=doc['on'];events={events} if isinstance(events,str) else set(events)
                self.assertLessEqual(events,{'workflow_dispatch','workflow_call'})
            self.assertFalse((root/'.git').exists());self.assertFalse((root/'.github/workflows/vpn.yml').exists())
            app=(root/'android/app/src/main/java/app/continuum/BetaCatalog.java').read_text()
            self.assertIn('BuildConfig.BETA_REPOSITORY',app);self.assertNotIn('asomethinggood-sys',app)
            self.assertIn("environmentVariable('GITHUB_REPOSITORY')",(root/'android/app/build.gradle').read_text())
            start=yaml.load((root/'.github/workflows/start-beta.yml').read_text(),Loader=yaml.BaseLoader)
            self.assertEqual(start['jobs']['activate']['needs'],'build-app')
            self.assertEqual(start['jobs']['prepare']['concurrency']['group'],start['jobs']['activate']['concurrency']['group'])
            self.assertIn('from portable.control import enabled',(root/'server/run_slot.py').read_text())
            self.assertNotIn('AGENT START HERE',(root/'.github/workflows/continuum-beta-build.yml').read_text())
            for name,digest in json.loads((root/'PORTABLE-MANIFEST.json').read_text())['files'].items():
                self.assertEqual(exporter.hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)
    def test_export_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):exporter.export(Path(directory))

if __name__=='__main__':unittest.main()
