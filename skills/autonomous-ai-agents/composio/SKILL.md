---
name: composio
description: Composio CLI setup, install, OAuth login link, connect apps.
---

# Composio CLI setup, login & connections

Composio gives agents tool access to third-party apps (Gmail, GitHub, Slack, …) with hosted OAuth. The CLI has TWO generations — know which one you're on:

| | Legacy (dead) | New (current) |
|---|---|---|
| Install | `pip install composio-core` | `curl -fsSL https://composio.dev/install \| bash` |
| Version | 0.7.21 (PyPI frozen here — no newer pip release) | 0.3.x compiled binary |
| Binary | venv script, e.g. `~/.venvs/composio/bin/composio` | `~/.composio/composio` (installer puts `~/.composio` first on PATH) |
| Backend | `backend.composio.dev/api/v1/*` — **decommissioned** | v3 APIs |

## Install (headless server)

```bash
# Inspect first, then run — it's a GitHub-release downloader with checksum verify
curl -fsSL https://composio.dev/install -o /tmp/composio_install.sh
bash /tmp/composio_install.sh --no-plugins   # --no-plugins skips Claude Code plugin probing
```

## Login (the OAuth link flow)

1. `composio login --no-wait --no-skill-install` → prints a one-time URL:
   `https://dashboard.composio.dev/?cliKey=<uuid>` (valid ~10 min)
2. Send that URL to the user to open in their browser and authorize.
3. Start `composio login --poll` (background + notify_on_complete) so login completes automatically the moment the user clicks. Do NOT ask the user whether to poll — they already requested login.
4. Verify: `composio whoami` (empty output = not logged in).
5. Alternative for unattended agents: `composio login --agent` (creates a Composio agent account, no browser).

## Connect app accounts

- `composio link <app>` → generates a **Connect Link** like `https://connect.composio.dev/link/ln_abc123` that the user opens to authorize the app. Credentials never pass through your machine.
- **Headless pitfall:** plain `composio link <app>` opens a browser and WAITS — on a headless server it hangs until timeout. Use `composio link <app> --no-wait` (prints `redirect_url` + `connected_account_id` as JSON and exits instantly) or `--no-browser`. `--alias <name>` is required for a 2nd+ account on the same toolkit.
- `composio search "<natural language>"` — find tools; `composio execute <TOOL_SLUG> -d '{...}'` — run a tool; `composio proxy <provider-url> --toolkit <tk>` — call a provider API with Composio-managed auth.
- `composio execute <SLUG> --dry-run -d '{...}'` validates args + connection without executing — cheap pre-flight before wiring anything automated.
- **File uploads & parsing `execute` output:** see `references/execute-file-upload-and-parsing.md`. Two recurring gotchas: (1) `--file <path>` only works when the tool has a SINGLE `file_uploadable` input — with two (e.g. Instagram's `image_file` + `video_file`) the CLI errors and you must pass the path explicitly in `-d` as the field key; (2) `execute` stdout is usually clean JSON but banner/error paths prepend prose that can contain braces, so parse by walking `{`-suffixes, never `rfind("{")`.

## Inspect connected accounts

- **Instagram posting end-to-end:** a complete single-image post recipe (create-container → publish with `image_file`, resolve the Creator/Business account, handle error codes 9007 / code 9 / permanent-auth fast-fail, and the `storedInFile` large-payload gotcha) is verified in `references/instagram-posting-execute.md`.

- The working subcommand is `composio connections list` (optionally `--toolkit <tk>` for one app). It returns JSON keyed by app name with `status` ACTIVE/EXPIRED, `alias`, and the account `word_id`.
- **`composio connected-accounts` returns nothing, and `composio connected` errors with "Invalid subcommand for composio — use one of 'version', 'upgrade', ..., 'connections', ...".** The verb is `connections`, not `connected` — don't guess.

## Pitfalls

1. **Legacy v1 backend is gone.** Any request to `backend.composio.dev/api/v1/*` returns `HTTP 410 "This endpoint is no longer available. Please upgrade to v3 APIs."` — including old-CLI API-key validation and `composio login`. The old pip CLI is unusable, period; install the binary CLI instead. See `references/legacy-v1-to-v3-migration.md`.
2. **410 is endpoint-wide, not key-specific.** Before blaming the API key, probe: `curl -s -o /dev/null -w '%{http_code}' https://backend.composio.dev/api/v1/client/auth/client_info` with no key / garbage key — if those also 410, the endpoint (not the key) is dead.
3. **PyPI has no upgrade path.** `composio-core` is frozen at 0.7.21; `pip install -U` changes nothing.
4. **Stale `COMPOSIO_API_KEY` env var** may hold a dead legacy key. `unset COMPOSIO_API_KEY` before running the new CLI (the new CLI ignores it, but it can shadow/confuse state checks).
5. Old CLI's `composio --help` crashes with a traceback (click help-format bug) — don't use it for command discovery; use `composio <cmd> --help` or just upgrade.
6. Docs moved: `docs.composio.dev/cli/*` is 404 → use `docs.composio.dev/docs/*` (cli, authentication, migration-guide). Plain `curl -sL` works on the docs (web tools may be down); strip tags with python/regex to read them.

## Verification checklist

- [ ] `~/.composio/composio --version` reports 0.3.x
- [ ] `composio whoami` shows a session (not empty)
- [ ] `composio link <app>` yields a `connect.composio.dev/link/...` URL
