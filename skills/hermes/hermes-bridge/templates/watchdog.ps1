# watchdog.ps1 — far-side self-healing loop (Windows)
# 60s cycle: heal serve (port check), recycle on stale-token 401, restart tunnel with backoff.
# Launch at login via Startup-folder VBS:
#   Set shell = CreateObject("WScript.Shell")
#   shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\<path>\watchdog.ps1", 0, False
# Instance values to adjust: $envFile path, hermes.exe path, ssh target host.

$envFile = "C:\Users\<user>\AppData\Local\hermes\.env"
$hermes  = "$env:LOCALAPPDATA\Hermes\bin\hermes.exe"
$ssh     = "C:\Windows\System32\OpenSSH\ssh.exe"
$hostUri = "root@your-vps.example.com"

$token = (Select-String -Path $envFile -Pattern '^HERMES_DASHBOARD_SESSION_TOKEN=(.+)$').Matches.Groups[1].Value
$backoff = 0
while ($true) {
    # --- serve: start only if port closed (prevents duplicate processes) ---
    $portOpen = (Test-NetConnection -ComputerName 127.0.0.1 -Port 27183 -InformationLevel Quiet -WarningAction SilentlyContinue)
    if (-not $portOpen) {
        Start-Process $hermes -ArgumentList 'serve','--port','27183','--host','127.0.0.1','--skip-build' -WindowStyle Hidden
        Start-Sleep 20
    }

    # --- stale-token detection: authed probe must not 401; if it does, serve lost its env ---
    try {
        Invoke-WebRequest -Uri 'http://127.0.0.1:27183/api/config' `
            -Headers @{ 'X-Hermes-Session-Token' = $token } -UseBasicParsing -TimeoutSec 10 | Out-Null
    } catch {
        if ($_.Exception.Response.StatusCode.value__ -eq 401) {
            Get-Process hermes -ErrorAction SilentlyContinue | Stop-Process -Force
            Start-Sleep 5
            continue
        }
    }

    # --- tunnel: exactly one matching process; exponential backoff caps at 15 min ---
    # (backoff protects against fail2ban bans when the VPS is unreachable for a while)
    $tunnel = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" |
              Where-Object { $_.CommandLine -match '27183:127\.0\.0\.1:27183' }
    if (-not $tunnel) {
        Start-Sleep ([Math]::Min(60 * [Math]::Pow(2, $backoff), 900))
        Start-Process $ssh -ArgumentList '-R','27183:127.0.0.1:27183','-N','-T',
            '-o','BatchMode=yes','-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3',
            '-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=15',$hostUri -WindowStyle Hidden
        $backoff = [Math]::Min($backoff + 1, 4)
    } else { $backoff = 0 }

    Start-Sleep 60
}
