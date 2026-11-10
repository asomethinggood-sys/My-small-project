import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import worker, {handle, validRoute} from '../worker/worker.mjs';

const profile = JSON.parse(readFileSync(new URL('../worker/profile.json', import.meta.url)));
const token = 'test-only-not-a-real-secret-1234567890';
const route = () => ({host: 'sample-tunnel.trycloudflare.com', expiresAt: Date.now() + 3600000});
function environment(initial = null) {
  let saved = initial;
  return {UPDATE_TOKEN: token, ROUTES: {
    async get() { return saved; },
    async put(key, text, options) {
      assert.equal(key, 'active-route');
      assert.equal(options.expirationTtl, 21600);
      saved = JSON.parse(text);
    }
  }};
}
const update = (body, secret = token) => new Request(`https://${profile.host}/__route`, {
  method: 'POST', headers: {'Authorization': `Bearer ${secret}`}, body: JSON.stringify(body)
});
const socket = () => new Request(`https://${profile.host}${profile.path}`, {
  headers: {Upgrade: 'websocket', 'Sec-WebSocket-Protocol': 'early-data-bytes',
    Cookie: 'private-cookie', Authorization: 'private-header'}
});

test('route permits only a bounded HTTPS Quick Tunnel destination', () => {
  assert.ok(validRoute(route()));
  for (const host of ['127.0.0.1', 'localhost', 'x.trycloudflare.com.evil.com',
    'https://x.trycloudflare.com', 'a@x.trycloudflare.com', 'x.trycloudflare.com:443'])
    assert.equal(validRoute({...route(), host}), false);
  for (const expiresAt of [0, Date.now() - 1, Date.now() + 21601000, 'tomorrow'])
    assert.equal(validRoute({...route(), expiresAt}), false);
});

test('no unauthenticated route update', async () => {
  assert.equal((await handle(update(route(), 'wrong'), environment())).status, 401);
  assert.equal((await handle(update(route()), {})).status, 503);
});

test('valid update survives across separate requests; invalid update does not replace it', async () => {
  const env = environment();
  assert.equal((await handle(update(route()), env)).status, 200);
  assert.equal((await handle(update({...route(), host: 'evil.com'}), env)).status, 400);
  assert.equal((await env.ROUTES.get()).host, route().host);
});

test('request bodies are bounded', async () => {
  assert.equal((await handle(update({padding: 'x'.repeat(2048)}), environment())).status, 413);
});

test('expired or missing route fails closed', async () => {
  for (const initial of [null, {...route(), expiresAt: 0}]) {
    const response = await handle(socket(), environment(initial), () => assert.fail('must not fetch'));
    assert.equal(response.status, 503);
  }
});

test('WebSocket forwards early data, strips secrets, and returns upgrade unchanged', async () => {
  const upgrade = {status: 101, webSocket: {mock: true}};
  const response = await handle(socket(), environment(route()), async (url, init) => {
    assert.equal(url, `https://sample-tunnel.trycloudflare.com${profile.path}`);
    assert.equal(init.redirect, 'manual');
    assert.equal(init.headers.get('Sec-WebSocket-Protocol'), 'early-data-bytes');
    for (const header of ['Cookie', 'Authorization', 'Host']) assert.equal(init.headers.get(header), null);
    return upgrade;
  });
  assert.equal(response, upgrade);
});

test('backend redirects and errors are not followed or passed off as success', async () => {
  for (const status of [200, 301, 403, 502])
    assert.equal((await handle(socket(), environment(route()), async () => new Response('', {status}))).status, 502);
  assert.equal((await handle(socket(), environment(route()), async () => {throw Error('offline');})).status, 502);
});

test('only exact WS path accepts upgrades, ordinary requests cannot proxy arbitrary URLs', async () => {
  assert.equal((await handle(new Request(`https://${profile.host}/other`), environment(route()))).status, 404);
  assert.equal((await handle(new Request(`https://${profile.host}${profile.path}`), environment(route()))).status, 426);
  assert.equal((await handle(new Request(`https://${profile.host}${profile.path}?target=evil.com`), environment(route()))).status, 400);
});

test('Cloudflare entrypoint does not confuse execution context with fetch dependency', async () => {
  const response = await worker.fetch(new Request(`https://${profile.host}/healthz`), environment(route()), {});
  assert.equal(response.status, 200);
  assert.match(await response.text(), /NOT an end-to-end/);
});
