# Bulletproof VPS ↔ Local Hermes Link Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make the VPS→Windows-Hermes communication link self-healing, monitored, and diagnosable so a single failure (reboot, sleep, token drift, fail2ban ban, dead tunnel) never silently breaks it again.

**Architecture:** Three independent safety nets around the same working chain (Windows `hermes serve` + `ssh -R` tunnel → VPS `127.0.0.1:27183`): (1) a hardened Windows watchdog that heals processes *and* token drift, (2) a VPS cron watchdog that detects breakage within minutes and alerts Telegram (silent on success), (3) a layered `doctor` diagnostic that pinpoints exactly which layer broke. Plus a runbook skill so future sessions never re-debug from scratch.

**Tech Stack:** PowerShell watchdog (Windows), Python websockets client (VPS), fail2ban `ignoreip`, Hermes cronjob scheduler (`no_agent` watchdog pattern), `hermes send -t telegram` alerts.

---

## Current State (verified this session)

| Component | Path / Command | Status |
|---|---|---|
| Local binary | `C:\Users\pheme\AppData\Local\Hermes\bin\hermes.exe` v0.20.5 | ✅ |
| Serve | `hermes serve --port 27183 --host 127.0.0.1 --skip-build` | ✅ running |
| Reverse tunnel | `ssh -R 27183:127.0.0.1:27183 root@102.208.217.192 -o ServerAliveInterval=30 -o ExitOnForwardFailure=yes -N -T` | ✅ established |
| Token (canonical) | `HERMES_DASHBOARD_SESSION_TOKEN=` in `C:\Users\pheme\AppData\Local\hermes\.env` | ✅ pinned |
| Token (copy) | `/root/.hermes/.env` on VPS | ✅ synced |
| Chat client | `/root/local_hermes_chat.py`, wrapper `/usr/local/bin/local-hermes` | ✅ verified (PONG/ACK tests passed) |
| Gateway | Startup-folder `Hermes_Gateway.vbs`, auto-starts at login | ✅ |
| Watchdog | Startup-folder script (name unverified) | ⚠️ never kill-tested |
| Chat protocol | `ws://127.0.0.1:27183/api/ws?token=<token>` → JSON-RPC `session.create {}` → `prompt.submit {session_id, text}` → `message.complete` event carries reply text | verified |

## Failure Modes Observed Today (what "bulletproof" must cover)

1. **Tunnel process died silently** (pid dead, no socket) — discovered only when used.
2. **Serve claimed running but wasn't** — status said down; had to be restarted.
3. **fail2ban banned the Windows IP** after rapid SSH retry bursts → ping worked, port 22 timed out, ~10 min outage.
4. **Token drift risk**: if serve ever restarts WITHOUT `.env` loaded, it mints a fresh random token → VPS copy goes stale → all authed calls 401. Two copies of one secret = DRY violation needing a sync procedure.
5. **Reboot/login gap**: Startup items only run at user login. After a reboot to a locked screen, nothing starts (Scheduled Task fallback happened because admin/UAC was unavailable).
6. **No monitoring**: every failure today was discovered by trying to use the link.
7. **Provider 401s** (opencode-zen key) — separate axis: transport can be perfect while the local agent itself can't answer.

---

### Task 1: Verify and harden the Windows watchdog

**Objective:** Prove the existing watchdog actually heals failures, and upgrade it to also detect stale tokens and prevent duplicate processes.

**Files:**
- Modify: `C:\Users\pheme\AppData\Local\hermes\watchdog\hermes_watchdog.ps1` (ask local agent for its actual current script path first)
- Create: `C:\Users\pheme\AppData\Local\hermes\watchdog\link_health.log`

**Step 1: Ask the local agent for the exact watchdog script path and content** (it created a Startup entry whose real name/path we never saw).

**Step 2: Kill-tests (run via local agent):**
```powershell
# kill serve → expect watchdog to restore within ~90s
Stop-Process -Name hermes -Force
# kill ssh tunnel → expect restore within ~90s
Get-Process ssh | Stop-Process -Force
```
Verify each time: `Test-NetResult 127.0.0.1 -Port 27183` succeeds and VPS `curl -s http://127.0.0.1:27183/api/health` returns `{"ok":true,...}`.

**Step 3: Harden the watchdog loop** — required properties in final script:

```powershell
# Core loop (complete replacement skeleton)
$envFile = "C:\Users\pheme\AppData\Local\hermes\.env"
$token = (Select-String -Path $envFile -Pattern '^HERMES_DASHBOARD_SESSION_TOKEN=(.+)$').Matches.Groups[1].Value
$backoff = 0
while ($true) {
  # --- serve: start ONLY if port closed (prevents duplicates) ---
  $portOpen = Test-NetConnection -ComputerName 127.0.0.1 -Port 27183 -InformationLevel Quiet -WarningAction SilentlyContinue
  if (-not $portOpen) {
    Start-Process -FilePath "$env:LOCALAPPDATA\Hermes\bin\hermes.exe" `
      -ArgumentList 'serve','--port','27183','--host','127.0.0.1','--skip-build' `
      -WindowStyle Hidden
    Start-Sleep 20
  }
  # --- stale-token check: authed call must not 401 ---
  try {
    $h = @{ 'X-Hermes-Session-Token' = $token }
    $r = Invoke-WebRequest -Uri 'http://127.0.0.1:27183/api/config' -Headers $h -UseBasicParsing -TimeoutSec 10
  } catch {
    if ($_.Exception.Response.StatusCode.value__ -eq 401) {
      # serve lost its token (restarted without env) -> recycle it; .env is canonical
      Get-Process hermes -ErrorAction SilentlyContinue | Stop-Process -Force
      Start-Sleep 5
      continue
    }
  }
  # --- tunnel: exactly one ssh with our marker; exponential backoff on repeated fails ---
  $tunnel = Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" |
            Where-Object CommandLine -match '27183:127\.0\.0\.1:27183'
  if (-not $tunnel) {
    Start-Sleep ([Math]::Min(60 * [Math]::Pow(2, $backoff), 900))  # 60s..15min backoff (fail2ban safety)
    Start-Process -FilePath 'C:\Windows\System32\OpenSSH\ssh.exe' `
      -ArgumentList '-R','27183:127.0.0.1:27183','-N','-T','-o','BatchMode=yes',`
                    '-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3',`
                    '-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=15',`
                    'root@102.208.217.192' -WindowStyle Hidden
    $backoff++
  } else { $backoff = 0 }
  Start-Sleep 60
}
```

**Step 4: Verify from VPS after each kill-test:**
Run: `python3 /root/local_hermes_chat.py "reply ACK"` — Expected: reply containing `ACK` within 2 min of the kill.

**Step 5: Commit** (if watchdog lives in a synced repo; otherwise skip — Windows side isn't git-managed).

---

### Task 2: Single-source-of-truth token rotation script (Windows side)

**Objective:** One command that rotates the token and guarantees the VPS copy matches — eliminating failure mode #4 permanently.

**Files:**
- Create: `C:\Users\pheme\AppData\Local\hermes\watchdog\rotate_token.ps1`

**Step 1: Write the script**

```powershell
# rotate_token.ps1 — regenerate token, restart serve with it, push to VPS
$envFile = "C:\Users\pheme\AppData\Local\hermes\.env"
$newTok = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 64 | % {[char]$_})
(Get-Content $envFile) -replace '^HERMES_DASHBOARD_SESSION_TOKEN=.*$',"HERMES_DASHBOARD_SESSION_TOKEN=$newTok" |
  Set-Content $envFile
Get-Process hermes -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 5
Start-Process "$env:LOCALAPPDATA\Hermes\bin\hermes.exe" `
  -ArgumentList 'serve','--port','27183','--host','127.0.0.1','--skip-build' -WindowStyle Hidden
Start-Sleep 20
# push over the existing authenticated SSH channel (token never on screen)
$newTok | ssh root@102.208.217.192 "python3 -c 'import sys;p=sys.stdin.read().strip();f=open(\"/root/.hermes/.env\");ls=[l for l in f if not l.startswith(\"HERMES_DASHBOARD_SESSION_TOKEN=\")];f.close();f=open(\"/root/.hermes/.env\",\"w\");f.writelines(ls+[\"HERMES_DASHBOARD_SESSION_TOKEN=\"+p+chr(10)]);f.close()'"
Write-Host "ROTATED_AND_SYNCED"
```

**Step 2: Verify from VPS**
Run: `python3 /root/local_hermes_chat.py "reply ACK"` — Expected: `ACK` (proves new token works end-to-end).
Then confirm old token is gone: `grep -c HERMES_DASHBOARD_SESSION_TOKEN /root/.hermes/.env` → `1` exactly.

**Step 3:** Have the local agent run this once as a live drill.

---

### Task 3: VPS-side layered doctor script

**Objective:** One command that identifies exactly which of the 5 layers is broken, with the matching fix printed.

**Files:**
- Create: `/root/local_hermes_doctor.py`

**Step 1: Write failing test first** — run before script exists:
Run: `python3 /root/local_hermes_doctor.py` — Expected: FAIL (file not found).

**Step 2: Write the script**

```python
#!/usr/bin/env python3
"""Layered diagnosis of the VPS->local Hermes link. Exit 0 = all green."""
import socket, sys, urllib.request

TOKEN = None
for line in open('/root/.hermes/.env'):
    if line.startswith('HERMES_DASHBOARD_SESSION_TOKEN='):
        TOKEN = line.strip().split('=', 1)[1]

results = []
def check(name, fn, fix):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, str(e)[:80]
    results.append((name, ok, detail, fix))

def tcp():
    s = socket.create_connection(('127.0.0.1', 27183), timeout=4); s.close()
    return True, 'connected'
def health():
    r = urllib.request.urlopen('http://127.0.0.1:27183/api/health', timeout=8)
    d = __import__('json').loads(r.read())
    return d.get('ok') is True, f"ok={d.get('ok')} version={d.get('version')}"
def auth():
    req = urllib.request.Request('http://127.0.0.1:27183/api/config',
                                 headers={'X-Hermes-Session-Token': TOKEN})
    urllib.request.urlopen(req, timeout=8)
    return True, 'token accepted'

check('1. token in /root/.hermes/.env', lambda: (TOKEN is not None and len(TOKEN) >= 32,
      f'{len(TOKEN) if TOKEN else 0} chars'),
      'FIX: re-run rotate_token.ps1 on Windows')
check('2. tunnel+serve TCP 127.0.0.1:27183', tcp,
      'FIX: Windows-side down. Check watchdog running / serve+tunnel processes on Phemelo.')
check('3. GET /api/health (unauthed)', health,
      'FIX: TCP open but HTTP dead — serve wedged; recycle hermes.exe on Windows.')
check('4. authed GET /api/config', auth,
      'FIX: 401 = TOKEN DRIFT. Re-run rotate_token.ps1 on Windows (syncs both sides).')

fails = [r for r in results if not r[1]]
for name, ok, detail, fix in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name:38s} {detail}")
    if not ok:
        print(f"      -> {fix}")
print('\nLINK HEALTHY' if not fails else f'\n{len(fails)} LAYER(S) DOWN')
sys.exit(0 if not fails else 1)
```

**Step 3: Run it**
Run: `python3 /root/local_hermes_doctor.py`
Expected: all four `PASS`, `LINK HEALTHY`, exit 0.

**Step 4: Negative test** — ask local agent to stop serve briefly; re-run doctor.
Expected: layer 2 FAIL with its FIX line; other layers short-circuit gracefully. Restore after.

---

### Task 4: VPS cron watchdog with Telegram alert (silent-on-success)

**Objective:** Detect any link breakage within 15 minutes and alert automatically; stay completely silent when healthy.

**Files:**
- Create: `~/.hermes/scripts/link_watchdog.py`

**Step 1: Write the script** (imports doctor logic; prints NOTHING when healthy — the no_agent watchdog contract):

```python
#!/usr/bin/env python3
"""Silent-on-success link watchdog. Non-empty stdout = alert."""
import subprocess, sys, socket
# quick gate: if TCP is down, say which layer before running full doctor
try:
    s = socket.create_connection(('127.0.0.1', 27183), timeout=4); s.close()
except Exception:
    print("🔴 VPS↔local Hermes link DOWN: TCP 127.0.0.1:27183 unreachable "
          "(tunnel or Windows serve dead — watchdog should self-heal; "
          "run `python3 /root/local_hermes_doctor.py` if it persists >15 min)")
    sys.exit(0)
r = subprocess.run([sys.executable, '/root/local_hermes_doctor.py'],
                   capture_output=True, text=True, timeout=60)
if r.returncode != 0:
    print("🔴 VPS↔local Hermes link DEGRADED:\n" + r.stdout)
sys.exit(0)
```

**Step 2: Register the cron job** (via Hermes `cronjob` tool at execution time):

```
action=create
name=local-hermes-link-watchdog
schedule=15m
script=~/.hermes/scripts/link_watchdog.py
no_agent=true
deliver=origin
```

**Step 3: Verify both paths**
- Healthy: wait 2 ticks, confirm NO message delivered.
- Break: ask local agent to stop serve for >15 min, confirm 🔴 alert arrives on Telegram; restore, confirm next tick is silent.

---

### Task 5: fail2ban + sshd hardening (prevent failure mode #3)

**Objective:** The Windows box must never get banned by its own watchdog, and sshd must be boot-persistent.

**Step 1: Check current jail tuning**
Run: `fail2ban-client get sshd maxretry; fail2ban-client get sshd findtime`
Expected: values that a 60s-cadence watchdog can never trip.

**Step 2: Whitelist + tune** — edit `/etc/fail2ban/jail.local` `[sshd]` section:
```ini
ignoreip = 127.0.0.1/8 <WINDOWS_PUBLIC_IP>
maxretry = 10
findtime = 10m
bantime  = 30m
```
Note: Windows public IP is dynamic (ISP NAT). The exponential-backoff watchdog (Task 1) is the primary protection; `ignoreip` is defense-in-depth. Add a comment in the file to refresh the IP if it changes.

**Step 3: Apply and verify**
Run: `systemctl reload fail2ban && fail2ban-client get sshd ignoreip`
Expected: whitelist shown.

**Step 4: Boot persistence**
Run: `systemctl is-enabled ssh`
Expected: `enabled`. If not: `systemctl enable ssh`.

---

### Task 6: Reboot/login gap — decide and document

**Objective:** Close failure mode #5 honestly: either eliminate it or make it a documented known-limitation.

**Decision point (needs user input during execution):**
- **Option A (recommended):** Enable Windows auto-login (`netplwiz`, password stored locally). Startup items then run at boot with zero interaction. Trade-off: anyone at the physical machine gets the desktop — acceptable for a personal box, user's call.
- **Option B:** Accept it: after a reboot-to-lock-screen the link waits for first login; the VPS cron watchdog (Task 4) tells the user immediately, so it degrades into a notification instead of a mystery.

**Step 1:** Ask user A vs B. If A: local agent runs `netplwiz` config steps.
**Step 2:** Either way, do one real reboot drill: reboot Windows, measure time-from-login to `LINK HEALTHY` on doctor. Record result in runbook.

---

### Task 7: Runbook skill so future sessions never re-derive any of this

**Objective:** Persist today's hard-won knowledge as a skill (paths, protocol, failure playbook) — the meta-fix for how this session went.

**Files:**
- Create: `~/.hermes/skills/local-hermes-link/SKILL.md`

**Step 1: Write SKILL.md** covering (content already fully established this session):
- Trigger: any task involving the local Windows Hermes agent / the tunnel / "talk to my PC"
- The chain diagram + every exact path/command from the Current State table
- Protocol recipe: WS connect `?token=` → `session.create` → `prompt.submit {session_id,text}` → collect `message.complete`
- Usage: `local-hermes "<msg>"` / `python3 /root/local_hermes_chat.py --session <id> "<msg>"`
- Diagnosis ladder: `doctor` → per-layer FIX lines → who owns each fix (Windows watchdog auto-heals layers 2–4; user only for persistent reds)
- Account facts: account `pheme`, hostname `Phemelo` (never `phemelo`)

**Step 2: Verify**
Fresh-session test: `skill_view(name='local-hermes-link')` returns the content; a cold `local-hermes "reply ACK"` works using only the skill's instructions.

**Step 3: Commit** to `/root/hermes-profile-backup` (already git-managed + daily cron):
```bash
cd /root/hermes-profile-backup && rsync -a ~/.hermes/skills/local-hermes-link skills/ && git add skills/ && git commit -m "feat: local-hermes-link runbook skill"
```

---

### Task 8: Chaos acceptance suite (final gate)

**Objective:** Prove bulletproofness empirically before declaring done.

**Tests (each followed by `python3 /root/local_hermes_doctor.py` + one `local-hermes "reply ACK"`):**

| # | Chaos action | Expect |
|---|---|---|
| 1 | Kill `hermes.exe` on Windows | Auto-restore ≤2 min, ACK works, cron silent |
| 2 | Kill `ssh.exe` tunnel on Windows | Auto-restore ≤2 min (backoff respected), ACK works |
| 3 | Rotate token via `rotate_token.ps1` | Zero manual steps, doctor all-PASS, ACK works |
| 4 | Start a SECOND serve manually | Watchdog does NOT spawn duplicates; port conflict resolved cleanly |
| 5 | Real Windows reboot (per Task 6 choice) | Link returns after login/boot per chosen option; alert fires if >15 min |
| 6 | Normal 24h idle | Zero false-positive alerts |

**Pass criterion:** all six rows behave as specified. Any miss loops back to the owning task.

---

## Risks / Tradeoffs

- **Auto-login (Task 6A)** trades physical security for availability — explicitly user's decision.
- **Dynamic Windows IP** makes permanent fail2ban whitelisting imperfect; backoff in the watchdog is the real fix, ignoreip is best-effort.
- **Token push uses the same SSH channel it protects** — if the link is fully down during rotation, the push queues/fails; rotation should only be run when doctor shows layer ≥2 green.
- **Watchdog alert fatigue** mitigated by silent-on-success + hysteresis (only alert when a tick fails; recovery is silent).
- **hy3-free provider outages** will look identical to link death in chat-based probes — that's why doctor layer 4 uses `/api/config` (no LLM) as the auth probe, and why full PONG round-trips are reserved for explicit chaos tests.

## Open Questions

1. Task 6: auto-login (A) or accept-login-required (B)?
2. Should the cron watchdog escalate to @-mention/Discord too after 3 consecutive failed ticks, or Telegram-only is enough?
3. Does the user want `list_methods.py` retired now that `doctor` + `local-hermes` supersede it? (Recommended: yes, delete to avoid two divergent clients.)
