---
name: hermes-bridge
description: Link a NAT'd Hermes agent to an always-on host via SSH.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, windows]
metadata:
  hermes:
    tags: [Hermes, Networking, Automation]
---

# Bridging a Remote Hermes Agent to Your Host

Gives one Hermes agent hands in two places: conversational + tool-execute control over a second Hermes running on a machine you cannot reach inbound (a desktop behind NAT). Works purely with ssh + the far side's own `hermes serve` — no extra daemons. Does NOT cover Hermes messaging gateways (Telegram/Discord); that is separate infrastructure.

## When to Use

- "Talk to my PC / laptop / home machine from here"
- A second Hermes exists on a NAT'd desktop and must join this workspace
- A desktop agent must be driven by cron or schedules while unattended
- An existing bridge is down and needs diagnosis or hardening

## Prerequisites

- OpenSSH **client** on the far machine (Windows 10/11 ships one in System32); an account on THIS (reachable) host
- Far machine runs Hermes v0.20+ (`hermes serve` subcommand available)
- Outbound port 22 allowed from the far network to this host
- Keys only — never type or transmit passwords through the agent; the user enters any interactive secret (e.g. Autologon GUI) personally

## How to Run

Work the Procedure below top to bottom, driving the far machine through its own Hermes agent (chat prompts) whenever you lack direct access. Invoke every snippet through the `terminal` tool. On completion, persist instance-specific facts to `memory` and the general method stays in this skill.

## Quick Reference

```bash
# far side (via its agent): pinned-token serve + reverse tunnel
hermes serve --port 27183 --host 127.0.0.1 --skip-build
ssh -R 27183:127.0.0.1:27183 -N -T -o BatchMode=yes -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes root@<THIS_HOST>

# this side: health layers + chat (scripts ship with this skill, scripts/ dir)
BRIDGE_TOKEN=<tok> python3 scripts/chat_client.py "reply ACK"
python3 scripts/bridge_doctor.py    # exit 0 = green
```

Supporting files (load on demand with `skill_view`, file_path=...):
- `scripts/chat_client.py` — conversational client (`session.create` → `prompt.submit` → `message.complete`)
- `scripts/bridge_doctor.py` — 4-layer health check, exit 0 = all green
- `templates/watchdog.ps1` — far-side self-healing loop (serve + tunnel + stale-token recycle)
- `templates/rotate_token.ps1` — one-command token rotation with atomic two-side sync

Auth surfaces on `hermes serve`: REST header `X-Hermes-Session-Token: <token>`; WebSocket `?token=` query param (loopback binds). Token env var: `HERMES_DASHBOARD_SESSION_TOKEN` — set it in `.env` BEFORE first serve start.

## Procedure

### 1. Verify far-side facts through its agent — never assume
Ask the far agent for `whoami`, hostname, `hermes.exe --version`, config/.env location. Wrong assumptions (username, install paths) cost a full debug session once; accounts and hosts rarely match documentation.

### 2. Discover the real server command
Have the far agent run `hermes serve --help`. Do NOT invent config keys to expose APIs — unrecognized keys are saved silently but bind nothing (e.g. a `remote_api:` block does nothing; only `serve` actually listens).

### 3. Choose tunnel direction by reachability
Far side behind NAT/no port-forward → REVERSE tunnel initiated from the far side to this host: `-R <port>:127.0.0.1:<port>`. This host never connects inbound to the far machine.

### 4. Establish key trust
Append the far machine's ed25519 pubkey to this host's `~/.ssh/authorized_keys` (mode 600, dir 700). If auth fails despite a valid key, suspect the USERNAME in the ssh command, not the key.

### 5. Pin the session token before first serve
Generate a 64-char random string into the far `.env` as `HERMES_DASHBOARD_SESSION_TOKEN=`. If serve starts without it, it mints a fresh ephemeral token per process — every restart silently breaks clients.

### 6. Start the stack and prove TCP through
Serve on loopback + tunnel (Quick Reference commands). From this host: TCP connect to 127.0.0.1:<port>, then `GET /api/health` expecting `{"ok":true,...}`.

### 7. Read source for the real API surface
`GET /api/chat` and `/api/agent` are web-UI stubs that 404 headless. Search the installed package (`search_files` for `web_server.py`, then `read_file`) for the websocket route and RPC handlers: `/api/ws` + JSON-RPC methods `session.create`, `prompt.submit` (param is `session_id`, snake_case), replies arrive as `message.complete` events.

### 8. Deploy the chat client
Copy this skill's `scripts/chat_client.py` to the host (invoke through the `terminal` tool), export `BRIDGE_TOKEN`, round-trip test: expect an exact-word reply.

### 9. Sync the token without exposing it
Pipe stdin over the working ssh channel; never echo secrets to logs or chat:
`ssh <user>@<host> "cat > /tmp/t && python3 -c '<rewrite .env keeping single token line>'"`

### 10. Layered doctor script
A small Python checker (see Verification) asserting four layers independently — token present / TCP / unauthed health / authed call — printing PASS/FAIL + fix per layer, exit 0 only when all green.

### 11. Self-healing watchdog on the far side
60-second PowerShell loop: start serve only if port closed (prevents duplicates); recycle serve when the authed probe returns 401 (stale token); restart tunnel with exponential backoff capped at 15 min (protects against fail2ban bans during outages). Launch at login via Startup-folder VBS (`wscript.exe` → hidden powershell). Scheduled Tasks need UAC — Startup folder is the fallback that works unattended.

### 12. Kill-test everything
Stop serve → expect restore ≤90 s. Stop tunnel → same. Rotate token via script → zero manual steps. Only then declare the bridge done.

### 13. Monitor from this host (silent on success)
Register a `cronjob` (no_agent=true, e.g. `*/15 * * * *`) whose script prints NOTHING when healthy and an alert line when degraded. Silence = green; you only hear about failures.

### 14. Persist
Save instance facts (accounts, paths, ports, quirks) to `memory`; save this method as a skill so future sessions skip rediscovery.

## Pitfalls

- **Assumed identity**: docs said one username, reality another — always verify remotely first.
- **Inert config keys**: Hermes saves unknown YAML keys with a warning but implements nothing; `--help` is ground truth.
- **UI-stub routes**: headless `serve` 404s `/api/chat` — real conversation lives on `/api/ws`.
- **Ephemeral tokens**: unpinned serve regenerates its token every restart; pin before first launch, sync copies atomically (two copies of one secret = drift class).
- **fail2ban self-bans**: rapid ssh retry bursts ban the far IP — symptom is ping OK but port 22 times out; fix `fail2ban-client set sshd unbanip <ip>` and add backoff/whitelist.
- **Startup ≠ boot**: Startup items fire only at login; auto-login (Sysinternals Autologon, encrypted LSA store — user types the password themselves) closes the reboot gap; otherwise alert-on-downgrade instead.
- **Provider ≠ transport**: doctor green + chat dead usually means the far agent's LLM provider key failed, not the bridge.

## Verification

`python3 scripts/bridge_doctor.py` exits 0 (all four layers PASS) AND `python3 scripts/chat_client.py "reply ACK"` returns a reply containing ACK — proving transport, auth, and the far agent's brain in one shot.
