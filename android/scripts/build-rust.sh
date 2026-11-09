#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
abi="${1:-arm64-v8a}"
version=1.85.1
if ! rustup run "$version" rustc --version >/dev/null 2>&1; then
  rustup toolchain install "$version" --profile minimal
fi
cargo +"$version" test --locked --manifest-path rust-core/Cargo.toml
cargo +"$version" build --locked --release --manifest-path rust-core/Cargo.toml
sdk="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
test -n "$sdk" || { echo 'Android SDK required'; exit 1; }
ndk="$sdk/ndk/27.2.12479018"
if [[ ! -d "$ndk" ]]; then "$sdk/cmdline-tools/latest/bin/sdkmanager" 'ndk;27.2.12479018'; fi
case "$abi" in
  arm64-v8a) target=aarch64-linux-android; compiler=aarch64-linux-android26-clang ;;
  x86_64) target=x86_64-linux-android; compiler=x86_64-linux-android26-clang ;;
  *) echo "Unsupported ABI: $abi"; exit 1 ;;
esac
rustup target add --toolchain "$version" "$target"
linker="$ndk/toolchains/llvm/prebuilt/linux-x86_64/bin/$compiler"
test -x "$linker"
export RUSTFLAGS="-C linker=$linker -C link-arg=-Wl,-z,max-page-size=16384"
cargo +"$version" build --locked --release --manifest-path rust-core/Cargo.toml --target "$target"
mkdir -p "app/src/main/jniLibs/$abi"
cp "rust-core/target/$target/release/libcontinuum_core.so" "app/src/main/jniLibs/$abi/"
