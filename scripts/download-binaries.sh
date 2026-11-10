#!/usr/bin/env bash
# Linux x86_64 only. Immutable release versions + hashes from GitHub release assets.
set -euo pipefail
out="$(realpath -m "${1:-.runtime/bin}")"
mkdir -p "$out"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fL --connect-timeout 15 --max-time 180 --retry 3 https://github.com/XTLS/Xray-core/releases/download/v26.10.31/Xray-linux-64.zip -o "$tmp/xray.zip"
echo "e4bd9119f50ae7c41658b1abd0679ae06f98bd864a2907ff33f2f2cf7081b214  $tmp/xray.zip" | sha256sum -c -
unzip -qo "$tmp/xray.zip" xray -d "$out"
chmod 755 "$out/xray"
if [[ "${2:-}" == --xray-only ]]; then exit 0; fi
curl -fL --connect-timeout 15 --max-time 180 --retry 3 https://github.com/caddyserver/caddy/releases/download/v2.11.9/caddy_2.11.9_linux_amd64.tar.gz -o "$tmp/caddy.tar.gz"
echo "5b8cb7faf8726a2028ad96a66e54e6e81e8f361bc6175e5d22bbd997cc5177fb  $tmp/caddy.tar.gz" | sha256sum -c -
tar -xzf "$tmp/caddy.tar.gz" -C "$out" caddy
chmod 755 "$out/xray" "$out/caddy"
