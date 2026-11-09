// Public-page browser acquisition probe. No login, CAPTCHA solving or VPN connection.
import { chromium } from '../.runtime/browser/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
import {GERMAN_SERVER_LABEL, UDP53_LABEL, CONFIG_DOWNLOAD_LABEL, downloadFormat, allowedSource} from './egress_browser_policy.mjs';

const report = {provider: 'vpnbook', protocol: 'openvpn', country: 'DE',
  connection_tested: false, status: 'not_started'};
const browser = await chromium.launch({headless: true});
try {
  const context = await browser.newContext({acceptDownloads: true});
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    // Do not fetch ads/trackers or interact with an external verification service.
    if (allowedSource(url.href))
      return route.continue();
    return route.abort();
  });
  const page = await context.newPage();
  await page.goto('https://www.vpnbook.com/freevpn/openvpn', {waitUntil: 'networkidle', timeout: 30000});
  // Wait for hydration via visible controls, not a long-lived background process.
  await page.locator('body').waitFor();
  report.has_german_endpoint = await page.getByText('de20.vpnbook.com', {exact: true}).count() > 0;
  const controls = await page.locator('button, a[download], select').evaluateAll(elements =>
    elements.map(el => ({tag: el.tagName, text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 100)}))
      .filter(el => /download|openvpn|udp|tcp|germany|de20/i.test(el.text)).slice(0, 30));
  // Export only allowlisted control labels, never document text/credentials/configs.
  report.controls = controls.filter(item => !/password|username|private|key/i.test(item.text));
  const germany = page.getByText('de20.vpnbook.com', {exact: true}).first();
  let button;
  if (await germany.count()) {
    for (let depth = 1; depth <= 5; depth++) {
      const ancestor = germany.locator('xpath=' + Array(depth).fill('..').join('/'));
      const choices = ancestor.getByRole('button', {name: /download/i});
      if (await choices.count() === 1) {button = choices.first(); break;}
      const links = ancestor.getByRole('link', {name: /download/i});
      if (await links.count() === 1) {button = links.first(); break;}
    }
  }
  if (!button) {
    // Current official UI is a server selector followed by protocol selectors,
    // rather than a static ZIP link. Use those controls without guessing APIs.
    const server = page.getByRole('button', {name: GERMAN_SERVER_LABEL});
    if (await server.count() === 1) {
      await server.click({timeout: 10000});
      const protocol = page.getByRole('button', {name: UDP53_LABEL});
      if (await protocol.count() === 1) button = protocol;
    }
  }
  if (!button) report.status = 'no_unambiguous_german_download_control';
  else {
    const text = await button.innerText();
    if (/verify|captcha|check/i.test(text)) report.status = 'verification_required';
    else {
      const downloadPromise = page.waitForEvent('download', {timeout: 15000});
      // Attach rejection handling before the click, to avoid unhandled timeout.
      const pending = downloadPromise.catch(() => null);
      await button.click({timeout: 10000});
      const confirm = page.getByRole('button', {name: CONFIG_DOWNLOAD_LABEL});
      const link = page.getByRole('link', {name: CONFIG_DOWNLOAD_LABEL});
      if (await confirm.count() === 1) await confirm.click({timeout: 10000});
      else if (await link.count() === 1) await link.click({timeout: 10000});
      const download = await pending;
      if (!download) {
        report.status = 'download_not_started';
        report.remaining_controls = await page.locator('button, a[download], label').evaluateAll(elements =>
          elements.map(el => (el.textContent || '').trim().replace(/\s+/g, ' '))
            .filter(text => text.length < 150 && /download|verify|captcha|generate|agree|accept|continue/i.test(text)
              && !/password|username|private|key/i.test(text)).slice(0, 12));
        report.verification_iframe_present = await page.locator('iframe[src*="challenges.cloudflare.com"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]').count() > 0;
        if (report.verification_iframe_present) report.status = 'verification_required';
      }
      else {
        const filename = download.suggestedFilename();
        if (!downloadFormat(filename)) {
          await download.cancel(); report.status = 'unexpected_download_name';
        } else {
          const stream = await download.createReadStream();
          let size = 0;
          const chunks = [];
          for await (const chunk of stream) {
            size += chunk.length;
            if (size > 2 * 1024 * 1024) {await download.cancel(); break;}
            chunks.push(chunk);
          }
          report.status = size > 2 * 1024 * 1024 ? 'download_size_rejected' : 'download_received_unverified';
          report.bytes = size;
          report.format = downloadFormat(filename);
          if (size <= 2 * 1024 * 1024) {
            const result = spawnSync('python3', ['-m', 'scripts.egress_vpnbook',
              report.format === 'zip' ? '--bundle-stdin' : '--profile-stdin'],
              {input: Buffer.concat(chunks), encoding: 'utf8', timeout: 20000,
                maxBuffer: 65536, env: {PATH: process.env.PATH}});
            if (result.status === 0) report.inspection = JSON.parse(result.stdout);
            else report.inspection = {status: 'inspection_process_failed'};
          }
          if (process.env.NYX_PROVIDER_PROBE === 'true' && report.format === 'ovpn'
              && report.inspection?.status === 'sanitized_unverified') {
            const bodyText = await page.locator('body').innerText();
            const username = bodyText.match(/Username\s*:\s*(vpnbook)\b/i);
            const password = bodyText.match(/Password\s*:\s*([A-Za-z0-9_-]{4,64})\b/i);
            if (username && password && !/loading|hidden/i.test(password[1])) {
              const input = JSON.stringify({provider: 'vpnbook', username: 'vpnbook', password: password[1],
                profile_base64: Buffer.concat(chunks).toString('base64')});
              const result = spawnSync('sudo', ['-n', 'python3', '-m', 'scripts.egress_openvpn_probe'],
                {input, encoding: 'utf8', timeout: 125000, maxBuffer: 65536, env: {PATH: process.env.PATH}});
              report.live_probe = result.status === 0 ? JSON.parse(result.stdout) : {status: 'probe_process_failed'};
            } else report.live_probe = {status: 'public_credentials_not_detected'};
          }
          await download.delete();
        }
      }
    }
  }
} catch {
  report.status = 'browser_or_source_error';
} finally {
  await browser.close();
}
await fs.mkdir('.runtime/egress', {recursive: true});
await fs.writeFile('.runtime/egress/vpnbook-browser.json', JSON.stringify(report, null, 2) + '\n');
console.log(`::notice title=Nyx browser acquisition::${report.status}; German endpoint visible=${report.has_german_endpoint || false}`);
if (report.inspection) {
  console.log(`::notice title=Nyx downloaded configuration::${report.inspection.status}`);
  if (report.inspection.reason) console.log(`::notice title=Nyx configuration policy::${report.inspection.reason}`);
  if (report.inspection.directive_names) console.log(`::notice title=Nyx configuration directives::${report.inspection.directive_names.join(',')}`);
  if (report.inspection.inline_blocks) console.log(`::notice title=Nyx configuration block types::${report.inspection.inline_blocks.join(',')}`);
}
if (report.live_probe) {
  console.log(`::notice title=Nyx bounded provider test::${report.live_probe.status}; stage=${report.live_probe.failed_stage || 'complete'}; daemon_alive=${report.live_probe.openvpn_alive_at_failure === true}; country_verified=${report.live_probe.country_verified === true}; UDP_DNS=${report.live_probe.udp_dns_passed === true}; host_routes_unchanged=${report.live_probe.host_main_routes_unchanged === true}`);
}
for (const text of report.remaining_controls || []) {
  console.log(`::notice title=Nyx remaining control::${text.replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A')}`);
}
for (const item of report.controls || []) {
  const text = item.text.replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A');
  console.log(`::notice title=Nyx download control::${text}`);
}
