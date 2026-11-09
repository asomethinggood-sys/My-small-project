export const GERMAN_SERVER_LABEL = /Germany Server 1.*de20\.vpnbook\.com/i;
export const UDP53_LABEL = /UDP 53/i;
export const CONFIG_DOWNLOAD_LABEL = /^Download \.ovpn File$/i;
export function candidatePolicy(server = 'de20', port = '53') {
  if (!['de20', 'de220'].includes(server) || !['53', '25000'].includes(port))
    throw new Error('Unsupported bounded test candidate');
  const number = server === 'de20' ? '1' : '2';
  return {id: `vpnbook-${server}-udp${port}`, server, port: Number(port),
    hostname: `${server}.vpnbook.com`,
    serverLabel: new RegExp(`Germany Server ${number}.*${server}[.]vpnbook[.]com`, 'i'),
    protocolLabel: new RegExp(`UDP ${port}(?![0-9])`, 'i')};
}
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
