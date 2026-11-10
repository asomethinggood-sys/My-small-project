#!/usr/bin/env bash
# Run ON a dedicated Debian/Ubuntu x86_64 VPS after configuring DNS/firewalls.
set -euo pipefail
cd "$(dirname "$0")/.."
[[ $EUID -eq 0 && $(uname -m) == x86_64 ]] || { echo 'Requires root on Linux x86_64'; exit 1; }
[[ $# -eq 1 ]] || { echo 'Usage: sudo bash scripts/deploy-vps.sh vpn.your-domain.tld'; exit 1; }
# Do not overwrite an unrelated web server installation.
for unit in caddy nginx apache2; do
  if systemctl is-active --quiet "$unit"; then echo "Stop/reconcile existing $unit first"; exit 1; fi
done
umask 077
python3 scripts/generate.py --host "$1" --output /etc/arena-vpn
bash scripts/download-binaries.sh .runtime/bin
.runtime/bin/xray run -test -c /etc/arena-vpn/xray.json
# Adapt offline; validation with automatic HTTPS can have provisioning side effects.
.runtime/bin/caddy adapt --config /etc/arena-vpn/Caddyfile --adapter caddyfile >/dev/null
id arena-vpn >/dev/null 2>&1 || useradd --system --home-dir /var/lib/arena-vpn --shell /usr/sbin/nologin arena-vpn
install -d -m 755 /usr/local/lib/arena-vpn
install -m 755 .runtime/bin/{xray,caddy} /usr/local/lib/arena-vpn/
chown -R root:arena-vpn /etc/arena-vpn
chmod 750 /etc/arena-vpn
chmod 640 /etc/arena-vpn/{xray.json,Caddyfile}
for service in xray caddy; do
  if [[ $service == xray ]]; then
    args='run -c /etc/arena-vpn/xray.json'
  else
    args='run --config /etc/arena-vpn/Caddyfile --adapter caddyfile'
  fi
  cat > "/etc/systemd/system/arena-$service.service" <<UNIT
[Unit]
Description=Arena VPS $service
Wants=network-online.target
After=network-online.target
[Service]
User=arena-vpn
Group=arena-vpn
StateDirectory=arena-vpn
Environment=HOME=/var/lib/arena-vpn
ExecStart=/usr/local/lib/arena-vpn/$service $args
Restart=always
RestartSec=5
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=/var/lib/arena-vpn
LimitNOFILE=65536
[Install]
WantedBy=multi-user.target
UNIT
done
rm -f /etc/arena-vpn/verified-{uri,subscription}.txt
systemctl daemon-reload
systemctl enable arena-xray arena-caddy
systemctl restart arena-xray arena-caddy
echo 'Services started, NOT yet verified. Wait for certificate issuance; run:'
echo 'sudo bash scripts/verify.sh /etc/arena-vpn /usr/local/lib/arena-vpn/xray'
