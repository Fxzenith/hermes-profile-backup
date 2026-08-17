---
name: composio-cli-setup
description: Set up the agent-tools CLI and issue OAuth login links.
version: 0.1.0
author: Hermes
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Composio, CLI Setup, OAuth, Agent Tools]
---

# Composio CLI Setup & OAuth Connect

Installs and authenticates the current-generation Composio CLI (v0.3.x, a compiled binary installed to `~/.composio/composio`) and produces the OAuth link a human clicks to link their account. It does NOT manage app integrations end-to-end, does NOT handle `--user-api-key` auth, and does not fix apps already connected. The legacy pip CLI (`composio-core` 0.7.x) is dead — its v1 backend returns HTTP 410 — so this skill exists to detect and replace it.

## When to Use

- "Is composio configured?" / "Set up composio" / "Configure composio in /root"
- "Send me the OAuth link to connect composio"
- Errors like `HTTP 410`, "This endpoint is no longer available", "upgrade to v3 APIs"
- `composio whoami` prints a key but every real command tracebacks or 410s
- Generating a Connect Link for an app (`composio link github`)

## Prerequisites

- `curl`, `unzip`, `bash` on PATH (installer requirement)
- Network access to `github.com` (release download), `composio.dev`, `dashboard.composio.dev`
- A human available to click the OAuth link (for unattended setups use `composio login --agent` instead)
- The old `COMPOSIO_API_KEY` env var (if set) is legacy-only — `unset` it before login/poll commands

## How to Run

1. Check state through the `terminal` tool: `command -v composio`, `composio --version`, `composio whoami`.
2. If legacy (0.7.x) or missing, install the new CLI (see Procedure step 3).
3. Generate the login link: `composio login --no-wait --no-skill-install` — it prints `https://dashboard.composio.dev/?cliKey=<uuid>`.
4. Start `composio login --poll --no-skill-install` as a background `terminal` process with `notify_on_complete=true`; hand the URL to the user.
5. On completion, verify with `composio whoami` and `composio tools list github`.

## Quick Reference

```bash
composio --version                    # 0.3.1 = new-gen; 0.7.21 = legacy (dead backend)
composio whoami                       # account JSON; empty = not logged in
curl -fsSL https://composio.dev/install -o /tmp/composio_install.sh   # fetch installer
bash /tmp/composio_install.sh --no-plugins                            # install to ~/.composio/composio
composio login --no-wait --no-skill-install   # print login URL, exit
composio login --poll --no-skill-install      # complete login (polls cached key, ~10 min)
composio link <toolkit> --no-wait             # app OAuth Connect Link (connect.composio.dev/link/...)
composio connections list                     # connected accounts ({} = none)
composio tools list <toolkit>                 # e.g. github — proves backend auth works
```
Valid subcommands (v0.3.x): `version upgrade whoami login signup setup agent logout run proxy artifacts install tools triggers search link execute connections generate orgs config dev`.

## Procedure

1. **Check current state** via `terminal`: `command -v composio && composio --version`, then `composio whoami`. Also read `~/.composio/user_data.json` with `read_file` (legacy key lives here as `api_key`).
2. **Diagnose failures**: if commands return `HTTP 410` / "This endpoint is no longer available", confirm it is endpoint-wide, not key-specific: `curl -s -o /dev/null -w "%{http_code}" https://backend.composio.dev/api/v1/client/auth/client_info` — 410 with **no** key proves the v1 backend is decommissioned. Stop debugging the key.
3. **Install the new CLI**: fetch the installer with `curl -fsSL https://composio.dev/install -o /tmp/composio_install.sh`, skim it (it's a legit GitHub-release installer: `ComposioHQ/composio`), then run `bash /tmp/composio_install.sh --no-plugins` via `terminal`. `--no-plugins` skips agent-host plugin probing (right for headless). Binary lands at `~/.composio/composio` and the installer puts `~/.composio` first on PATH.
4. **Generate the OAuth link**: `composio login --no-wait --no-skill-install`. Capture the printed `https://dashboard.composio.dev/?cliKey=<uuid>`.
5. **Complete login in the background**: start `unset COMPOSIO_API_KEY; composio login --poll --no-skill-install` with `terminal` `background=true, notify_on_complete=true`. Send the user the URL; the poll saves credentials the moment they authorize.
6. **Verify**: `composio whoami` must return JSON (`email`, `current_org_name`), and `composio tools list github` must return real tool schemas (proves authenticated backend round-trip).
7. **Optional — app Connect Links**: `composio link <toolkit> --no-wait` prints `https://connect.composio.dev/link/...` for the user to authorize an app account; `composio connections list` shows what's connected.

## Pitfalls

- **Legacy CLI looks installed but is dead**: pip `composio-core` 0.7.x targets `backend.composio.dev/api/v1`, which is fully decommissioned (410 even with no key). Upgrade, don't troubleshoot.
- **Old 0.7.x `--help` tracebacks** on `composio` / `composio --help` (click formatting bug) — probe subcommands like `composio connections --help` instead; you can still see valid commands in the error line.
- **Login URL expires**: the `--poll` window is ~10 minutes from `--no-wait`. Start the poll immediately; if it lapses, re-run `--no-wait` for a fresh key.
- **`web_search`/`web_extract` may fail** with Firecrawl "Invalid token" — fall back to `curl` + `terminal` against `docs.composio.dev/docs/...`; `browser_navigate` can also time out on composio docs.
- **Docs moved**: old paths like `/cli/overview` 404; current docs live under `https://docs.composio.dev/docs/cli`, `/docs/authentication`, `/docs/migration-guide`.
- **Not a valid command**: `composio apps list` (use `tools list <toolkit>`), `composio connections` without a subcommand (use `connections list`).
- **`COMPOSIO_API_KEY` env var** is legacy; the new CLI stores credentials itself. Unset it for login/poll to avoid interference.

## Verification

`composio whoami` returns JSON with a real `email` and `current_org_name` — and `composio tools list github` returns non-empty tool schemas (not an error).
