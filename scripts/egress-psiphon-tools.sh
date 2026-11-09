#!/usr/bin/env bash
# Upstream release-candidate tools for LOCAL fixtures, not a production client.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REV=0f968b4dd6981b75aad9c72b51e39edfefec52ff
SOURCE="$ROOT/.runtime/tool-src/psiphon-binaries"
DEST="$ROOT/.runtime/psiphon-bin"
mkdir -p "$(dirname "$SOURCE")" "$DEST"
if [ ! -d "$SOURCE/.git" ]; then
  git clone --quiet --filter=blob:none --no-checkout https://github.com/Psiphon-Labs/psiphon-tunnel-core-binaries.git "$SOURCE"
fi
if [ "$(git -C "$SOURCE" remote get-url origin)" != 'https://github.com/Psiphon-Labs/psiphon-tunnel-core-binaries.git' ]; then
  echo 'Unexpected Psiphon tool source' >&2
  exit 1
fi
git -C "$SOURCE" sparse-checkout set linux psiphond
if ! git -C "$SOURCE" cat-file -e "$REV^{commit}"; then
  git -C "$SOURCE" fetch --quiet origin "$REV"
fi
git -C "$SOURCE" checkout --quiet --detach "$REV"
CLIENT="$SOURCE/linux/psiphon-tunnel-core-x86_64"
SERVER="$SOURCE/psiphond/psiphond"
[ "$(git hash-object "$CLIENT")" = a078d26335d59f2de7a934bbf2f2813680f5d336 ]
[ "$(git hash-object "$SERVER")" = fa2869a4ee6dc550860b7aa7ea39e26aebbac2a3 ]
printf '%s  %s\n' d83dcaa632b265536852e2d97c45eb4831960f8dbcb2d8638293d5958483705b "$CLIENT" | sha256sum -c -
printf '%s  %s\n' 073769485c5b5817e042f7f0e9a51a1b09cd1050ccb61d667f62038874d7db43 "$SERVER" | sha256sum -c -
install -m 755 "$CLIENT" "$DEST/client"
install -m 755 "$SERVER" "$DEST/server"
echo 'Pinned upstream Psiphon RC fixtures ready; no public Psiphon connection made.'
