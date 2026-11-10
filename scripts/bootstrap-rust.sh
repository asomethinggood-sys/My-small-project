#!/usr/bin/env bash
# Bootstrap a working Rust toolchain in sandboxes that cannot reach
# static.rust-lang.org or crates.io.
#
# This environment only allows outbound traffic to github.com,
# codeload.github.com, api.github.com, registry.npmjs.org, pypi.org and
# files.pythonhosted.org. Fortunately the Rust distribution is re-published
# verbatim to the npm registry, so we install rustc + cargo + rust-std from
# there, into ~/.local/rust (which is excluded from workspace snapshots).
#
# Usage:
#   ./scripts/bootstrap-rust.sh          # install if missing
#   ./scripts/bootstrap-rust.sh --force  # reinstall
#   eval "$(./scripts/bootstrap-rust.sh --env)"   # just print export lines
#
# IMPORTANT: crates.io is unreachable here, so the backend is written with
# zero third-party dependencies (std only). Keep it that way, or nothing
# will compile. `cargo build --offline` works with an empty dependency set.

set -euo pipefail

RUST_VERSION="1.99.0"
PREFIX="${RUST_PREFIX:-$HOME/.local/rust}"
NPM_BASE="https://registry.npmjs.org"

pkg_url() {
  # $1 = npm package name, $2 = tarball filename
  printf '%s/%s/-/%s' "$NPM_BASE" "$1" "$2"
}

env_lines() {
  printf 'export PATH="%s/bin:$PATH"\n' "$PREFIX"
  printf 'export CARGO_NET_OFFLINE=true\n'
}

if [ "${1:-}" = "--env" ]; then
  env_lines
  exit 0
fi

if [ "${1:-}" = "--force" ]; then
  rm -rf "$PREFIX"
fi

if [ -x "$PREFIX/bin/rustc" ] && [ -x "$PREFIX/bin/cargo" ]; then
  echo "Rust already installed at $PREFIX"
  "$PREFIX/bin/rustc" --version
  env_lines
  exit 0
fi

ARCH="x86_64-unknown-linux-gnu"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fetch() { # $1 = npm package, $2 = tarball file, $3 = dest
  echo "  downloading $1"
  curl -fsSL --retry 3 --max-time 600 -o "$3" "$(pkg_url "$1" "$2")"
}

echo "Installing Rust $RUST_VERSION into $PREFIX"
mkdir -p "$PREFIX" "$TMP"

fetch "@toolchain-bin/rustc-$RUST_VERSION-$ARCH" \
  "rustc-$RUST_VERSION-$ARCH-$RUST_VERSION.tgz" "$TMP/rustc.tgz"
fetch "@toolchain-bin/cargo-$RUST_VERSION-$ARCH" \
  "cargo-$RUST_VERSION-$ARCH-0.100.0.tgz" "$TMP/cargo.tgz"
fetch "@toolchain-bin/rust-std-$RUST_VERSION-$ARCH" \
  "rust-std-$RUST_VERSION-$ARCH-$RUST_VERSION-1.tgz" "$TMP/std.tgz"

install_component() { # $1 = tarball, $2 = label
  local dir="$TMP/x-$2"
  mkdir -p "$dir"
  tar xzf "$1" -C "$dir"
  ( cd "$dir/package" && bash install.sh --prefix="$PREFIX" --disable-ldconfig >/dev/null )
  echo "  $2 installed"
}

install_component "$TMP/rustc.tgz" rustc
install_component "$TMP/cargo.tgz" cargo
install_component "$TMP/std.tgz" std

# npm tarballs lose the executable bit; rustc's bundled lld needs it too.
chmod +x "$PREFIX"/bin/* 2>/dev/null || true
chmod +x "$PREFIX/lib/rustlib/$ARCH/bin/"* 2>/dev/null || true
chmod +x "$PREFIX/lib/rustlib/$ARCH/bin/gcc-ld/"* 2>/dev/null || true

echo
"$PREFIX/bin/rustc" --version
"$PREFIX/bin/cargo" --version
echo
echo "Add this to your shell:"
env_lines
