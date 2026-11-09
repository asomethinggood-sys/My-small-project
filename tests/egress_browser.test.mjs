import test from 'node:test';
import assert from 'node:assert/strict';
import {GERMAN_SERVER_LABEL, UDP53_LABEL, CONFIG_DOWNLOAD_LABEL, candidatePolicy, downloadFormat, allowedSource} from '../scripts/egress_browser_policy.mjs';

test('current provider accessible labels match without matching another server', () => {
  assert.ok(GERMAN_SERVER_LABEL.test('Germany Server 1de20.vpnbook.com'));
  assert.ok(GERMAN_SERVER_LABEL.test('Germany Server 1 de20.vpnbook.com'));
  assert.ok(!GERMAN_SERVER_LABEL.test('Germany Server 2de220.vpnbook.com'));
  assert.ok(UDP53_LABEL.test('UDP 53DNS port - Good for restricted networks'));
  assert.ok(CONFIG_DOWNLOAD_LABEL.test('Download .ovpn File'));
  assert.ok(!CONFIG_DOWNLOAD_LABEL.test('3Download Configuration'));
  assert.ok(!CONFIG_DOWNLOAD_LABEL.test('Download xovpn File'));
});
test('bounded candidate selection matches the exact server and UDP port', () => {
  const first = candidatePolicy('de20', '25000');
  assert.equal(first.id, 'vpnbook-de20-udp25000');
  assert.ok(first.serverLabel.test('Germany Server 1de20.vpnbook.com'));
  assert.ok(!first.serverLabel.test('Germany Server 2de220.vpnbook.com'));
  assert.ok(first.protocolLabel.test('UDP 25000High port'));
  assert.ok(!first.protocolLabel.test('UDP 53DNS port'));
  const second = candidatePolicy('de220', '53');
  assert.ok(second.serverLabel.test('Germany Server 2de220.vpnbook.com'));
  assert.ok(second.protocolLabel.test('UDP 53DNS port'));
  assert.ok(!second.protocolLabel.test('UDP 5353'));
  assert.throws(() => candidatePolicy('other', '53'));
  assert.throws(() => candidatePolicy('de20', '443'));
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
