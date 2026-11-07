# Tehran-side measurement protocol

**Location requirement:** run this on a phone/computer actually in Tehran using
your ordinary ISP/mobile data. A VPS, Actions runner, VPN endpoint, remote browser
or this development sandbox elsewhere is not a Tehran client. Record location
manually; scripts do not certify geolocation. Do not publish your exact address,
public IP, full UUID/URI or raw traceroutes if you consider them sensitive.

## 1. Establish the baseline before migration

Record date/time/timezone, Tehran ISP/ASN if known, Wi-Fi vs mobile, signal quality,
v2rayNG/app-core versions, test mode, routing mode, DNS settings, test URL, number
of concurrent users and the current tunnel region. Record whether IPv4/IPv6 is
used. Save the existing profile privately. Avoid background downloads/updates.

Choose one small HTTPS URL accessible through all candidates, for example
`https://www.gstatic.com/generate_204` (availability is NOT assumed). Keep it
unchanged. Use a second independent URL to detect destination-specific effects.
A blocked test site does not by itself prove the proxy is broken. Do not pick a
large file as a latency test or silently switch URLs between profiles.

1. In v2rayNG set the delay-test URL consistently (setting names vary by version).
   Use **real delay / connection test**, not only TCP ping. Set full/global proxy
   routing so the test destination is not bypassed. Record the precise mode.
2. Test the existing US tunnel 30 times, ~1 second apart. Save individual results,
   including timeouts; do not keep only the best number. Repeat at quiet and busy
   Tehran hours on at least two days. Report median, p95 and failure percentage.
3. Repeat for direct Istanbul and Frankfurt profiles, alternating candidate order
   within each session. Keep the device, ISP, URL and conditions constant. Re-test
   each ISP separately: success on one mobile carrier does not generalize.
4. Test a normal direct connection with the VPN off as a control when the chosen
   website is reachable. This is a different route, not a proxy RTT baseline.

For reproducible HTTP timing on Android Termux or a computer on the same Tehran
network, install Python and curl (Termux: `pkg install python curl`). Copy
`scripts/measure.py` to the device. In **v2rayNG VPN mode**, include Termux in the
VPN (no per-app exclusion), choose global proxy routing, then:

```bash
mkdir -p measurements
python3 scripts/measure.py --label Tehran-ISP-US-tunnel-evening \
  --url https://www.gstatic.com/generate_204 --count 30 \
  --output measurements/us-evening.csv
# Switch profile, connect, and rerun with a NEW label/output for each candidate.
```

Alternatively, with a local Xray/v2rayNG SOCKS listener reachable on that same
device, add `--proxy socks5h://127.0.0.1:10808` (check the actual port). This is a
**client-device** localhost address, not the VPS or sandbox. Do not expose SOCKS
to the LAN. Confirm via logs or an IP-check destination that traffic is actually
using the candidate VPS; an accidental routing bypass invalidates the comparison.

Each curl invocation is a fresh connection: the script reports **cold HTTP total**,
TTFB, cumulative DNS/TCP/TLS times, bytes and errors. It does not measure raw RTT
or the same cache/connection reuse behavior as every v2rayNG version. With SOCKS,
`connect_s` refers to the local SOCKS listener, NOT the remote proxy. The script
records non-2xx responses/timeouts as failures, and reports successful-sample
median/p95 separately. Timeouts are not zero latency and must not be hidden by
reporting only successful-sample stats. CSV files are ignored by Git by default.

## 2. Diagnose route versus application delay

From the Tehran machine with VPN **off**, using a provider-authorized test IP:

```bash
ping -c 30 VPS_IP
mtr --tcp --port 443 --report --report-cycles 30 VPS_IP
```

Install `mtr` if needed; some systems need elevated privileges. Probe only servers
you own or have permission to test. ICMP may be blocked or deprioritized. Ignore
intermediate-hop loss if it does not persist at the destination. Repeat with VPN
on only if intentionally testing a different route and label it accordingly.
Pinging a `trycloudflare.com` host measures the edge, not the US origin. Lack of
an MTR reply is not proof of a dead VLESS service. Provider looking glasses are
useful for candidate selection but are not Tehran-to-server measurements.

Measure downloads separately: use the same permitted test file of known size,
with a bounded transfer (e.g. curl `--max-time 30`) through each profile. Record
bytes, seconds, Mbps (= bytes * 8 / seconds / 1,000,000), failures and transfer
quota. Never compare file-download duration with proxy ping. Test under shared
load separately from idle tests.

## 3. Decide and report honestly

Define the requested metric **before** accepting the target. Recommended user-
visible criterion: same v2rayNG real-delay mode and URL, successful-sample median
**<200 ms**, p95 also **<200 ms**, and <1% failures across at least 100 samples per
candidate spread over busy and quiet periods. Thirty samples per initial session
are screening, not a reliability guarantee. Report both median and p95 even if
only one passes. If only TCP RTT passes, say so; do not claim that real-delay or
web load time is under 200 ms. Never subtract handshake time just to hit the goal.

| Location / ISP / time | Profile / region | Mode / URL | Samples | Median ms | p95 ms | Fail % |
|---|---|---|---:|---:|---:|---:|
| Tehran / fill in | Original US tunnel | fill in | — | — | — | — |
| Tehran / fill in | Istanbul direct | identical | — | — | — | — |
| Tehran / fill in | Frankfurt direct | identical | — | — | — | — |

No rows have been measured yet. If results fail, try a different provider/peering
route, not just another VM with the same upstream. If direct access is blocked,
trial a named tunnel to the **nearby VPS** separately; it may improve reachability
but may worsen latency. Do not enable a US fallback and call that an improvement.
