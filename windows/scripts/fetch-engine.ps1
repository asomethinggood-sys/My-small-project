param([string]$Architecture = 'x64', [string]$Destination = 'engine')
$ErrorActionPreference = 'Stop'
$assets = @{
    x64 = @('Xray-windows-64.zip', '2e04a9995a6f2ad1b28c0bb25c708ecb2695e43a1c9c7889c4b6ac2b48cf7a6a')
    arm64 = @('Xray-windows-arm64-v8a.zip', 'db062e8a177facacc8ae53d4c9c0df4132b13fc3a89acda6f21d92d36633077e')
}
if (!$assets.ContainsKey($Architecture)) { throw 'Unsupported architecture' }
$asset = $assets[$Architecture]
$temp = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Force $temp, $Destination | Out-Null
try {
    Invoke-WebRequest "https://github.com/XTLS/Xray-core/releases/download/v26.10.31/$($asset[0])" -OutFile "$temp/core.zip"
    if ((Get-FileHash "$temp/core.zip" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $asset[1]) { throw 'Engine archive checksum mismatch' }
    Expand-Archive "$temp/core.zip" "$temp/core"
    foreach ($file in @('xray.exe','wintun.dll','LICENSE','LICENSE-Wintun')) {
        if (!(Test-Path "$temp/core/$file")) { throw "Engine asset missing: $file" }
        Copy-Item "$temp/core/$file" $Destination -Force
    }
    $signature = Get-AuthenticodeSignature (Join-Path $Destination 'wintun.dll')
    if ($signature.Status -ne 'Valid') { throw 'Wintun signature verification failed' }
} finally { Remove-Item $temp -Recurse -Force }
