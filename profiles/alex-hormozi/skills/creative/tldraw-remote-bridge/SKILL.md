---
name: tldraw-remote-bridge
description: Connect remote tldraw Offline to Hermes via SSH tunnel.
version: 0.2.0
author: Hermes Agent
license: MIT
platforms: [linux, windows]
metadata:
  hermes:
    tags: [tldraw, ssh-tunnel, remote, vps, canvas]
---

# Bridging Hermes (VPS) to tldraw Offline (Remote PC)

Connect a tldraw Offline desktop app running on a **different machine** (e.g. your Windows PC) to Hermes running on a **VPS**, so the `tldraw-offline` skill's `curl` recipes reach the canvas over `localhost:7236`. This skill covers the connection/ops arc only: environment audit, enabling the optional skill, the reverse-SSH tunnel, token persistence, and the latency pitfalls. The actual canvas scripting recipes live in the `tldraw-offline` skill — load it with `skill_view(name="tldraw-offline")` once the bridge is up.

It does NOT draw anything, and does NOT cover document-script authoring (that is `tldraw-offline`).

## When to Use

- "Connect Hermes on my VPS to tldraw Offline on my Windows PC."
- "Set up the reverse SSH tunnel so the tldraw API is reachable from the server."
- "Enable the tldraw-offline skill / it's not showing in `hermes skills list`."
- "Why does `saveDoc()` return `file-save timed out after 30000ms`?" (OneDrive path — not the tunnel)
- "Create a Hermes-controlled tldraw doc outside OneDrive so edits persist."
- After the bridge is up, canvas tasks are handed to `tldraw-offline`.

## Prerequisites

- tldraw Offline installed and **running with a document open** on the remote PC. Its local API listens on `127.0.0.1:7236` on that PC.
- SSH access from the PC to the VPS (we used `root@<VPS_IP>` — note there is **no `pheme` user**; the key is authorized under `root`).
- `curl`, `ssh`, `ss` available on the VPS (all standard). `tailscale` was NOT present — so we use a plain reverse tunnel, not a VPN.
- The per-launch tldraw bearer token from the PC's `server.json` (`%APPDATA%\tldraw\server.json` on Windows). The VPS copy goes to `~/.config/tldraw/server.json`.

## How to Run

Invoke every command through the `terminal` tool. Write the token file with `write_file` (never paste the token into chat logs longer than needed). Verify the bridge with `ss` and a no-token `curl /readme`. For authenticated calls, use the helper `scripts/tldraw_req.sh` via `terminal`, or read the token inline each call. Canvas edits after this point belong to `tldraw-offline` (load via `skill_view`).

## Quick Reference

- Enable optional skill: `hermes skills install official/creative/tldraw-offline --yes`
- Verify enabled: `hermes skills list | grep -i tldraw` → `enabled`
- Tunnel (run on **Windows PowerShell**, not the VPS): `ssh -N -R 7236:127.0.0.1:7236 root@<VPS_IP>`
- Tunnel up check: `ss -tlnp | grep 7236` → `LISTEN ... ("sshd",...)`
- No-token reachability: `curl -i --max-time 10 http://127.0.0.1:7236/readme` → `200 OK`
- Authenticated read: `POST /api/search` with `{"code":"return await api.getDocs()"}`
- Token file: `~/.config/tldraw/server.json` = `{"port":7236,"token":"<token>"}`, perms `600`
- Helper: `bash scripts/tldraw_req.sh <endpoint> <payload.json> [METHOD]`
- Create doc: `POST /api/docs/create` with `{"name":"Hermes-Workspace","directory":"C:\\tldraw"}` returns `id`,`filePath`,`windowId`. Directory MUST already exist (API rejects a missing dir, will not mkdir).
- Get focused doc id: `POST /api/search` `{"code":"return (await api.getFocusedDoc()).id"}`
- Mutate + save (in `/exec`): `editor.createShape(...)` then `await helpers.saveDoc()`
- Persisted? read back via `/api/search`: `d.unsavedChanges === false` and `d.shapeCount` reflects the edit.

## Procedure

1. **Audit (read-only).** Confirm tooling and that no private network already exists:
   - `command -v curl wget ssh tailscale nc netcat` (we had curl/wget/ssh/nc; no tailscale)
   - `ip -brief addr` and `ip route` — expect only public `eth0` + a DOWN `docker0`; **no RFC1918 route to the PC LAN**.
   - `ss -tlnp | grep 7236` — empty until the tunnel is up.
   - `hermes skills list | grep -i tldraw` — empty until step 2.

2. **Enable the optional skill** (it is NOT active by default and will not appear in `hermes skills list` until installed):
   - `hermes skills install official/creative/tldraw-offline --yes`
   - Built-in scanner may flag the skill's own `curl ... Authorization` examples as "DANGEROUS" but auto-allows it (builtin source). Safe.
   - Re-run `hermes skills list | grep -i tldraw` → should now show `tldraw-offline ... enabled`.

3. **Open the reverse tunnel from the PC** (VPS cannot initiate to your LAN, so the PC pushes the port):
   - Windows PowerShell: `ssh -N -R 7236:127.0.0.1:7236 root@<VPS_IP>`
   - On the VPS, verify: `ss -tlnp | grep 7236` → `LISTEN 127.0.0.1:7236 ... ("sshd",pid=...)`.
   - Reachability without auth: `curl -i --max-time 10 http://127.0.0.1:7236/readme` → `HTTP/1.1 200 OK` with the API README. (`/readme` and `GET /` need no token.)

4. **Persist the token on the VPS** (the skill reads it from a local file each call):
   - `write_file` to `/root/.config/tldraw/server.json`: `{"port":7236,"token":"<paste-token-here>"}`
   - `terminal`: `chmod 600 ~/.config/tldraw/server.json`

5. **Authenticated smoke test (read-only):**
   - Write a payload file, e.g. `{"code":"return await api.getDocs()"}`, then:
     `bash scripts/tldraw_req.sh /api/search /tmp/docs.json`
   - Expect `{"success":true,"result":[ ... ]}` listing the open doc(s). This proves auth + canvas reachability.

6. **Hand off to `tldraw-offline`** for actual canvas work. Remember the scope + latency rules in Pitfalls.

7. **(Persistence) Create a non-OneDrive doc so `saveDoc()` sticks.** This resolved the save timeout — OneDrive paths stall the write past tldraw's 30s cap:
   - User pre-creates the folder on Windows (VPS cannot mkdir a Windows path): e.g. `mkdir C:\tldraw` (PowerShell).
   - Create the doc via `POST /api/docs/create` with `{"name":"Hermes-Workspace","directory":"C:\\tldraw"}` → returns `id` (e.g. `tldr:file:...`), `filePath` (`C:\tldraw\Hermes-Workspace.tldraw`), `documentId`, `windowId`.
   - Save its `id` to `/tmp/tldraw_docid.txt` for later `/exec` calls.
   - Build + save in one `/exec`: `editor.createShape({id:createShapeId('x'), type:'geo', x:120, y:120, props:{geo:'rectangle', w:220, h:110, color:'violet', fill:'solid', richText:toRichText('Hermes Workspace')}})` then `await helpers.saveDoc()`.
   - Read back via `/api/search`: find `d=docs.find(x=>x.name==='Hermes-Workspace')`; confirm `d.unsavedChanges === false` and `d.shapeCount` includes the new shape → persisted. Verified end-to-end: save ~12s, `unsaved:false`, shape present.
   - Proven-good persistent docs: `Hermes-tldraw` (`C:\Users\pheme\Hermes-tldraw.tldraw`) and `Hermes-Workspace` (`C:\tldraw\Hermes-Workspace.tldraw`). Leave the OneDrive `Untitled.tldraw` alone for `saveDoc()`.

## Pitfalls

- **`saveDoc()` times out on OneDrive-backed docs — NOT the tunnel.** Symptom: `helpers.saveDoc()` fails at ~30s with `Request 'file-save' timed out after 30000ms` (or `Timed out waiting for the authoritative room to acknowledge edits`), even though a no-op `/exec` round-trips in ~200ms. Root cause: the Windows doc path is under OneDrive (`C:\Users\<user>\OneDrive\Documents\...`) and OneDrive's Files-On-Demand / sync engine intercepts the write, stalling past tldraw's 30s `file-save` cap. The tunnel latency is NOT the cause (proven: same call on a non-OneDrive path saves in <1s). Fix: **create docs in a plain-local directory** (`C:\tldraw`, `C:\Users\<user>`) via `POST /api/docs/create`, then `saveDoc()` persists in <1s and `unsavedChanges` goes `false`. The old OneDrive doc can stay open; just don't rely on `saveDoc()` against it.
- **`POST /api/docs/create` needs an existing directory.** It validates the `directory` field and returns `Directory does not exist: <path>` — it will NOT mkdir. The VPS cannot create Windows folders, so either have the user pre-create it (e.g. `mkdir C:\tldraw` in PowerShell) or fall back to `C:\Users\<user>` (also non-OneDrive). Passing a non-existent dir is the only failure mode of this endpoint.
- **Scope split — this bit us twice.** In `/api/search` only `api` is in scope (`api.getDocs()`, `api.getFocusedDoc()`, `api.getShapes()`). `helpers`/`editor` are NOT defined there. In `/exec` only `editor`, `helpers`, `signal`, `app` are injected — `api` is NOT defined. Use `/api/search` to *read*, `/exec` to *mutate*.
- **Inline JSON quoting is fragile.** Quoted `-d '{"code":"... await import(\"tldraw\") ..."}'` in a shell breaks. Write the payload to a file and use `--data @file` (see `scripts/tldraw_req.sh`).
- **Token does not persist across shells.** Each `terminal` call is fresh, so an exported `TOKEN` is gone next call. Read it inline every time: `TOKEN=$(python3 -c "import json;print(json.load(open('/root/.config/tldraw/server.json'))['token'])")`.
- **Login user is `root`, not `pheme`.** The key is authorized under root; `pheme@<ip>` falls through to a password prompt that can't work.
- **Tunnel direction.** The `-R` forward is initiated from the PC. A bare `ssh root@<vps>` is just your normal login — it does NOT open the canvas tunnel.
- **No public exposure needed.** The forward binds `127.0.0.1:7236` on the VPS only; ufw stays untouched. Do not open port 7236 to `0.0.0.0`.

## Verification

A working bridge shows all three:
1. `ss -tlnp | grep 7236` → `LISTEN` owned by `sshd` (tunnel up).
2. `curl -i --max-time 10 http://127.0.0.1:7236/readme` → `HTTP/1.1 200 OK`.
3. `bash scripts/tldraw_req.sh /api/search /tmp/docs.json` → `{"success":true,"result":[ ... open docs ... ]}`.

If 1–2 pass but 3 returns `401`, the token file is wrong/missing. If 3 returns `success:true` with `shapeCount`, the canvas is fully reachable and `tldraw-offline` can take over.

**Persistence proof (non-OneDrive doc):** after `createShape` + `helpers.saveDoc()`, read back via `/api/search`: the doc `unsavedChanges` is `false` and `shapeCount` includes the new shape. If `unsavedChanges` stays `true` or `saveDoc()` hits `file-save timed out after 30000ms`, the doc path is under OneDrive — recreate it in a plain-local dir.
