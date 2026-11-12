param([string]$AppDirectory = 'package-x64')
$ErrorActionPreference = 'Stop'
$core = (Resolve-Path "$AppDirectory/engine/xray.exe").Path
$fixture = $null; $server = $null; $client = $null; $app = $null
try {
    dotnet run --project windows/Tests/Tests.csproj -c Release -- --write-fixture
    if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed' }
    & $core run -test -config fixture/full-tun.json
    if ($LASTEXITCODE -ne 0) { throw 'Full TUN configuration rejected by pinned engine' }
    $config = @{
        log = @{loglevel='debug'; error='fixture/server-detail.log'}
        inbounds = @(@{listen='127.0.0.1';port=23081;protocol='shadowsocks';settings=@{method='aes-128-gcm';password='continuum-ci-only-password';network='tcp,udp'}})
        outbounds = @(@{protocol='freedom';settings=@{redirect='127.0.0.1:23080'}})
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
    dotnet run --project windows/Tests/Tests.csproj -c Release --no-build -- --engine-lifecycle 2>&1 | Tee-Object -Variable lifecycleLog
    if ($LASTEXITCODE -ne 0) {
        $detail = (($lifecycleLog | Select-Object -Last 18) -join "`n").Replace('%','%25').Replace("`r",'%0D').Replace("`n",'%0A')
        Write-Output "::error title=Local engine lifecycle diagnostics::$detail"
        throw 'App engine lifecycle test failed'
    }
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
    Stop-Process -Id $client.Id -Force; $client.WaitForExit(); $client = $null
    Start-Sleep 2
    if (Get-NetRoute -DestinationPrefix '198.18.0.0/15' -ErrorAction SilentlyContinue) { throw 'Fixture tunnel route remained after engine exit' }
    Write-Output 'PASS Scoped tunnel route removed on process exit'
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
    foreach ($log in @('fixture/client.log','fixture/server.log','fixture/server-detail.log')) {
        if (Test-Path $log) {
            $tail = ((Get-Content $log -Tail 18) -join "`n").Replace('%','%25').Replace("`r",'%0D').Replace("`n",'%0A')
            Write-Output "::notice title=Local fixture engine diagnostics::$log $tail"
        }
    }
    throw
} finally {
    foreach ($p in @($app,$client,$server,$fixture)) { if ($null -ne $p -and !$p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } }
}
