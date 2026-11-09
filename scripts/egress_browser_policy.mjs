export const GERMAN_SERVER_LABEL = /Germany Server 1.*de20\.vpnbook\.com/i;
export const UDP53_LABEL = /UDP 53/i;
export function downloadFormat(name) {
  if (!/^[A-Za-z0-9_.-]{1,100}\.(zip|ovpn)$/i.test(name)) return null;
  return name.toLowerCase().endsWith('.zip') ? 'zip' : 'ovpn';
}
export function allowedSource(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' && !parsed.username && !parsed.password &&
      ['vpnbook.com', 'www.vpnbook.com'].includes(parsed.hostname);
  } catch { return false; }
}
