#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p app/libs third-party
curl -fL --retry 3 --connect-timeout 15 --max-time 240 \
  https://github.com/2dust/AndroidLibXrayLite/releases/download/v26.10.31/libv2ray.aar -o app/libs/libv2ray.aar
printf '%s\n' '2efdf731b1ed624eb1cb0d5a4d0aa95c0672e89f9702226d1ba2dc90308630b6  app/libs/libv2ray.aar' | sha256sum -c -
curl -fL --retry 3 --connect-timeout 15 --max-time 120 \
  https://github.com/2dust/AndroidLibXrayLite/releases/download/v26.10.31/libv2ray-sources.jar -o third-party/libv2ray-sources.jar
printf '%s\n' 'c6d5eda3d69739c7cdfa177f607b5549b6764062ed2ee9a65c600c2fc26e8ccf  third-party/libv2ray-sources.jar' | sha256sum -c -
