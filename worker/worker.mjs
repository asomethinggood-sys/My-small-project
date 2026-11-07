// Paste this entire module into Cloudflare's Worker editor, then Deploy.
// Bind KV namespace ROUTES and encrypted secret UPDATE_TOKEN before use.
// This relays WebSockets; it does NOT implement a VLESS egress or TCP socket API.
const WS_PATH = '/cc348e094b70465493bfd61bc17cb083';
const KEY = 'active-route';
const MAX_LEASE_SECONDS = 6 * 60 * 60;

export function validRoute(route, now = Date.now()) {
  return route !== null && typeof route === 'object' &&
    typeof route.host === 'string' &&
    /^[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com$/.test(route.host) &&
    route.host.length <= 253 && Number.isSafeInteger(route.expiresAt) &&
    route.expiresAt > now && route.expiresAt <= now + MAX_LEASE_SECONDS * 1000;
}

function reply(message, status) {
  return new Response(message, {status, headers: {'Cache-Control': 'no-store'}});
}

export async function handle(request, env, fetchUpstream = fetch) {
  const url = new URL(request.url);
  if (url.pathname === '/__route') {
    if (request.method !== 'POST') return reply('Method not allowed', 405);
    if (!env.UPDATE_TOKEN || env.UPDATE_TOKEN.length < 32 || !env.ROUTES)
      return reply('Relay is not configured', 503);
    if (request.headers.get('Authorization') !== `Bearer ${env.UPDATE_TOKEN}`)
      return reply('Unauthorized', 401);
    if (Number(request.headers.get('Content-Length') || 0) > 1024)
      return reply('Too large', 413);
    // Bound streamed bodies too; do not trust Content-Length.
    const reader = request.body?.getReader();
    if (!reader) return reply('Invalid body', 400);
    let bytes = 0;
    const chunks = [];
    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > 1024) { await reader.cancel(); return reply('Too large', 413); }
      chunks.push(value);
    }
    let route;
    try {
      const body = new Uint8Array(bytes);
      let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
      route = JSON.parse(new TextDecoder().decode(body));
    } catch { return reply('Invalid JSON', 400); }
    if (!validRoute(route)) return reply('Invalid or expired route', 400);
    try {
      await env.ROUTES.put(KEY, JSON.stringify({host: route.host, expiresAt: route.expiresAt}),
        {expirationTtl: MAX_LEASE_SECONDS});
    } catch { return reply('Route storage unavailable', 503); }
    return reply('Route accepted; propagation and proxy checks still required', 200);
  }
  if (url.pathname !== WS_PATH && url.pathname !== '/healthz') return reply('Not found', 404);
  if (request.method !== 'GET') return reply('Method not allowed', 405);
  if (url.search) return reply('Unexpected query', 400);
  if (url.pathname === WS_PATH && request.headers.get('Upgrade')?.toLowerCase() !== 'websocket')
    return reply('WebSocket required', 426);
  if (!env.ROUTES) return reply('Relay is not configured', 503);
  let route;
  try { route = await env.ROUTES.get(KEY, {type: 'json', cacheTtl: 60}); }
  catch { return reply('Route storage unavailable', 503); }
  if (!validRoute(route)) return reply('No active route', 503);
  if (url.pathname === '/healthz') return reply('Route present; NOT an end-to-end proxy test', 200);

  // Only forward the required handshake headers, never cookies or update credentials.
  const headers = new Headers();
  for (const name of ['Upgrade', 'Connection', 'Sec-WebSocket-Key',
    'Sec-WebSocket-Version', 'Sec-WebSocket-Protocol', 'Sec-WebSocket-Extensions']) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  try {
    const response = await fetchUpstream(`https://${route.host}${WS_PATH}`,
      {method: 'GET', headers, redirect: 'manual'});
    // A redirect or HTTP page is not a valid tunnel; never follow arbitrary destinations.
    if (response.status !== 101) {
      await response.body?.cancel();
      return reply('Backend WebSocket unavailable', 502);
    }
    return response;
  } catch { return reply('Backend unavailable', 502); }
}

export default {fetch(request, env) { return handle(request, env); }};
