param([string]$AppDirectory = 'package-x64', [switch]$NativeApp)
$ErrorActionPreference = 'Stop'
$core = (Resolve-Path "$AppDirectory/engine/xray.exe").Path
$fixture = $null; $server = $null; $client = $null; $app = $null
function Wait-TestTunnel($child) {
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($child.HasExited) { throw 'Test tunnel process exited before readiness' }
        $marker = & curl.exe --noproxy '*' --silent --max-time 2 http://198.18.0.10:23080/
        if ($LASTEXITCODE -eq 0 -and $marker -eq 'continuum-windows-route-fixture') { return }
        Start-Sleep 1
    }
    throw 'Test tunnel did not pass its actual route readiness check'
}
try {
    if ($NativeApp) { & "$AppDirectory/validate.exe" } else { dotnet run --project windows/Tests/Tests.csproj -c Release -- --write-fixture }
    if ($LASTEXITCODE -ne 0) { throw 'Fixture generation failed' }
    & $core run -test -config fixture/full-tun.json
    if ($LASTEXITCODE -ne 0) { throw 'Full TUN configuration rejected by pinned engine' }
    $config = @{
        log = @{loglevel='debug'; error='fixture/server-detail.log'}
        inbounds = @(@{listen='127.0.0.1';port=23081;protocol='shadowsocks';settings=@{method='aes-128-gcm';password='continuum-ci-only-password';network='tcp,udp'}})
        # Local fixture only: permit exactly the owned echo service, not general private-network access.
        outbounds = @(
            @{tag='internet';protocol='freedom';settings=@{targetStrategy='UseIPv4'}},
            @{tag='fixture';protocol='freedom';settings=@{redirect='127.0.0.1:23080';finalRules=@(@{action='allow';network='tcp,udp';ip=@('127.0.0.1/32');port='23080'})}}
        )
        routing = @{rules=@(@{type='field';ip=@('198.18.0.10/32');port='23080';outboundTag='fixture'})}
    }
    $config | ConvertTo-Json -Depth 15 | Set-Content fixture/server.json
    $fixture = Start-Process python -ArgumentList 'windows/scripts/fixture.py' -PassThru -WindowStyle Hidden
    $server = Start-Process $core -ArgumentList 'run -config fixture/server.json' -PassThru -WindowStyle Hidden -RedirectStandardError fixture/server.log
    Start-Sleep 2
    if ($fixture.HasExited -or $server.HasExited) { throw 'Local fixture process failed to start' }
    $direct = & curl.exe --noproxy '*' --silent --max-time 3 http://127.0.0.1:23080/
    if ($LASTEXITCODE -ne 0 -or $direct -ne 'continuum-windows-route-fixture') { throw 'Local HTTP fixture is not ready' }
    New-Item -ItemType Directory -Force windows/Tests/bin/Release/net8.0-windows/engine | Out-Null
    Copy-Item "$AppDirectory/engine/*" windows/Tests/bin/Release/net8.0-windows/engine -Force
    if ($NativeApp) { & "$AppDirectory/validate.exe" --lifecycle 2>&1 | Tee-Object -Variable lifecycleLog }
    else { dotnet run --project windows/Tests/Tests.csproj -c Release --no-build -- --engine-lifecycle 2>&1 | Tee-Object -Variable lifecycleLog }
    if ($LASTEXITCODE -ne 0) {
        $detail = (($lifecycleLog | Select-Object -Last 18) -join "`n").Replace('%','%25').Replace("`r",'%0D').Replace("`n",'%0A')
        Write-Output "::error title=Local engine lifecycle diagnostics::$detail"
        throw 'App engine lifecycle test failed'
    }
    $client = Start-Process $core -ArgumentList 'run -config fixture/legacy-dns-tun.json' -PassThru -WindowStyle Hidden -RedirectStandardError fixture/legacy.log
    Wait-TestTunnel $client
    python windows/scripts/network-check.py --baseline-drop
    if ($LASTEXITCODE -ne 0) { throw 'Legacy DNS reproduction failed' }
    Stop-Process -Id $client.Id -Force; $client.WaitForExit(); $client = $null
    Start-Sleep 2
    $client = Start-Process $core -ArgumentList 'run -config fixture/scoped-tun.json' -PassThru -WindowStyle Hidden -RedirectStandardError fixture/client.log
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep 1
        if ($client.HasExited) { Get-Content fixture/client.log; throw 'TUN engine exited' }
        $body = & curl.exe --noproxy '*' --silent --max-time 2 http://198.18.0.10:23080/
        if ($LASTEXITCODE -eq 0 -and $body -eq 'continuum-windows-route-fixture') { $ready = $true; break }
    }
    if (!$ready) { Get-Content fixture/client.log; throw 'Scoped TUN did not route HTTP through Shadowsocks' }
    python -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.settimeout(8);data=b'continuum-udp-fixture'*60;s.sendto(data,('198.18.0.10',23080));result,peer=s.recvfrom(4096);assert result==data"
    if ($LASTEXITCODE -ne 0) { throw 'Scoped TUN UDP echo failed' }
    Write-Output 'PASS Actual Windows TUN HTTP marker and UDP echo through local Shadowsocks peer'
    python windows/scripts/network-check.py
    if ($LASTEXITCODE -ne 0) { throw 'TUN DNS and byte-verified transfers failed' }
    if ($NativeApp) {
        python windows/scripts/session-check.py
        if ($LASTEXITCODE -ne 0) { throw 'Long-lived UDP/media regression failed' }
    }
    & curl.exe --silent --fail --noproxy '' --proxy http://127.0.0.1:23082 --max-time 15 --output NUL https://example.com/
    if ($LASTEXITCODE -ne 0) { throw 'Certificate-verified public HTTPS through test peer failed' }
    Stop-Process -Id $client.Id -Force; $client.WaitForExit(); $client = $null
    Start-Sleep 2
    if (Get-NetRoute -DestinationPrefix '198.18.0.0/15' -ErrorAction SilentlyContinue) { throw 'Fixture tunnel route remained after engine exit' }
    Write-Output 'PASS Scoped tunnel route removed on process exit'
    $client = Start-Process $core -ArgumentList 'run -config fixture/fallback-tun.json' -PassThru -WindowStyle Hidden -RedirectStandardError fixture/fallback.log
    Wait-TestTunnel $client
    python windows/scripts/network-check.py --dns-only
    if ($LASTEXITCODE -ne 0) { throw 'Secondary DoH did not recover from unreachable primary' }
    Stop-Process -Id $client.Id -Force; $client.WaitForExit(); $client = $null
    Start-Sleep 2
    if (Get-NetRoute -DestinationPrefix '198.18.0.0/15' -ErrorAction SilentlyContinue) { throw 'Fallback test left a route behind' }
    $exe = (Resolve-Path "$AppDirectory/Continuum.exe").Path
    $app = Start-Process $exe -PassThru
    if (!$app.WaitForInputIdle(20000)) { throw 'Desktop window did not become idle' }
    Start-Sleep 3
    $app.Refresh()
    if ($app.HasExited -or $app.MainWindowTitle -ne 'Continuum') { throw 'Continuum desktop launch failed' }
    Add-Type -AssemblyName System.Drawing,System.Windows.Forms
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap $screen.Width,$screen.Height
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screen.Location,[System.Drawing.Point]::Empty,$screen.Size)
    $bitmap.Save((Join-Path (Get-Location) 'windows-desktop.png'))
    $graphics.Dispose(); $bitmap.Dispose()
    $app.CloseMainWindow() | Out-Null
    if (!$app.WaitForExit(10000)) { throw 'Desktop did not close cleanly' }
    Write-Output 'PASS Packaged WPF desktop launch and clean close'
} catch {
    $detail = ($_.ToString() + ' at ' + $_.ScriptStackTrace).Replace('%','%25').Replace("`r",'%0D').Replace("`n",'%0A')
    Write-Output "::error title=Windows smoke failure::$detail"
    foreach ($log in @('fixture/client.log','fixture/server.log','fixture/server-detail.log','fixture/legacy.log','fixture/tun-detail.log','fixture/fallback.log')) {
        if (Test-Path $log) {
            $tail = ((Get-Content $log -Tail 18) -join "`n").Replace('%','%25').Replace("`r",'%0D').Replace("`n",'%0A')
            Write-Output "::notice title=Local fixture engine diagnostics::$log $tail"
        }
    }
    throw
} finally {
    foreach ($p in @($app,$client,$server,$fixture)) { if ($null -ne $p -and !$p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
}
