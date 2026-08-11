---
name: agentmail-email
description: Read and send email via the AgentMail API.
version: 0.1.0
author: Hermes
metadata:
  hermes:
    tags: [Email, AgentMail, REST API, Inbox]
---

# AgentMail Email Access

Connects to AgentMail's API for AI agents: verify an API key, locate the agent inbox, read threads/messages, and send mail. It does NOT cover webhooks/WebSockets, custom domains, pods, or the MCP server. Depends on `curl` (REST) and optionally the official npm CLI; no Python SDK required.

## When to Use

- "Connect to agentmail" / "set up our email inbox"
- "Check the inbox", "read my email", "send an email" when the user has given an `am_...` key or an `@agentmail.to` address
- Verifying a pod-/inbox-scoped key and discovering its org/inbox
- First-time setup of AgentMail credentials for an agent

## Prerequisites

- AgentMail API key (`am_...`) — org-, pod-, or inbox-scoped
- `curl`; optional official CLI: `npm install -g agentmail-cli` (binary `agentmail`)
- Docs are agent-authored: start at `https://docs.agentmail.to/llms.txt`; append `.md` to any page URL for clean markdown

## How to Run

1. Verify the key and discover its scope via `GET https://api.agentmail.to/v0/auth/me` (Bearer auth).
2. List inboxes with `GET /v0/inboxes` — `inbox_id` equals the email address.
3. Read or send through REST or the CLI (`AGENTMAIL_API_KEY` env var).
4. Persist credentials to `~/.agentmail/credentials.json` (chmod 600) and add a `memory` entry pointing at the file.

## Quick Reference

REST — base `https://api.agentmail.to`, header `Authorization: Bearer $AM_KEY`:

```bash
GET  /v0/auth/me                              # identity + scope_type (organization|pod|inbox)
GET  /v0/inboxes                              # list inboxes
GET  /v0/inboxes/{inbox_id}                   # inbox details
GET  /v0/inboxes/{inbox_id}/threads           # list threads
GET  /v0/inboxes/{inbox_id}/messages          # list messages
POST /v0/inboxes/{inbox_id}/messages/send     # send (client_id for idempotent retries)
```

CLI (`export AGENTMAIL_API_KEY=am_...`):

```bash
agentmail inboxes list
agentmail inboxes:messages send --inbox-id <inbox_id> --to <to> --subject "<s>" --text "<body>"
agentmail inboxes:threads ...   # thread subcommands (colon resources: inboxes:messages, inboxes:threads)
```

## Procedure

1. **Docs first** (AgentMail's own instruction): fetch `https://docs.agentmail.to/llms.txt` through `terminal` (`curl`), then `llms-full.txt` for the full endpoint index; pull exact paths/schemas from specific pages like `api-reference/inboxes/list.md` and `api-reference/auth/me.md`.
2. **Verify the key**: `curl -s https://api.agentmail.to/v0/auth/me -H "Authorization: Bearer $AM_KEY"` — note `api_key_id`, `organization_id`, and `scope_type` (an inbox-scoped key works fine against `/v0/inboxes`).
3. **Locate the inbox**: `GET /v0/inboxes` — the `inbox_id` field is the email address itself (e.g. `phemeloagent-001@agentmail.to`).
4. **Check contents**: list threads and messages; a fresh inbox returns `{"count": 0}` — that is success.
5. **Persist credentials**: `write_file` `~/.agentmail/credentials.json` with `api_key`, `api_key_id`, `organization_id`, `pod_id`, `inbox_id`, `email`, `scope_type`, `base_url`; then `chmod 600` it via `terminal` and add a `memory` entry referencing the file path (never the raw key).
6. **Install the CLI (optional)**: `npm install -g agentmail-cli`; set `AGENTMAIL_API_KEY`; confirm with `agentmail inboxes list`.

## Pitfalls

- **URL-encode inbox IDs in paths**: `@` breaks curl paths — use `phemeloagent-001%40agentmail.to` in `/v0/inboxes/{inbox_id}/...` URLs.
- **Docs-vs-CLI drift**: `agentmail auth me` is NOT a valid topic in v0.7.14 ("No help topic for 'auth'") — use the REST `/v0/auth/me` for identity; CLI topics use colons (`inboxes:messages`, `inboxes:threads`).
- **Never store the API key in `memory`** (it is injected into every future turn); the chmod-600 JSON file is the store, memory holds only the path.
- **`{}` / `count: 0` is not an error** on a fresh inbox — read and send paths still work.
- **EU region**: `https://api.agentmail.eu` is the alternative base; prod default is `api.agentmail.to`.
- **Sign-up flow** (`POST /agent/sign-up` + OTP verify) is only for first-time self-registration — with an existing key, skip it and use Bearer auth.
- Rate-limit specifics live in the KB: `https://docs.agentmail.to/knowledge-base/rate-limits.md`.

## Verification

`curl -s https://api.agentmail.to/v0/auth/me -H "Authorization: Bearer $AM_KEY"` returns JSON with `api_key_id` and `scope_type`, and `GET /v0/inboxes` returns the expected `inbox_id` — proving read access; a successful `POST .../messages/send` proves send.
