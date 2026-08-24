#!/usr/bin/env python3
"""Conversational client for a remote Hermes agent reached through an SSH reverse tunnel.

Usage:
  BRIDGE_TOKEN=<token> python3 chat_client.py [--session <id>] "your message"

Env:
  BRIDGE_TOKEN   value of the far side's HERMES_DASHBOARD_SESSION_TOKEN
  BRIDGE_PORT    tunnel port on this host (default 27183)

Protocol (discovered in hermes_cli/web_server.py source):
  ws://127.0.0.1:<port>/api/ws?token=<BRIDGE_TOKEN>
  → JSON-RPC session.create {}            → result.session_id
  → JSON-RPC prompt.submit {session_id, text}
  → collect events until type == "message.complete", payload.text is the reply.
"""
import asyncio, json, os, sys

PORT = int(os.environ.get("BRIDGE_PORT", "27183"))
TOKEN = os.environ.get("BRIDGE_TOKEN")
URI = f"ws://127.0.0.1:{PORT}/api/ws?token={TOKEN}"


async def run(prompt: str, session_id: str | None) -> None:
    import websockets  # pip install websockets

    if not TOKEN:
        sys.exit("BRIDGE_TOKEN not set")
    async with websockets.connect(URI, open_timeout=15, max_size=2**23) as ws:
        await asyncio.wait_for(ws.recv(), timeout=10)          # gateway.ready frame
        if not session_id:
            await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1,
                                      "method": "session.create", "params": {}}))
            while session_id is None:
                d = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                if d.get("id") == 1:
                    session_id = d["result"]["session_id"]
        await ws.send(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "prompt.submit",
                                  "params": {"session_id": session_id, "text": prompt}}))
        t0 = asyncio.get_event_loop().time()
        reply = ""
        while asyncio.get_event_loop().time() - t0 < 300:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=30)
            except asyncio.TimeoutError:
                break
            try:
                d = json.loads(raw)
            except Exception:
                continue
            p = d.get("params", {})
            t = str(p.get("type", ""))
            if d.get("id") == 2 and d.get("error"):
                sys.exit(f"submit error: {d['error']}")
            if t == "message.complete":
                pl = p.get("payload", {})
                reply = pl.get("text", "") if isinstance(pl, dict) else ""
                break
        print(f"[session: {session_id}]")
        print(reply or "(no response)")


if __name__ == "__main__":
    args = sys.argv[1:]
    sid = None
    if args and args[0] == "--session":
        sid = args[1]
        args = args[2:]
    asyncio.run(run(" ".join(args), sid))
