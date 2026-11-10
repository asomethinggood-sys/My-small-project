import copy
import threading
import unittest
from unittest.mock import patch, MagicMock
import urllib.error
from scripts.egress_path_probe import client_config, request, await_service, conflict_lookup, measure_geography
from scripts.egress_openvpn_probe import assess_responses


class IssuedPathTests(unittest.TestCase):
    def lease(self):
        return {'country':'DE','token':'A'*43,'generation':1,'expires_in':90,
                'profile':'vless://12345678-1234-1234-1234-123456789abc@trial.example:443?security=tls&type=ws&sni=trial.example&host=trial.example&path=%2Fs%2F'+'A'*43+'%2F1'}

    def test_parallel_geography_keeps_independent_sources_and_proxied_path(self):
        barrier = threading.Barrier(4)
        calls = []
        def fake_run(command, **kwargs):
            calls.append(command)
            barrier.wait(timeout=2)
            return MagicMock(returncode=0, stdout=b'{"ip":"8.8.4.4","country":"DE"}')
        with patch('scripts.egress_path_probe.subprocess.run', side_effect=fake_run):
            rows, timings = measure_geography(18089, threading.Event())
        self.assertEqual(set(rows), {0, 1, 2, 3})
        self.assertEqual(set(timings), {'0', '1', '2', '3'})
        self.assertTrue(all('socks5h://127.0.0.1:18089' in command for command in calls))
        self.assertEqual(len({command[-1] for command in calls}), 4)

    def test_cancelled_geography_does_not_issue_requests(self):
        event=threading.Event();event.set()
        with patch('scripts.egress_path_probe.subprocess.run') as run:
            with self.assertRaises(ValueError):measure_geography(18089,event)
        run.assert_not_called()

    def test_profile_uses_exact_tls_lease_route_and_no_direct_outbound(self):
        config=client_config('https://trial.example',self.lease(),'DE',18089)
        self.assertEqual(len(config['outbounds']),1)
        outbound=config['outbounds'][0]
        self.assertEqual(outbound['protocol'],'vless')
        self.assertFalse(outbound['streamSettings']['tlsSettings']['allowInsecure'])
        self.assertEqual(config['inbounds'][0]['listen'],'127.0.0.1')
        self.assertEqual(outbound['streamSettings']['wsSettings']['path'],'/s/'+'A'*43+'/1')

    def test_misbound_country_generation_host_security_and_expiry_rejected(self):
        original=self.lease()
        for field,value in [('country','FR'),('generation',2),('expires_in',0),('expires_in',301),('token','B'*43),
                            ('profile',original['profile'].replace('trial.example','other.example')),
                            ('profile',original['profile'].replace('security=tls','security=none'))]:
            with self.subTest(field=field,value=value):
                lease=copy.deepcopy(original);lease[field]=value
                with self.assertRaises(ValueError):client_config('https://trial.example',lease,'DE',18089)

    def test_credentials_never_sent_to_non_https_or_nonroot_origin(self):
        with patch('urllib.request.build_opener') as opener:
            for origin in ['http://trial.example','https://user@trial.example','https://trial.example:8443','https://trial.example/path']:
                with self.assertRaises(ValueError):request(origin,'user','private','/v1/sessions',{})
            opener.assert_not_called()

    def test_readiness_never_retries_auth_failure_or_creates_lease(self):
        cancel=MagicMock();cancel.is_set.return_value=False
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect=urllib.error.HTTPError('https://trial.example',401,'denied',{},None)
            with self.assertRaises(urllib.error.HTTPError):await_service('https://trial.example','user','private','DE',cancel)
            self.assertEqual(opener.return_value.open.call_count,1)
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.get_method(),'GET')
            self.assertIsNone(req.data)

    def test_readiness_rejects_unavailable_country_without_retry(self):
        cancel=MagicMock();cancel.is_set.return_value=False
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'{"countries":[{"country":"FR"}]}'
            with self.assertRaises(ValueError):await_service('https://trial.example','user','private','DE',cancel)
            self.assertEqual(opener.return_value.open.call_count,1)

    def test_any_french_observation_rejects_german_selection(self):
        observations={0:{'ip':'8.8.4.4'},1:{'ip':'8.8.4.4','country_iso':'DE'},
                      2:{'ip':'8.8.4.4','success':True,'country_code':'DE'},3:{'ip':'8.8.4.4','country':'FR'}}
        result=assess_responses(observations)
        self.assertFalse(result['country_verified'])
        self.assertIsNone(result['verified_country'])
        self.assertEqual(result['exit_ipv4'],'8.8.4.4')

    def test_metadata_lookup_is_bound_to_measured_exit_not_runner_ip(self):
        with patch('urllib.request.build_opener') as opener:
            response=opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value=b'{"ip":"51.75.145.20","country":"DE"}'
            self.assertEqual(conflict_lookup('51.75.145.20'),{'ip':'51.75.145.20','country':'DE'})
            self.assertEqual(opener.return_value.open.call_args.args[0],'https://api.country.is/51.75.145.20')
            response.read.return_value=b'{"ip":"8.8.8.8","country":"DE"}'
            with self.assertRaises(ValueError):conflict_lookup('51.75.145.20')

    def test_private_or_malformed_exit_cannot_choose_lookup_url(self):
        with patch('urllib.request.build_opener') as opener:
            for address in ['127.0.0.1','169.254.169.254','evil.example/path']:
                with self.assertRaises(ValueError):conflict_lookup(address)
            opener.assert_not_called()

    def test_reported_france_source_is_required_and_has_veto(self):
        observations={1:{'ip':'51.75.145.220','country_iso':'DE'},
                      2:{'ip':'51.75.145.220','success':True,'country_code':'DE'},
                      3:{'ip':'51.75.145.220','country':'DE'}}
        self.assertFalse(assess_responses(observations,require_conflict_source=True)['country_verified'])
        observations[4]={'ip':'51.75.145.220','country':'FR'}
        rejected=assess_responses(observations,require_conflict_source=True)
        self.assertFalse(rejected['country_verified'])
        self.assertTrue(rejected['conflict_source_checked'])
        self.assertIsNone(rejected['verified_country'])
        observations[4]['country']='DE'
        self.assertTrue(assess_responses(observations,require_conflict_source=True)['country_verified'])

    def test_observed_country_is_not_assigned_from_provider_label(self):
        observations={1:{'ip':'8.8.4.4','country_iso':'FR'},3:{'ip':'8.8.4.4','country':'FR'}}
        self.assertFalse(assess_responses(observations,'DE')['country_verified'])
        self.assertTrue(assess_responses(observations,'FR')['country_verified'])
        observations[3]['ip']='1.1.1.1'
        self.assertFalse(assess_responses(observations,'FR')['country_verified'])
