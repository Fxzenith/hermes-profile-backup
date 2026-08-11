---
name: agent-reach-social-config
description: Wire Agent Reach Twitter/Reddit and diagnose CLI 404s.
version: 0.1.0
author: Hermes
metadata:
  hermes:
    tags: [AgentReach, Twitter, Reddit, Proxy, Webshare, Diagnose]
---

# Agent Reach Social Platform Config

Configures Agent Reach (github.com/Panniantong/Agent-Reach) so a headless server agent can read/search Twitter and Reddit. Wire auth from pasted cookies, fetch free Webshare proxies when an IP route is needed, and diagnose why a CLI endpoint 404s without burning time on the wrong fix. Does NOT patch upstream tool internals for good (a targeted one-line trial patch is OK but gets reverted); captures the honest "this is an unfixed upstream bug" path instead.

## When to Use
- "Configure Agent Reach for Twitter" or "wire up X search".
- "Configure Reddit on this server" / paste a reddit_session cookie.
- "Set up a proxy for Twitter search" / a Webshare API key is provided.
- "Why does `twitter search` return 404 but feed works?" — clinical diagnosis.

## Prerequisites
- Agent Reach CLI installed into a venv (PEP 668): `python3 -m venv ~/.agent-reach-venv && ~/.agent-reach-venv/bin/pip install -e /root/Agent-Reach` (or `pipx install <repo zip>`).
- Upstream CLIs via pipx (auto-placed on `~/.local/bin`): `twitter-cli` and `rdt-cli`.
- Cookies pasted by the user (see Procedure). Never scrape a browser with browser-cookie3 tricks — the user exports cleanly.
- Webshare API key (`Authorization: Token <key>`) only needed for the proxy path.

## How to Run
Invoke all binaries through the `terminal` tool. Real binaries live at:
`~/.agent-reach-venv/bin/agent-reach`, `~/.local/bin/twitter`, `~/.local/bin/rdt`.

## Quick Reference
- `twitter status` / `twitter feed -n 3` / `twitter user-posts <handle>` — auth + read checks.
- `rdt status` / `rdt search "q" -r <sub> -n 5 -c` / `rdt read <short_id>` — Reddit.
- `rdt read <short_id>`: use the short post ID (e.g. `1abc123`), NOT `t3_`-prefixed; the prefixed form 404s.
- `agent-reach configure twitter-cookies --stdin` — saves Twitter tokens to `~/.agent-reach/config.yaml`.
- `agent-reach configure proxy` / `agent-reach doctor` — proxy + health check.
- Webshare API: `curl -H "Authorization: Token $KEY" "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page_size=20"`.

## Procedure

### 1. Configure Twitter auth
```
printf 'auth_token=...; ct0=...' | ~/.agent-reach-venv/bin/agent-reach configure twitter-cookies --stdin
pipx install twitter-cli
export TWITTER_AUTH_TOKEN="..."; export TWITTER_CT0="..."   # persisted in ~/.bashrc
twitter status    # expect authenticated: true
```
Only `auth_token` (40 chars) and `ct0` (160 chars) are needed from the Cookie-Editor export. When pasting, verify byte-exactness — one corrupt char in `ct0` yields `403 code 353 csrf` on read endpoints.

### 2. Configure Reddit (headless: manual credential file)
```
pipx install 'git+https://github.com/public-clis/rdt-cli.git@5e4fb3720d5c174e976cd425ccc3b879d52cac66'
mkdir -p ~/.config/rdt-cli
# write ~/.config/rdt-cli/credential.json
{"cookies":{"reddit_session":"<value>"},"source":"manual","username":"","modhash":null,"saved_at":<epoch>,"last_verified_at":null}
rdt status    # authenticated: true, capabilities read+write
rdt search "q" -n 3 -c
rdt read <short_id>
```
The `reddit_session` JWT cookie only is what rdt-cli reads. Delegate this to a subagent via `delegate_task` if parallel with other work, but always re-verify the credential file exists and `rdt status` passes afterward — a subagent may install the binary yet skip the credential+verify step.

### 3. Provide a proxy via the Webshare API (free tier)
```
curl -H "Authorization: Token $KEY" "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page_size=20"
```
Each result has `username`, `password`, `proxy_address`, `port`, `country_code`, `valid`. Build `http://user:pass@host:port` and export `HTTP_PROXY`/`HTTPS_PROXY` for the upstream call, or `agent-reach configure proxy`. Test the proxy route with `curl -x "$PROXY" https://api.ipify.org` first.

### 4. Diagnose `twitter search` HTTP 404 (feed works)
Check the official issue tracker first — this is a KNOWN unfixed bug:
```
gh issue list --repo public-clis/twitter-cli --search "search 404 OR SearchTimeline"
```
Root cause (issue #73/#78): an x.com home page redesign broke `get_ondemand_file_url`'s regex in `x_client_transaction/utils.py` → `ClientTransaction` never inits → the `x-client-transaction-id` header is missing → SearchTimeline returns 404 while HomeTimeline/UserTweets tolerate its absence. Contributions/config/proxies do NOT fix it. A one-line trial swap of `FALLBACK_QUERY_IDS["SearchTimeline"]` (fresh ID e.g. `Yw6L66Pw54NHKuq4Dp7b4Q` from `twitter-openapi/.../placeholder.json`) is worth testing but must be reverted; the request still 404s without the tx header.

## Pitfalls
- A raw `urllib`/`requests` probe to x.com JSON 404s or returns a bare `200` with 0 bytes — that's anti-bot TLS detection, not proof the endpoint is down. Always use curl_cffi `impersonate="chrome133a"` to match twitter-cli's fingerprint before concluding.
- Free Webshare proxies are already shared/flagged — usually they do NOT clear an X block. Confirm with a quick empirical test before telling the user "proxy fixed it".
- Twitter search 404 is NOT the user's account being new/trust-flagged. The proxy and the account both test cleanly; the missing tx header is the cause.
- Cookie-Editor string is sensitive (full account access). Prefer a secondary account; never echo full values back to chat.
- `ClientTransaction` init needs the AUTHENTICATED homepage + ondemand bundle to build its key — cannot be faked headlessly, so the tx-id cannot be generated without a real browser session.

## Verification
`twitter feed -n 1` and `rdt search "openai" -n 1 -c` both return `ok: true` with data, and `~/.config/rdt-cli/credential.json` plus `~/.agent-reach/config.yaml` exist — that proves auth is wired on both platforms.