# local-hermes-link

Use when any task involves the local Windows Hermes agent, the VPS↔local tunnel, or "talk to my PC / local machine".

## The link (verified working 2026-08-24)

```
VPS /root/local_hermes_chat.py
  → ws://127.0.0.1:27183/api/ws?token=<HERMES_DASHBOARD_SESSION_TOKEN>   [VPS .env copy]
    → ssh -R tunnel (Windows-initiated, port 27183)
      → hermes serve --port 27183 on Windows (C:\Users\pheme\AppData\Local\Hermes\bin\hermes.exe)
        → JSON-RPC: session.create {} → prompt.submit {session_id, text} → collect message.complete event
```

## Usage from VPS

```bash
local-hermes "question"                                  # new session each time
python3 /root/local_hermes_chat.py --session <id> "msg"  # continue a session
python3 /root/local_hermes_doctor.py                     # layered health check (exit 0 = green)
```

The local agent runs tools normally (terminal, files) — treat it as a remote worker. It confirms file writes; verify critical ones yourself.

## Facts that cost a debug session once — do not re-derive

- Windows account is **pheme**, hostname **Phemelo** (never `phemelo`).
- Config/.env: `C:\Users\pheme\AppData\Local\hermes\.env` — canonical token lives here.
- Token is shared to VPS `/root/.hermes/.env`. Two copies = drift risk; rotation script syncs both.
- `/api/chat`, `/api/agent` are UI stubs in headless serve (404). Real chat = `/api/ws` WebSocket protocol above.
- Auth header for REST: `X-Hermes-Session-Token: <token>`; WS uses `?token=` query param (loopback mode).
- fail2ban here bans IPs after rapid SSH retries (ping works but port 22 times out = likely banned).
  - Unban: `fail2ban-client set sshd unbanip <ip>`; whitelist now in `/etc/fail2ban/jail.local`.
- Watchdog cron: `local-hermes-link-watchdog` (15m, silent-on-success, Telegram alert via origin).

## Diagnosis ladder

1. `python3 /root/local_hermes_doctor.py` — tells you the broken layer + fix:
   - Layer 1 FAIL → token missing on VPS: ask local agent to re-push (or run rotate_token.ps1 there).
   - Layer 2 FAIL → tunnel or serve dead on Windows: watchdog should heal ≤2 min; if persistent, ask local agent to restart both.
   - Layer 3 FAIL → serve wedged: recycle hermes.exe on Windows.
   - Layer 4 FAIL → token drift: run rotate_token.ps1 on Windows (syncs both sides atomically).
2. If doctor all-green but chat fails: provider issue on local agent (e.g. opencode-zen key) — not the link.

## Self-healing components on Windows

- Startup folder: `Hermes_Gateway.vbs` (gateway), watchdog script (serve+tunnel, 60s loop).
- `rotate_token.ps1`: regenerates token, restarts serve, pushes new token to VPS over SSH stdin.
