# rotate_token.ps1 — single-source token rotation (run on the FAR machine)
# Regenerates HERMES_DASHBOARD_SESSION_TOKEN, restarts serve with the new env,
# pushes the new token to the bridge host over SSH stdin (secret never on screen).
# Requires: the reverse-tunnel ssh key already trusted by the bridge host.

$envFile = "C:\Users\<user>\AppData\Local\hermes\.env"
$vpsTarget = "root@your-vps.example.com"
$vpsEnvFile = "/root/.hermes/.env"          # where the bridge host keeps its copy

$newTok = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 64 | ForEach-Object {[char]$_})

(Get-Content $envFile) -replace '^HERMES_DASHBOARD_SESSION_TOKEN=.*$',("HERMES_DASHBOARD_SESSION_TOKEN=" + $newTok) |
    Set-Content $envFile

Get-Process hermes -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 5
Start-Process "$env:LOCALAPPDATA\Hermes\bin\hermes.exe" `
    -ArgumentList 'serve','--port','27183','--host','127.0.0.1','--skip-build' -WindowStyle Hidden
Start-Sleep 20

# Push via stdin over the authenticated channel; remote side rewrites its .env keeping one token line.
$newTok | ssh $vpsTarget "cat > /tmp/newtoken && python3 -c `"import os;p=open('/tmp/newtoken').read().strip();os.remove('/tmp/newtoken');f=open('$vpsEnvFile');ls=[l for l in f if not l.startswith('HERMES_DASHBOARD_SESSION_TOKEN=')];f.close();f=open('$vpsEnvFile','w');f.writelines(ls+['HERMES_DASHBOARD_SESSION_TOKEN='+p+chr(10)]);f.close()`""

Write-Output "ROTATED_AND_SYNCED"
