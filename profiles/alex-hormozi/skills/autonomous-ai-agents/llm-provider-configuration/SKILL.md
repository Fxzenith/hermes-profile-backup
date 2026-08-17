---
name: llm-provider-configuration
description: Configure LLM providers, manage API keys, model picker.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, providers, api-keys, models, configuration, troubleshooting]
    related_skills: [hermes-agent]
---

# LLM Provider Configuration

## Overview
Hermes Agent supports 35+ provider profiles. This guide covers adding API keys, custom providers, alias resolution, and troubleshooting visibility in the model picker.

## Adding Providers

### Built-in Providers
Use `hermes auth add <provider>` or set environment variables:
- `OPENROUTER_API_KEY`
- `ANTHROPIC_API_KEY`
- `OPENCODE_ZEN_API_KEY`
- `GOOGLE_API_KEY`
- etc.

### Non-interactive API key setup (agent sessions, cron, CI)
Bare `hermes auth add <provider>` prompts for the key via getpass and FAILS when
there is no TTY (agent terminal calls, cron, pipes) with `EOFError` /
`termios.error: Inappropriate ioctl for device`. Do NOT fight the prompt. Two
headless-safe paths:

- **Preferred: pass the key inline** — `hermes auth add <provider> --type api-key --api-key "$KEY" --label my-key-1`
  stores the credential in the pool (`~/.hermes/auth.json`) with NO prompt — works
  from cron, agents, and CI. Repeat calls ADD more credentials (multi-key pool,
  see "Credential Pools" below).
- Fallback: write the key to `~/.hermes/.env` as `<PROVIDER>_API_KEY=...` (or export it
  in the session — exported env vars persist across terminal calls).

Verify with `hermes auth status <provider>` (expect "logged in") and
`hermes auth list <provider>` (shows the credential pool + which env var feeds it).
Smoke-test with `hermes chat -q "Hello" --provider <provider>`.

Pitfalls:
- `hermes auth status` REQUIRES the provider arg — bare `hermes auth status` is a usage error.
- `read_file` on `~/.hermes/.env` is blocked by secret redaction (defense in depth);
  write with terminal/write_file, verify via `hermes auth` commands.
- A key added to `.env`/env var shows up as `env:VARNAME` in `hermes auth list`.
- See `references/opencode-zen.md` for OpenCode Zen specifics (base URLs, model routing).

### Custom Providers
Define in `config.yaml` under `providers:`:

```yaml
providers:
  my-proxy:
    name: "My Proxy"
    api: "https://proxy.example.com/v1"
    key_env: "MY_PROXY_KEY"
    transport: "openai_chat"
```

Then use `--provider my-proxy` or `/model my-proxy`.

## Provider Aliases

Hermes maps aliases via `ALIASES` in `providers.py`. Common mappings:

- `opencode-zen` → `opencode`
- `zen` → `opencode`
- `openai` → `openrouter`
- `grok` → `xai`
- `nim` → `nvidia`
- `kimi` → `kimi-for-coding`
- `copilot` → `github-copilot`
- `hf` → `huggingface`

Use canonical names in commands.

## Model Picker Visibility

If a provider is configured but missing from `hermes model`:

1. Verify provider entry in `HERMES_OVERLAYS` (in `hermes_cli/providers.py`).
2. Ensure `opencode` has `is_aggregator=true` but is not a routing aggregator; its models are first‑party.
3. Check for label overrides in `_LABEL_OVERRIDES`. Add a friendly name if desired.
4. Remember the picker may show providers under a DIFFERENT name than the one you
   authenticated with: `hermes auth add opencode-zen` stores under `OPENCODE_ZEN_API_KEY`,
   but the canonical provider id is `opencode` (alias table maps `opencode-zen` → `opencode`).
   Search the picker for `opencode`, not `opencode-zen`.
5. Use `hermes config edit` to add the provider under `providers:` for reliable visibility.
6. Restart Hermes or run `hermes doctor --fix` to refresh the picker.

## Credential Pools (multi-key rotation)

One provider can hold MULTIPLE credentials; Hermes auto-rotates across them.
This is the native answer to "one key keeps hitting rate limits" — better than
cron key swapping: no process restarts, zero downtime, and burst traffic splits
across keys (rotation trigger = per-request round-robin vs on-exhaustion —
verify empirically, they may differ by provider).

- Add more keys: `hermes auth add <provider> --api-key "$KEY2" --label key-2` (repeat; each call appends).
- Inspect pool: `hermes auth list <provider>` — env-fed entries show as `env:VARNAME`.
- Raw store: `~/.hermes/auth.json` → `credential_pool.<provider>` array. Fields:
  `label`, `source` (`env:VARNAME` vs stored), `base_url`, `priority`,
  `request_count`, `secret_fingerprint`, `last_status` / `last_error_*`.
- Prove rotation really happens: snapshot `request_count` per credential, fire
  several provider calls (`hermes chat -q ping --provider <provider> ×N`), re-read
  counters — ALL should move:
  `jq -r '.credential_pool.<provider>[] | [.label, .request_count] | @tsv' ~/.hermes/auth.json`
- Key exhaustion: pool auto-marks it (fields populate); `hermes auth reset <provider>`
  clears exhaustion state; `hermes auth remove <provider>` drops a credential by index/id/label.

**"Which key is actually in use?" — diagnose in this order:**
1. `hermes auth list <provider>` — shows `env:VARNAME` credentials.
2. `~/.hermes/.env` — the gateway loads THIS file, so an env-fed entry there WINS
   over shell exports. Check `.env` BEFORE `~/.bashrc`. A different `XXX_API_KEY`
   exported in `.bashrc` feeds shell-launched tools only (e.g. gbrain embeddings).
3. `~/.hermes/auth.json` credential_pool entry — `source`, `base_url`, `secret_fingerprint`.
Compare key prefixes with masked greps (e.g. `grep -o 'KEYPREFIX-[A-Za-z0-9_-]\{8\}' file`)
and match on prefix — never echo full secrets (`.env` reads are redaction-blocked anyway).

## Verification

```bash
hermes auth status opencode-zen
hermes chat -q "test" --provider opencode
hermes config get model.default model.provider
```

## References

- `references/providers-and-models.md` (hermes-agent skill)
- `references/provider-aliases.md` (full alias table)
- `references/troubleshooting-visibility.md` (model picker visibility guide)