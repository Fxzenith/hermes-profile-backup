---
name: hermes-ssh-stale-backend
description: "Fix Hermes Desktop SSH 'could not verify backend' errors."
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [Hermes, Desktop, SSH, Troubleshooting]
---

# Hermes Desktop SSH Stale-Backend Repair

Diagnoses and fixes the Hermes Desktop error "Desktop boot failed — Could not
verify the existing SSH backend." when connecting to a Linux VPS over SSH. This
is a clean-side stale-backend cleanup, NOT a network or auth fix. It only
touches the desktop's dedicated `hermes serve` SSH backend and its lockfile; it
does NOT touch the Telegram/CLI gateway, the 9119/9120 public dashboard, or any
running agent sessions. Companion to the setup skill `hermes-remote-ssh-gateway`.

## When to Use
- Desktop app overlay: "Desktop boot failed — Could not verify the existing SSH backend."
- Desktop keeps failing to connect on boot but the VPS SSH key auth clearly works.
- User asks "is this a network problem?" for a Hermes Desktop SSH connection.

## Prerequisites
- Linux VPS admin (root) reachable over SSH.
- The desktop app's "Connect via SSH" backend already configured once (key
  authorized, Identity file set) — this skill repairs a stale backend, it does
  not configure the connection the first time.
- The Hermes desktop renderer+electron source bundle (install dir, e.g.
  `/usr/local/lib/hermes-agent/apps/desktop`).

## Quick Reference
- Verify server side: `ss -tlnp | grep ':22\b'` (listening);
  `systemctl status ssh` (running); `ufw status | grep 22` (allowed);
  `journalctl -u ssh --since "3 hours ago"` (auth trail).
- Prove backend binary works: `hermes --version` and `hermes doctor` (expect exit 0).
- Find stale backend process:
  `ps -eo pid,lstart,cmd | grep -- --ssh-session-token-file | grep -v grep`
- Find ownership record: `find ~/.hermes/desktop-ssh -name backend.lock.json`.
- Wire the error to source: `search_files` for `Could not verify the existing
  SSH backend` under `apps/desktop/electron/remote-lifecycle.ts` (bundle path).
- Fix: `kill <pid>` then `rm -rf ~/.hermes/desktop-ssh/<ownershipId>`.
- User reconnects in the desktop app (fresh backend spawns).

## Procedure
1. Rule out network/auth FIRST so you don't clean up a healthy link. Probe the
   server via `terminal`: `ss -tlnp | grep ':22\b'`, `systemctl status sshd ssh`,
   `ufw status`. Then read the recent auth trail:
   `journalctl -u sshd -u ssh --since "8 hours ago"` (or `tail /var/log/auth.log`).
   The signature is `Accepted publickey for <user> from <IP>` followed ~1s later
   by `disconnected by user`, repeated in a burst = the desktop retrying at boot,
   i.e. auth WORKS and this is NOT a network problem.
2. Prove the remote backend binary is healthy: `which -a hermes`,
   `hermes --version`, `hermes doctor | tail` (expect exit 0). Also run it under
   a clean non-interactive env (mirrors an SSH remote command):
   `env -i /usr/bin/bash --noprofile --norc -c 'PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin; export PATH; hermes --version'`.
3. Confirm the failure mode is stale-backend reuse. Find the throw site with
   `search_files` for the exact string `Could not verify the existing SSH backend`
   in the bundled desktop source (`apps/desktop/electron/remote-lifecycle.ts`).
   It is raised when the desktop finds a live-but-unresponsive backend in
   `~/.hermes/desktop-ssh/<owner>/backend.lock.json`, tries to REUSE it by
   port-forward + token probe, and the probe throws (the code path does NOT
   fall back to respawn — that's why boot dies).
4. Locate the stale backend process: `ps -eo pid,lstart,cmd | grep -- --ssh-session-token-file`.
   It is `hermes serve --isolated --host 127.0.0.1 --port 0 --ssh-session-token-file
   <owner>/<nonce>.token --ssh-owner-nonce <nonce>` — alive as a PID but not serving.
   Read its lockfile `find ~/.hermes/desktop-ssh -name backend.lock.json` and
   confirm the PID/lock `spawnNonce`/token match.
5. Tear it down (this specifically is `terminal`):
   `kill <pid>`; if still alive after ~1s, `kill -9 <pid>`; then
   `rm -rf ~/.hermes/desktop-ssh/<ownershipId>`.
6. Verify: `ps -p <pid> --no-headers` is empty, and
   `find ~/.hermes/desktop-ssh -type f | wc -l` is 0.
7. Have the user reconnect in the desktop app — with no lock record, it spawns a
   fresh backend and connects.
8. If it still fails after reconnect, compare versions: server `hermes --version`
   (bundle `apps/desktop/package.json`'s `"version"`) vs the user's desktop app
   (Help → About), and reset the app's "Hermes path" to auto-detect.

## Pitfalls
- This symptom is NOT a network problem — the auth log already shows the key
  being accepted. Do not waste time on firewall/IP/key work; go straight to the
  stale backend.
- The stale serve process runs with `--port 0` (a random port); the lockfile can
  record a port the process is no longer answering, so the reuse probe times
  out even though the PID is alive.
- Kill ONLY the process whose cmdline contains `--ssh-session-token-file`. Leave
  the Telegram/CLI gateway and any `hermes serve --host 0.0.0.0 --port 9119` /
  `hermes dashboard --port 9120` (run under tmux) alone.
- the Hermes desktop source may live at `/usr/local/lib/hermes-agent/apps/desktop`;
  on other installs it's the bundle's `apps/desktop` path.

## Verification
`ps -p <killed_pid>` prints nothing, `find ~/.hermes/desktop-ssh -type f | wc -l` prints 0,
and the user's desktop app connects via a freshly spawned SSH backend.