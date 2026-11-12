#!/usr/bin/env bash
# Ephemeral runner tuning only. No persistent sysctl files, route changes,
# firewall changes, offload disabling or promises about client-side latency.
set -euo pipefail
if [[ "$EUID" -ne 0 ]]; then echo 'Runtime tuning needs root'; exit 1; fi
apply() {
  local key="$1" value="$2"
  if sysctl -q -w "$key=$value" >/dev/null 2>&1; then
    printf 'Applied %s=%s\n' "$key" "$value"
  else
    printf 'Unavailable: %s; retaining kernel default\n' "$key"
  fi
}
# quic-go needs receive/send headroom on a busy connector. Never shrink a
# runner whose buffers are already larger than this minimum.
for key in net.core.rmem_max net.core.wmem_max; do
  current="$(sysctl -n "$key" 2>/dev/null || echo 0)"
  if [[ "$current" =~ ^[0-9]+$ ]] && (( current < 8388608 )); then apply "$key" 8388608; fi
done
# Probe a smaller TCP MTU only when the kernel detects a PMTU black hole.
apply net.ipv4.tcp_mtu_probing 1
# BBR affects TCP egress/HTTP2, not QUIC's userspace congestion control.
modprobe tcp_bbr 2>/dev/null || true
available="$(sysctl -n net.ipv4.tcp_available_congestion_control 2>/dev/null || true)"
if [[ " $available " == *' bbr '* ]]; then
  apply net.core.default_qdisc fq
  apply net.ipv4.tcp_congestion_control bbr
else
  echo 'BBR unavailable; keeping existing congestion control'
fi
