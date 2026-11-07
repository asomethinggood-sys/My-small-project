#!/usr/bin/env bash
# This verifies function from its execution location, NOT Tehran latency.
set -euo pipefail
umask 077
dir="$(realpath "${1:-.runtime}")"
xray="$(realpath "${2:-.runtime/bin/xray}")"
rm -f "$dir/verified-uri.txt" "$dir/verified-subscription.txt"
"$xray" run -test -c "$dir/client-test.json"
"$xray" run -c "$dir/client-test.json" > "$dir/client-test.log" 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT
sleep 2
kill -0 "$pid" # fail if another process already owns the SOCKS port
host="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["host"])' "$dir/identity.json")"
# Public certificate + endpoint readiness, without disabling verification.
[[ "$(curl --noproxy '*' -fsS --connect-timeout 10 --max-time 30 "https://$host/healthz")" == ok ]]
# SOCKS remote DNS; exit destination independently chosen from the proxy host.
# Require HTTPS 200 to avoid exporting a config after an HTTP error page.
code="$(curl --noproxy '' --proxy socks5h://127.0.0.1:10809 -sS -o /dev/null -w '%{http_code}' \
  --connect-timeout 10 --max-time 30 https://example.com/)"
[[ "$code" == 200 ]] || { echo "Proxy probe returned $code; no config exported"; exit 1; }
cp "$dir/candidate-uri.txt" "$dir/verified-uri.txt"
cp "$dir/candidate-subscription.txt" "$dir/verified-subscription.txt"
echo "Functional check passed from THIS machine (not a Tehran latency test)."
echo "Importable URI: $dir/verified-uri.txt; base64 subscription: $dir/verified-subscription.txt"
