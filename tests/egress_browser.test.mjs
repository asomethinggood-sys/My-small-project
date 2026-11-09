import test from 'node:test';
import assert from 'node:assert/strict';
import {GERMAN_SERVER_LABEL, UDP53_LABEL, downloadFormat, allowedSource} from '../scripts/egress_browser_policy.mjs';

test('current provider accessible labels match without matching another server', () => {
  assert.ok(GERMAN_SERVER_LABEL.test('Germany Server 1de20.vpnbook.com'));
  assert.ok(GERMAN_SERVER_LABEL.test('Germany Server 1 de20.vpnbook.com'));
  assert.ok(!GERMAN_SERVER_LABEL.test('Germany Server 2de220.vpnbook.com'));
  assert.ok(UDP53_LABEL.test('UDP 53DNS port - Good for restricted networks'));
});
test('download names cannot select paths or executable formats', () => {
  assert.equal(downloadFormat('vpnbook-de20-udp53.ovpn'), 'ovpn');
  assert.equal(downloadFormat('VPNBook-DE20.zip'), 'zip');
  for (const name of ['../../bad.ovpn', 'file.exe', 'bad\n.ovpn', '/tmp/key.zip'])
    assert.equal(downloadFormat(name), null);
});
test('only the official HTTPS host is admitted', () => {
  assert.ok(allowedSource('https://www.vpnbook.com/freevpn/openvpn'));
  for (const url of ['http://www.vpnbook.com/', 'https://evil.example/',
                     'https://user:pass@www.vpnbook.com/', 'bad']) assert.ok(!allowedSource(url));
});
