import copy
import unittest
from unittest.mock import patch
from scripts.egress_path_probe import client_config, request
from scripts.egress_openvpn_probe import assess_responses


class IssuedPathTests(unittest.TestCase):
    def lease(self):
        return {'country':'DE','token':'A'*43,'generation':1,'expires_in':90,
                'profile':'vless://12345678-1234-1234-1234-123456789abc@trial.example:443?security=tls&type=ws&sni=trial.example&host=trial.example&path=%2Fs%2F'+'A'*43+'%2F1'}

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

    def test_any_french_observation_rejects_german_selection(self):
        observations={0:{'ip':'8.8.4.4'},1:{'ip':'8.8.4.4','country_iso':'DE'},
                      2:{'ip':'8.8.4.4','success':True,'country_code':'DE'},3:{'ip':'8.8.4.4','country':'FR'}}
        result=assess_responses(observations)
        self.assertFalse(result['country_verified'])
        self.assertIsNone(result['verified_country'])
        self.assertEqual(result['exit_ipv4'],'8.8.4.4')

    def test_observed_country_is_not_assigned_from_provider_label(self):
        observations={1:{'ip':'8.8.4.4','country_iso':'FR'},3:{'ip':'8.8.4.4','country':'FR'}}
        self.assertFalse(assess_responses(observations,'DE')['country_verified'])
        self.assertTrue(assess_responses(observations,'FR')['country_verified'])
        observations[3]['ip']='1.1.1.1'
        self.assertFalse(assess_responses(observations,'FR')['country_verified'])
