# Composio setup failure modes (verified 2026-07)

## 1. Legacy pip CLI → dead v2 endpoints

Installed `pip install composio-core` (0.7.21, latest on PyPI at the time). Symptoms:

- `composio whoami` echoes the env API key without validating it.
- `composio connections` → traceback ending `composio.exceptions.ApiKeyError: Unexpected error: HTTP 410` (validate_api_key hits a deprecated endpoint).
- `composio login` → `Error: {"error":"This endpoint is no longer available. Please upgrade to v3 APIs. "}` — even with `COMPOSIO_API_KEY` unset.

Root cause: PyPI composio-core 0.7.x targets the v2 API; the platform moved to v3 (sessions model). Fix: install the real CLI via the curl installer (see SKILL.md). Also note the pip install hits PEP 668 on Ubuntu 24.04+ — use a venv or pipx.

## 2. npm `composio` is a placeholder stub

`npm install -g composio` → version 1.0.0, but package.json has no `bin` entry and index.js is:

```js
console.log("hello world");
```

Squatted stub, not the real CLI. Uninstall it.

## 3. PATH shadowing

After pip-installing the legacy CLI, the `~/.local/bin/composio` symlink shadows the new `~/.composio/composio` binary even after the real install. Fix: `rm -f ~/.local/bin/composio`, then re-check `which composio` resolves to `~/.composio/composio`.

## 4. Dead API key in env

`COMPOSIO_API_KEY` set in environment (23 chars, `ak_C…` prefix) but rejected with HTTP 410 → key invalid/revoked, or endpoint deprecated. The env key also makes `composio login` print `WARNING: COMPOSIO_API_KEY Environment variable is set` and short-circuit into the failing validate path. The `--no-wait` URL flow bypasses the env key. `~/.composio/user_data.json` containing `{"api_key": null}` = never logged in.

## 5. Login URL flow (the working path)

```bash
composio login --no-wait --no-skill-install
# →
# Open this URL in your browser to log in:
#   https://dashboard.composio.dev/?cliKey=<uuid>
# Then run this command to complete login:
#   composio login --poll
```

Run `--poll` in a background process (polls up to 10 min, exits once credentials are saved). CLI hint text explicitly says: show the URL to the user, run the poll command, don't ask the user whether to poll. For unattended/agent use, `composio login --agent` signs in with a Composio agent account without a browser.

## 6. Docs are Mintlify — fetch raw markdown

docs.composio.dev renders client-side; `curl` of any page returns nav-only HTML with empty main content. Append `.md` to the URL to get raw Markdown: `curl https://docs.composio.dev/docs/cli.md`. This works for any Mintlify docs site.
