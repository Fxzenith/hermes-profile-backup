#!/usr/bin/env python3
"""Layered health check for the bridge to a remote Hermes agent.

Exit 0 = every layer green. Each FAIL prints the owning fix.
Edit LAYER 2/3/4 targets if you used a different port than 27183.
"""
import socket, sys, json, urllib.request

TOKEN = os.environ.get("BRIDGE_TOKEN")
if TOKEN is None:
    for line in os.path.expanduser("~/.hermes/.env"):
        if line.startswith("HERMES_DASHBOARD_SESSION_TOKEN="):
            TOKEN = line.strip().split("=", 1)[1]

results = []
def check(name, fn, fix):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, str(e)[:80]
    results.append((name, ok, detail, fix))

def tcp():
    s = socket.create_connection(("127.0.0.1", PORT), timeout=4); s.close()
    return True, "connected"
def health():
    r = urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=8)
    d = json.loads(r.read())
    return d.get("ok") is True, f"ok={d.get('ok')} version={d.get('version')}"
def auth():
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/config",
                                 headers={"X-Hermes-Session-Token": TOKEN})
    urllib.request.urlopen(req, timeout=8)
    return True, "token accepted"

check("1. token available", lambda: (TOKEN is not None and len(TOKEN) >= 32,
      f"{len(TOKEN) if TOKEN else 0} chars"),
      "FIX: re-run rotate_token.ps1 on far machine (syncs both sides)")
check("2. tunnel+serve TCP", tcp,
      "FIX: far side down; watchdog should heal <=2 min, else restart serve+tunnel there")
check("3. GET /api/health (unauthed)", health,
      "FIX: TCP open but HTTP dead - serve wedged; recycle hermes process")
check("4. authed GET /api/config", auth,
      "FIX: 401 = token drift; re-run rotate_token.ps1")

fails = [r for r in results if not r[1]]
for name, ok, detail, fix in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name:38s} {detail}")
    if not ok:
        print(f"      -> {fix}")
print("\nLINK HEALTHY" if not fails else f"\n{len(fails)} LAYER(S) DOWN")
sys.exit(0 if not fails else 1)
