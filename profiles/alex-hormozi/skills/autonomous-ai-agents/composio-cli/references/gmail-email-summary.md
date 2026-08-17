# Composio → Gmail: summarize inbox / block sender (proven recipe, Aug 2026)

End-to-end flow for "check my emails / summarize the last N days / block a sender"
on a headless VPS with the v3 composio CLI.

## 0. Preconditions
- `composio whoami` returns a session (logged in).
- `composio connections list --toolkit gmail` shows ≥1 connection with status `ACTIVE`.
  - If none: `composio link gmail --no-browser --no-wait` → send `redirect_url` to user →
    poll `connections list --toolkit gmail` (every ~10s) until `ACTIVE` (took ~10–60s in practice).
  - Two `INITIALIZING` entries can appear for one click; one becomes ACTIVE.

## 1. Fetch the window
```bash
composio execute GMAIL_FETCH_EMAILS -d '{"query": "after:2026/08/02", "max_results": 50}'
```
- Returns `{"successful": true, "storedInFile": true, "outputFilePath": "/tmp/composio/adhoc_*/GMAIL_FETCH_EMAILS_OUTPUT_*.json", "tokenCount": <huge>}`.
  The tool's stdout is NOT the payload — read the file.
- Payload: `{"data": {"messages": [...], "nextPageToken": "...", "resultSizeEstimate": N}, ...}`.
- Paginate: repeat with `"page_token": <nextPageToken>` until `nextPageToken` is absent.
  Merge pages and de-dupe by `messageId` (page overlap/dupes happen).

## 2. Parse (python3, standalone file — avoid heredocs with `&` in the terminal tool)
```python
import json, datetime
def safe(v):
    if v is None: return ""
    if isinstance(v, (list, dict)): return json.dumps(v)
    return str(v)
def ts(t):
    try: return datetime.datetime.fromtimestamp(int(t)/1000).strftime("%m-%d %H:%M")
    except: return str(t)
rows = []
for p in ["/tmp/composio/adhoc_xxx/GMAIL_FETCH_EMAILS_OUTPUT_a.json",
          "/tmp/composio/adhoc_yyy/GMAIL_FETCH_EMAILS_OUTPUT_b.json"]:
    d = json.load(open(p))["data"]
    for m in d["messages"]:
        rows.append({"id": m.get("messageId"), "stamp": m.get("messageTimestamp"),
                     "ts": ts(m.get("messageTimestamp")), "sender": safe(m.get("sender")),
                     "subject": safe(m.get("subject")), "preview": safe(m.get("preview"))[:200],
                     "labels": m.get("labelIds", [])})
seen = set(); uniq = []
for r in rows:
    if r["id"] not in seen: seen.add(r["id"]); uniq.append(r)
uniq.sort(key=lambda x: x.get("stamp", 0), reverse=True)
```
- `preview` is sometimes a dict (`{"body": "..."}`) — `safe()` handles it; never slice raw.
- Senders arrive as `"Display Name <addr@domain>"` — substring-match on the domain for grouping.

## 3. Classify before summarizing
Group by sender domain; in a typical inbox the bulk is noise (Pinterest recs, sports-betting
spam via whop/emails.who, crypto/newsletter blasts, daily platform statements). Flag:
- **Phishing/spoofed**: sender domain ≠ claimed brand (e.g. `google.account.support@…` claiming
  "Google Cloud balance due" is fake). Report as do-not-click.
- **Scam pattern**: repeated fake-urgency "loan/card approved, confirm access" from a single
  domain (e.g. `contato@utua.com.br`, addresses the user by the WRONG first name) → advance-fee
  phishing. Recommend blocking.
- **Actionable**: maintenance windows (e.g. TradeLocker), security alerts, job matches (Indeed),
  connection requests (LinkedIn).

## 4. Blocking a sender — what works and what doesn't (scope wall)
- ❌ `GMAIL_CREATE_FILTER` → **HTTP 403 `insufficientPermissions` / `ACCESS_TOKEN_SCOPE_INSUFFICIENT`**
  for `users/me/settings/filters`. The default `composio link gmail` grant has read+modify but NOT
  `gmail.settings.basic`, so persistent filters CANNOT be created via composio. Don't retry — it
  will not succeed with this grant.
- ✅ `GMAIL_BATCH_MODIFY_MESSAGES` (scope: `gmail.modify`, which IS granted):
  ```bash
  composio execute GMAIL_BATCH_MODIFY_MESSAGES -d '{"messageIds": [...], "addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX","UNREAD"]}'
  ```
  - Up to 1000 IDs/call. Response says "accepted" but **silently skips invalid IDs** — typos in
    IDs are dropped without error. Batch in chunks and verify at the end:
    `composio execute GMAIL_FETCH_EMAILS -d '{"query": "from:<domain> in:spam", "max_results": 20}'`
    → count matches the number you moved.
- ✅ Permanent future block: tell the user to Block sender in the Gmail UI (⋮ → Block).
- `GMAIL_FETCH_MESSAGE_BY_MESSAGE_ID` exists for full bodies/headers when a preview isn't enough.

## 5. Verifying scope limits before designing a flow
If a tool 403s on scopes, the connection is the limit — re-linking with the same composio grant
won't help. Design around what read/modify can do (fetch, summarize, label, move, trash) and hand
settings-level actions (filters) to the user or the Gmail UI.
