# Grant Access to Local Hermes Agent and List Methods Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Enable remote communication with the user's local Hermes Agent running on Windows and allow listing of its available methods.

**Architecture:** Use SSH tunneling to forward a local Unix domain socket or TCP port where the Hermes Agent exposing a management endpoint; modify the local Hermes configuration to expose a "list_methods" command; create a small CLI script to query it; verify output.

**Tech Stack:** Python CLI, SSH, Hermes desktop config, JSON-RPC over socket, git for version control.

---

## Task 1: Verify local Hermes binary and its version

**Objective:** Confirm the Hermes desktop binary is installed and accessible.

**Files:**
- Check: `C:\\Users\\phemelo\\AppData\\Local\\Hermes\\Hermes.exe` (Windows path)

**Step 1: Write failing check script**
```batch
@echo off
rem Check if Hermes.exe exists
if not exist "%LOCALAPPDATA%\\Hermes\\Hermes.exe" (
    echo Hermes binary not found
    exit 1
)
echo Hermes binary found
exit 0
```

**Step 2: Run script to verify**
Run the batch file; expected output: `Hermes binary found` and exit code 0.

**Step 3: Commit**
```bash
git add check_hermes.bat
```

---

## Task 2: Enable remote API in local Hermes config

**Objective:** Modify the Hermes desktop configuration to expose a management endpoint.

**Files:**
- Modify: `C:\\Users\\phemelo\\.hermes\\profiles\\default\\config.yaml`

**Step 1: Write new config snippet**
Add the following to the `communication` section:
```yaml
communication:
  remote_api:
    enabled: true
    port: 27183
    auth_token: "${HERMES_REMOTE_TOKEN}"
```

**Step 2: Save config**
Use a text editor or `write_file` to update the file.

**Step 3: Commit**
```bash
git add config.yaml
```

---

## Task 3: Create CLI script to list methods

**Objective:** Implement a Python CLI that connects to the remote API and lists available methods.

**Files:**
- Create: `C:\\Users\\phemelo\\.hermes\\scripts\\list_methods.py`

**Step 1: Write script**
```python
#!/usr/bin/env python3
import os
import json
import socket
import subprocess

HERMES_SOCKET = "127.0.0.1:27183"
AUTH_TOKEN = os.getenv("HERMES_REMOTE_TOKEN", "")

def send_request(method, params=None):
    if not AUTH_TOKEN:
        raise RuntimeError("HERMES_REMOTE_TOKEN not set")
    payload = json.dumps({
        "method": method,
        "params": params or {}
    })
    sock = socket.create_connection((HERMES_SOCKET.split(":")[0], int(HERMES_SOCKET.split(":")[1])), timeout=5)
    sock.sendall(payload.encode())
    response = sock.recv(4096).decode()
    sock.close()
    return json.loads(response)

def list_methods():
    return send_request("list_methods")

if __name__ == "__main__":
    try:
        methods = list_methods()
        print(json.dumps(methods, indent=2))
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
```

**Step 2: Make script executable**
```batch
chmod +x list_methods.py
```

**Step 3: Commit**
```bash
git add list_methods.py
```

---

## Task 4: Configure environment variable for auth token

**Objective:** Set `HERMES_REMOTE_TOKEN` securely.

**Files:**
- Modify: user environment variables (Windows)

**Step 1: Set token**
```batch
setx HERMES_REMOTE_TOKEN "your-strong-random-token-here"
```

**Step 2: Verify**
Open a new command prompt and run `echo %HERMES_REMOTE_TOKEN%`; token should be displayed.

**Step 3: Commit**
(Note: environment variable changes are not version‑controlled; document the step.)

---

## Task 5: Test the listing script

**Objective:** Verify that the script returns the expected list of methods.

**Files:**
- No new files; use previously created `list_methods.py`.

**Step 1: Run script**
```batch
python C:\\Users\\phemelo\\.hermes\\scripts\\list_methods.py
```

**Expected output:** JSON object with method names, e.g.:
```json
{
  "list_methods": "...",
  "ping": "...",
  "status": "..."
}
```

**Step 2: Verify success**
The output should be valid JSON and contain at least the method `list_methods`.

**Step 3: Commit**
```bash
git add list_methods.py
```

---

## Task 6: Document usage and add to PATH (optional)

**Objective:** Provide user-friendly instructions and make the script callable from anywhere.

**Files:**
- Create: `C:\\Users\\phemelo\\.hermes\\profile.d\\list_methods.env`
- Modify: user PATH environment variable

**Step 1: Create env file**
```batch
echo set "PATH=%PATH%;C:\Users\phemelo\.hermes\scripts" > list_methods.env
echo set HERMES_REMOTE_TOKEN=your-strong-random-token-here >> list_methods.env
```

**Step 2: Add to startup**
Add `list_methods.env` to the user's startup scripts or load it manually before using the script.

**Step 3: Commit**
```bash
git add profile.d/list_methods.env
```

---

## Testing / Validation

- Run `python list_methods.py` and confirm JSON output matches the expected schema.
- Verify that `HERMES_REMOTE_TOKEN` is not logged in plain text (use environment variable masking).
- Ensure the SSH tunnel from the VPS forwards port 27183 to the Windows machine (use `ssh -L 27183:127.0.0.1:27183 user@102.208.217.192`).

## Risks / Tradeoffs

- **Security:** Exposing a remote API can be a vector for unauthorized access; use strong tokens and firewall rules.
- **Compatibility:** The Windows path format differs from Linux; scripts must handle both.
- **Versioning:** Future Hermes updates may change the API; pin the contract version in the config.

## Open Questions

- Which exact methods should be exposed beyond `list_methods`?
- Should the endpoint be HTTP/JSON‑RPC or a custom binary protocol?
- How to handle reconnection and heartbeat monitoring?

---

**After saving the plan, the next step is to begin implementation using the `subagent-driven-development` skill, executing each task sequentially with spec and code quality reviews.** 

Saved path: `.hermes/plans/2026-09-28_123456-grant-access-to-local-hermes.md`