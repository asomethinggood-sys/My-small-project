// Public-page browser acquisition probe. No login, CAPTCHA solving or VPN connection.
import { chromium } from '../.runtime/browser/node_modules/playwright/index.mjs';
import fs from 'node:fs/promises';

const report = {provider: 'vpnbook', protocol: 'openvpn', country: 'DE',
  connection_tested: false, status: 'not_started'};
const browser = await chromium.launch({headless: true});
try {
  const context = await browser.newContext({acceptDownloads: true});
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    // Do not fetch ads/trackers or interact with an external verification service.
    if (url.protocol === 'https:' && ['vpnbook.com', 'www.vpnbook.com'].includes(url.hostname))
      return route.continue();
    return route.abort();
  });
  const page = await context.newPage();
  await page.goto('https://www.vpnbook.com/freevpn/openvpn', {waitUntil: 'domcontentloaded', timeout: 30000});
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
  if (!button) report.status = 'no_unambiguous_german_download_control';
  else {
    const text = await button.innerText();
    if (/verify|captcha|check/i.test(text)) report.status = 'verification_required';
    else {
      const downloadPromise = page.waitForEvent('download', {timeout: 15000});
      // Attach rejection handling before the click, to avoid unhandled timeout.
      const pending = downloadPromise.catch(() => null);
      await button.click({timeout: 10000});
      const download = await pending;
      if (!download) report.status = 'download_not_started_or_verification_required';
      else {
        const filename = download.suggestedFilename();
        if (!/^[A-Za-z0-9_.-]{1,100}\.(zip|ovpn)$/i.test(filename)) {
          await download.cancel(); report.status = 'unexpected_download_name';
        } else {
          const stream = await download.createReadStream();
          let size = 0;
          for await (const chunk of stream) {
            size += chunk.length;
            if (size > 2 * 1024 * 1024) {await download.cancel(); break;}
          }
          report.status = size > 2 * 1024 * 1024 ? 'download_size_rejected' : 'download_received_unverified';
          report.bytes = size;
          report.format = filename.toLowerCase().endsWith('.zip') ? 'zip' : 'ovpn';
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
for (const item of report.controls || []) {
  const text = item.text.replace(/%/g, '%25').replace(/\r/g, '%0D').replace(/\n/g, '%0A');
  console.log(`::notice title=Nyx download control::${text}`);
}
