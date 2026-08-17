---
name: agent-reach
description: "Configure Agent-Reach web/social read-access for a server."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [agent-reach, twitter, reddit, web-access, mcp, exa, cookie-auth]
---

# Agent Reach — multi-platform web-access layer

Agent Reach (repo `Panniantong/Agent-Reach`, v1.5.x) is an **installer + doctor + router**, NOT a wrapper. It provisions upstream CLIs (twitter-cli, bili-cli, yt-dlp, gh, opencli, rdt-cli) and reads via those directly. Install it when the user wants their agent to read/search the web, YouTube, GitHub, RSS, B站, Twitter/X, Reddit, etc. from a server (no browser session available to borrow).

Project dev install: `pip install -e .`, tests `pytest tests/ -v`, CLI docs in `docs/install.md`, upstream guide `https://raw.githubusercontent.com/Panniantong/agent-reach/main/docs/install.md`.

## Install (headless server)

PEP 668-safe. Prefer a dedicated venv (pipx may be absent):

```bash
python3 -m venv ~/.agent-reach-venv
~/.agent-reach-venv/bin/pip install -e .              # or: pip install https://github.com/Panniantong/agent-reach/archive/main.zip
~/.agent-reach-venv/bin/agent-reach --version
```

- `agent-reach install --env=auto` is **read-only / safe** (checks deps, lists missing). Run it first, always.
- `--system` performs system-level installs/config — only after explicit user approval.
- Optional channels: `--system --channels=twitter,reddit,...` or `all`. Names: `opencli, twitter, xiaoyuzhou, xueqiu, xiaohongshu, reddit, facebook, instagram, bilibili, linkedin, all`.
- `config/mcporter.json` declares MCP servers (exa = `https://mcp.exa.ai/mcp`, xiaohongshu = localhost:18060). Exa semantic search needs `mcporter` (`npm install -g mcporter`) + `mcporter config add exa https://mcp.exa.ai/mcp --scope home`.
- Zero-config channels that work immediately on a fresh server: web (Jina Reader `curl https://r.jina.ai/URL`), YouTube (yt-dlp), GitHub (`gh`), RSS (feedparser), V2EX, B站 basic search API. Rich media channels (B站 full, 小宇宙) and login channels need extra config.
- Verify: `agent-reach doctor` → status per channel; `doctor --json` shows active backend.

## Cookie/API-key auth (channels that need login)

On a server there is **no browser session to borrow**. The user must export cookies from their own browser and paste them. Do NOT try `browser_cookie3`-style browser scraping.

Twitter/X, Reddit, 小红书, 雪球: paste a **Cookie-Editor Header String** from the user's logged-in browser session:
1. User installs the [Cookie-Editor](https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm) Chrome extension.
2. Log into the platform in their browser (recommend a secondary account — cookie-based automation on X/R is a ban risk).
3. Extension → Export → Header String → paste to you.

Store via stdin so the secret isn't in process args:
```bash
printf 'auth_token=...; ct0=...' | agent-reach configure twitter-cookies --stdin
```
Groq key (小宇宙 podcast transcribe): `agent-reach configure groq-key` (free, console.groq.com).
Proxy (needed when server IP is geo/risk-blocked, e.g. datacenter IPs for Reddit/X): `agent-reach configure proxy`, then export `HTTP_PROXY`/`HTTPS_PROXY`.

## twitter-cli (cookie backend) — critical details

- twitter-cli provisioned by Agent Reach reads auth from env: `TWITTER_AUTH_TOKEN` + `TWITTER_CT0`. Set them in-process for each call:
  ```bash
  export TWITTER_AUTH_TOKEN="..." TWITTER_CT0="..."
  twitter search "query" -n 10
  ```
- `agent-reach configure twitter-cookies` stores `twitter_auth_token`/`twitter_ct0` in `~/.agent-reach/config.yaml` (used only by `doctor`'s presence check, not for live calls).
- twitter-cli sends the **same `ct0` value** as both the `Cookie:` header and the `X-Csrf-Token:` header. Available commands: `feed`, `search`, `show`, `status`, `followers`, `follow`, `post`, etc.
- **Diagnostic triage (IMPORTANT):** `twitter status` returning `authenticated: true` only proves the auth-token is valid — it does NOT prove reads work. Test the read families separately to isolate the failure class:
  - `feed`/`show`/`likes`/`user-posts` work, `search` 404s → **do NOT assume it's an IP block, and do NOT assume it's account-trust.** The most likely cause is a **known, open twitter-cli v0.8.5 tool bug**: an x.com frontend change broke ClientTransaction init (`'NoneType' object has no attribute 'group'`), so twitter-cli can't emit the **`x-client-transaction-id` header** that X's SearchTimeline endpoint hard-requires → 404. HomeTimeline/UserTweets/feed/likes currently tolerate the missing header, so reads work while search doesn't. Confirmed via GitHub issues #73/#78 (public-clis/twitter-cli, still open, zero comments) and by persistence across 4 residential proxies AND a fresh community queryId. A proxy, an older account, or queryId swap will NOT fix it — it needs a maintainer patch (or seeding a valid ClientTransaction from a real logged-in homepage + ondemand bundle, which can't be done headlessly). Full proof + the `x-client-transaction-id` diagnosis: `references/twitter-search-clienttransaction.md`.
  - **HTTP 403 code 353** ("request requires a matching csrf cookie and header") → **`ct0` mismatch/corruption**, see `references/twitter-cli-cookie-debug.md`.
- **The `Failed to init ClientTransaction: 'NoneType' object has no attribute 'group'` warning IS meaningful**, not cosmetic. It means X's SearchTimeline (search) will 404 because the client-transaction header can't be generated. Treat it as the root-cause signature for the work-reads/search-404s split, NOT as ignorable debug noise.
- Decisive first check before blaming IP/proxy/account: look for the `Failed to init ClientTransaction` warning on the failing run — present = the known twitter-cli tool bug (search blocked until maintainer fix), NOT geo and NOT (primarily) account-trust. Only if that warning is absent does the REST-search byte-size probe help distinguish a tool quirk (real data) from account-trust gating (empty 200). See `references/twitter-search-clienttransaction.md`.
- See `references/twitter-cli-cookie-debug.md` for the exact corruption ledger, byte-verify fix, and the search-block discriminator test.
- Fetching/test/wiring free Webshare residential proxies from a user's API key (no manual endpoint copy, and the account-trust caveat): `references/webshare-proxy-api.md`.

## rdt-cli (Reddit cookie backend)

Reddit on a headless server routes through `rdt-cli` (NO anonymous path — logged-in session required). Install the pinned git source via pipx, then write the cookie credential (a plain `reddit_session` JWT, not a Header String) to `~/.config/rdt-cli/credential.json`.
- **`rdt read` takes the SHORT post ID** (`1v49v7c`), not the `t3_`-prefixed fullname — the fullname returns a misleading `not_found`.
- Test with `rdt status` (auth) + `rdt search` (real read); test the actual server IP before buying a proxy — Reddit worked proxy-free here even though X search was broken on the same IP (that was the twitter-cli ClientTransaction bug, not geo).
- Full credential format, verify commands, and the subagent-completeness pitfall: `references/reddit-rdt-cli-setup.md`.

## Pitfalls

- **Byte-exact verification of pasted credentials**: mid-length tokens (40-char `auth_token`, 160-char `ct0`) can get a single char corrupted in transit (transcription, shell quoting, heredoc). A mangled `ct0` gives a confusing 403 that looks like a server/geo problem. Always diff the stored value character-by-character against the user's original before declaring a connection broken. Never trust grep-then-eyeball.
- Do not reflow/pretty-print the full cookie dump into config — pluck only the tokens the upstream tool needs (`auth_token`, `ct0`); X needs exactly these two.
- `agent-reach install` safe mode is read-only; warn the user before anything `--system`.
- Headless server ⇒ some platforms may geo/rate-block the datacenter IP, BUT verify before buying a proxy, and check the ClientTransaction warning first for X. In one session Reddit read worked proxy-free off the VPS IP, while X search's 404 turned out to be the **twitter-cli ClientTransaction tool bug** (missing `x-client-transaction-id` header), not an IP block and not account-trust. Different channels/IPs behave differently: run the actual endpoint (and, for X, check the ClientTransaction warning + REST byte-size probe) before spending any money on a proxy.
- Do not buy a proxy or blame the IP before testing the actual endpoint and (for X) checking the `Failed to init ClientTransaction` warning. See the discriminator tests in the twitter references.