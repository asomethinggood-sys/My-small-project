#!/usr/bin/env bash
set -euo pipefail
out="${1:-.runtime/bin}"
mkdir -p "$out"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fL --connect-timeout 15 --max-time 180 --retry 3 \
  https://github.com/cloudflare/cloudflared/releases/download/2026.10.7/cloudflared-linux-amd64 -o "$tmp"
echo "1f99fb518b83dec2ba8d870a7cc991d82a77e6196295a3d2754ba17ab9f91872  $tmp" | sha256sum -c -
install -m 755 "$tmp" "$out/cloudflared"
