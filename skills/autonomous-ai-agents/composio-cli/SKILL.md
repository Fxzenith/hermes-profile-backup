---
name: composio-cli
description: "Configure Composio: install CLI, OAuth login, link apps."
---

# Composio CLI

Composio is an AI-agent tool-integration platform: OAuth connections for apps (Gmail, GitHub, Instagram, X/Twitter, Slack…) exposed as tools an agent can execute. The CLI is the agent's local tool surface: connect apps, execute tools, proxy authenticated APIs.

## Install (v3 CLI — the ONLY current one)

```bash
curl -fsSL https://composio.dev/install | bash   # installs to ~/.composio/composio
export PATH="$HOME/.composio:$PATH"              # installer also appends to ~/.bashrc
composio --version                               # expect 0.3.x (v3)
```

- Installs a large (~120MB) self-contained `@composio/cli` binary.
- After install, `which composio` MUST resolve to `~/.composio/composio`. Any older `composio` symlink earlier in PATH (e.g. `~/.local/bin/composio` left by a previous pip install) shadows it — delete the stale symlink and re-check.

## Login — give the user an OAuth link

```bash
composio login --no-wait          # prints https://dashboard.composio.dev/?cliKey=<uuid> — send this URL to the user (valid ~10 min)
composio login --poll             # run in background; completes automatically once the user clicks the URL
```

- No human available: `composio login --agent` signs in with a Composio agent account, no browser.
- `--no-skill-install` skips auto-installing the composio-cli skill into Claude Code.
- Login state lives in `~/.composio/` (config.json / user_data.json). `"api_key": null` in user_data.json = never logged in.

## Connect apps & run tools

```bash
composio link <app>                     # OAuth-connect an account (gmail, instagram, twitter, github…)
composio link <app> --no-browser --no-wait   # HEADLESS (VPS/server): prints the connect URL and exits instead of opening a browser and hanging
composio search "<natural language>"    # find tools
composio execute <TOOL> --get-schema    # inspect schema
composio execute <TOOL> -d '{...}'      # run a tool
composio proxy <provider-url> --toolkit <app>   # call provider API with Composio-managed auth
composio run '<inline TS>'              # multi-step scripted workflow (execute/search/proxy injected)
composio connections list --toolkit <app>   # per-toolkit status (INITIALIZING → ACTIVE); use this to poll a link the user just clicked
```

- **On a headless box, `composio link <app>` without flags hangs** (tries to open a browser). Always use `--no-browser --no-wait`; it prints `{"redirect_url": "https://connect.composio.dev/link/lk_..."}` — send that URL to the user. Poll `composio connections list --toolkit <app>` until status is `ACTIVE` before executing tools; `INITIALIZING` + execute → `ToolRouterV2_NoActiveConnection`.
- **Big tool results are written to a file, not stdout**: `composio execute` returns `{"storedInFile": true, "outputFilePath": "/tmp/composio/adhoc_*/<TOOL>_OUTPUT_*.json"}`. Parse that JSON file — the payload is `data` (e.g. Gmail: `data.messages[]`). The tool's stdout itself is not the result.
- Tool schemas are cached at `~/.composio/tool_definitions/<SLUG>.json` — read `inputSchema` there instead of calling `--get-schema` every time.

## Gmail-specific (hit in practice — full recipe in references/gmail-email-summary.md)

- `GMAIL_FETCH_EMAILS` query uses Gmail search syntax (`after:YYYY/MM/DD before:YYYY/MM/DD from:x`); `before:` is exclusive. `max_results` caps ~500/call; paginate with `page_token` ← `nextPageToken` from the previous result. `resultSizeEstimate` is NOT the pagination source of truth.
- Message shape: `messageId`, `messageTimestamp` (ms epoch), `sender`, `subject`, `preview`, `labelIds`, `threadId`. `preview` can be a dict — coerce with `str()`/`json.dumps` before slicing.
- **Scope limitation: `GMAIL_CREATE_FILTER` (blocking a sender) requires the `gmail.settings.basic` scope, which the standard `composio link gmail` grant does NOT include → HTTP 403 `insufficient scopes`.** Do not burn cycles retrying; tell the user the workaround: Gmail UI → open email → ⋮ → Block sender, OR accept the connection only covers read/modify.
- **`GMAIL_BATCH_MODIFY_MESSAGES` DOES work** (needs only `gmail.modify`, which the default grant includes): `{"messageIds": [...], "addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX","UNREAD"]}` moves up to 1000 existing messages to Spam. It silently skips invalid IDs — a typo'd ID is silently dropped, so verify afterwards with `GMAIL_FETCH_EMAILS 'from:x in:spam'`.

## Instagram-specific (hit in practice — full recipes in references/instagram-comment-engagement.md, references/instagram-engagement.md, references/instagram-hashtag-diet.md, references/instagram-music-limits.md)

- Comment-engagement toolchain: `INSTAGRAM_GET_IG_USER_MEDIA` (latest posts), `INSTAGRAM_GET_IG_MEDIA_COMMENTS`, `INSTAGRAM_POST_IG_MEDIA_COMMENTS` (top-level comment), `INSTAGRAM_POST_IG_COMMENT_REPLIES` (≤300 chars), `INSTAGRAM_GET_IG_COMMENT_REPLIES`, `INSTAGRAM_DELETE_COMMENT`.
- **CRITICAL: the media-comments list includes the account's OWN comments AND nested replies** (items carry `parent_id` when nested; own comments carry your username). An idempotent reply loop MUST filter out `parent_id` items AND own-username items, or it will reply to its own self-question/replies. This bit live: the loop replied to its own reply (placeholder "@friend" got posted) — cleanup was `INSTAGRAM_DELETE_COMMENT` + re-post.
- `username` can be `None` from the API — never interpolate `@username` when it's null; keep separate templates with/without `{user}` so `@friend`-style artifacts never go live.
- Idempotency + state: track per-media state (`media_id → {self_comment_id, replied_comments[]}`) so each loop run posts ONE self-question and replies to each comment exactly once. **Dry-run must NOT write state** — a dry-run that persisted state made the next real run skip every reply.
- `limit` params are INTEGERs — passing a string `"5"` fails schema validation.
- Tool schemas are cached at `~/.composio/tool_definitions/<SLUG>.json` — read `parameters.properties` there instead of `--get-schema` each time.
- Media/comment IDs are long numeric strings (~17 digits): a typo yields `IGApiException code 100 "Object with ID does not exist"`. Always read IDs from a GET response, never retype from memory.
- **Hashtags in captions: pass literal `#` — do NOT HTML-URL-encode `%23`.** Verified live: Meta docs say to encode, but composio execute sends a JSON body and the account's captions render literal `#` fine. See references/instagram-hashtag-diet.md for the full rotation/tiering recipe.
- **Licensed music on stories is impossible via API** — the app's music sticker is native-app only; the only audio field is `audio_name` (labels your original audio). No scheduler can attach a licensed track. Baked-in copyrighted audio gets muted by IG fingerprinting. See references/instagram-music-limits.md (what's IMPOSSIBLE) and references/instagram-reels-audio-sourcing.md (the pipeline is BUILT & LIVE since Aug 2026: user-supplied MP3s in `music/` are the primary source — archive.org Kevin MacLeod CC-BY mechanics verified but the user REJECTED it; Pixabay has NO music API. Reels = `media_type:"REELS"` + `video_file`, published by the 18:00 cron `7a4c465fbd09` via `scripts/reel_post.py`, **no image fallback** — parallel post, not a switch).

## Pitfalls (all hit in practice — see references/pitfalls.md for transcripts)

1. **PyPI `composio-core` is the LEGACY v2 SDK** (0.7.x, as of mid-2026). Its CLI hits deprecated endpoints: `composio login` fails with `{"error":"This endpoint is no longer available. Please upgrade to v3 APIs."}` and API-key validation returns **HTTP 410 Gone**. Do not install it for CLI use.
2. **npm `composio` (1.0.0) is a "hello world" stub** — 114-byte index.js, no binary in package.json. Not the real CLI.
3. **A stale `COMPOSIO_API_KEY` env var poisons the CLI** — it gets picked up and validated against dead endpoints, and `composio login` warns about it. `composio whoami` echoes the key; never paste it into chat.
4. **Docs site (docs.composio.dev) is client-rendered**: plain curl returns nav-only HTML. Append `.md` to any docs URL (Mintlify) to get raw Markdown: `curl https://docs.composio.dev/docs/cli.md`.
5. **EXPIRED connections are only a problem when the one you rely on is EXPIRED**: `composio connections list --toolkit <app>` can show several EXPIRED stale connections alongside an ACTIVE primary (e.g. old Instagram grants) — that's healthy, don't re-auth or chase the stale ones. A health script must check the specific `word_id` it uses, not "any ACTIVE". If the primary flips EXPIRED, generate a fresh link (`composio link <app> --no-wait`) and send it to the user.
