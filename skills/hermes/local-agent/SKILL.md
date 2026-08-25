---
name: local-agent
description: Talk to the user's local Windows Hermes agent via tunnel.
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [Hermes, Local, Remote-Execution]
---

# Talking to the Local (Windows) Hermes Agent

When the user says "local agent", "ask my PC", "talk to the local machine", or invokes `/local-agent`, this skill is the entry point: send prompts to the Hermes agent running on their Windows desktop and get its replies back here.

## When to Use

- User says "local agent" / "ask the local agent" / "tell my PC"
- Any task that must execute on the user's Windows machine
- Checking state of the VPS↔local link

## Prerequisites

- Reverse tunnel up: Windows runs `ssh -R 27183:127.0.0.1:27183 root@102.208.217.192` and `hermes serve --port 27183 --host 127.0.0.1 --skip-build` (watchdog auto-heals both)
- Token `HERMES_DASHBOARD_SESSION_TOKEN` present in BOTH `.env` files (Windows canonical, VPS copy at `/root/.hermes/.env`)
- Companion skills: `local-hermes-link` (runbook + diagnosis ladder), `hermes-bridge` (generic method)

## How to Run

Canonical invocation — invoke through the `terminal` tool:

```bash
local-hermes "your prompt to the local agent"
python3 /root/local_hermes_chat.py --session <id> "follow-up in same session"
```

The wrapper lives at `/usr/local/bin/local-hermes`; it calls the Python client which speaks JSON-RPC over `ws://127.0.0.1:27183/api/ws?token=...`.

## Quick Reference

```bash
local-hermes "reply ACK"                                  # new session, fire-and-forget
python3 /root/local_hermes_chat.py --session <id> "msg"   # continue an existing session
python3 /root/local_hermes_doctor.py                      # 4-layer health check (exit 0 = green)
```

Reply arrives on stdout after `[session: <id>]`. The local agent has full tool access on its machine (terminal, files) — treat it as a remote worker; verify critical writes yourself.

## Procedure

1. **Health gate** (skip if you just used the link successfully): run `python3 /root/local_hermes_doctor.py`. If FAIL, follow the printed per-layer fix (see `local-hermes-link` skill's diagnosis ladder).
2. **Compose a self-contained prompt** — the local agent knows nothing about this conversation. Include exact paths, expected outputs, and constraints ("reply with exactly X", "do NOT print secrets", "one line each").
3. **Send** via `local-hermes "<prompt>"`. Timeout generously (`timeout=` ≥120 s): complex tasks can take minutes.
4. **(No response?)** The session may still be working — re-poll with `python3 /root/local_hermes_chat.py --session <same-id> "status?"`.
5. **Verify critical results independently** — ask for specific evidence (file sizes, first/last lines, registry values) rather than trusting "done".

## Pitfalls

- Long-running prompts time out the wrapper silently → poll the same session instead of resending (duplicate work).
- The local agent sometimes answers with commentary instead of the data asked for → re-ask with "one line each" / "paste raw output".
- PowerShell quirks on its side: `query session`/`quser` not on PATH inside git-bash shells — prefix with `powershell -Command "..."`.
- Secrets: never have it paste tokens/passwords into chat; pipe them via ssh stdin if a secret must move.

## Verification

`local-hermes "Reply with exactly: ACK"` returns output containing `ACK`.
