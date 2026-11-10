#!/usr/bin/env bash
# Build upstream wg only. No wg-quick, installation, configuration or connection.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REV=a998407747005ea7e4e0258d96f105c97241e1d3
DEST="$ROOT/.runtime/tool-src/wireguard-tools"
mkdir -p "$(dirname "$DEST")"
if [ ! -d "$DEST/.git" ]; then
  git clone --quiet https://github.com/WireGuard/wireguard-tools.git "$DEST"
fi
if [ "$(git -C "$DEST" remote get-url origin)" != 'https://github.com/WireGuard/wireguard-tools.git' ]; then
  echo 'Unexpected WireGuard source remote' >&2
  exit 1
fi
if ! git -C "$DEST" cat-file -e "$REV^{commit}"; then
  git -C "$DEST" fetch --quiet origin "$REV"
fi
git -C "$DEST" checkout --quiet --detach "$REV"
if [ -n "$(git -C "$DEST" status --porcelain --untracked-files=no)" ]; then
  echo 'WireGuard source has local changes; refusing build' >&2
  exit 1
fi
make -C "$DEST/src" -j2 WITH_WGQUICK=no WITH_SYSTEMDUNITS=no
"$DEST/src/wg" --version
