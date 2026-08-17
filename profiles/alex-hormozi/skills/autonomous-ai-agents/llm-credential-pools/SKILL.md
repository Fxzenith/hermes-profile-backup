---
name: llm-credential-pools
description: "Use when rotating LLM API keys across providers."
version: 1.0.0
author: Hermes Agent (curator)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, providers, api-keys, rate-limits, credential-pool, rotation]
    related_skills: [llm-provider-configuration, hermes-agent]
---

# LLM Credential Pools (multi-key rotation in Hermes)

Use when a provider's single API key keeps hitting rate limits and the user wants
multiple keys to share load or fail over — "rotate the keys", "one key rests while
the other works", "add my second key", "which key is actually being used?".

Hermes has a **native credential pool** per provider: multiple keys, automatic
selection, automatic exhaustion/cooldown. No cron, no gateway restarts, no .env
rewrites. This skill covers the operational mechanics and — critically — how to
prove rotation is really happening (CLI smoke tests can't).

## The mechanism (all verified against hermes-agent 0.20.0 source)

- Pool state lives in `~/.hermes/auth.json` under `credential_pool.<provider>` — an
  array of entries: `{id, label, auth_type, priority, source, base_url, request_count,
  last_status, last_error_*, secret_fingerprint}`. `source` is `env:VARNAME` (key fed
  from an env var / `.env`) or `manual` (key stored in auth.json).
- Keys come from `~/.hermes/.env` / env vars OR are stored via `hermes auth add`.
  `hermes auth list <provider>` shows which is which; `hermes auth status <provider>`
  confirms the provider is logged in.
- Exhaustion handling is built in: on transient failures (429 rate limit, 402) the
  selected entry is marked exhausted and the pool rotates; `hermes auth reset
  <provider>` clears exhaustion state. Permanent OAuth-terminal 401s are treated
  differently (see `credential_pool.is_terminal_auth_failure`).

## Adding a key to the pool (headless-safe)

`hermes auth add <provider> --api-key "$KEY" --label "<descriptive-label>"` works
non-interactively (no TTY needed, unlike the prompt-only path). Always verify the
key with a direct curl first — a dead key in the pool wastes rotation slots:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $KEY" \
  https://integrate.api.nvidia.com/v1/models   # nvidia example; expect 200
```

## Rotation strategies

Default is **`fill_first`**: entry #1 serves everything until it's exhausted, then
the next entry takes over (failover + cooldown, but NO load sharing). To actually
split load, set a strategy in config.yaml:

```bash
hermes config set credential_pool_strategies.<provider> round_robin
```

| Strategy | Behavior | Persists to auth.json? |
|---|---|---|
| `fill_first` (default) | use #1 until exhausted, then next | no (only on exhaustion) |
| `round_robin` | rotate per select; rewrites priorities | yes, on every select |
| `least_used` | pick min request_count, increment in memory | no (in-memory only) |
| `random` | random pick | no |

Strategy is re-read from config on **every** `load_pool()` call → a config change
applies immediately, no gateway restart needed.

## PITFALL: CLI smoke tests do NOT exercise the pool

`hermes chat -q "..." --provider nvidia` (and the oneshot/runtime-provider path
generally) only uses the credential pool for `openrouter`/`auto` providers
(`runtime_provider.py`: `should_use_pool = requested_provider in {"openrouter",
"auto"} and not has_custom_endpoint and not has_runtime_override`). For every other
provider it resolves the env-var key directly and the pool is never touched — so
counters/priorities in auth.json stay frozen and you will wrongly conclude the pool
is broken.

The real consumers of the pool are:
- the agent runtime (`agent._credential_pool`, `pool.select()` per turn),
- auxiliary clients, e.g. the vision aux model (`auxiliary_client._select_pool_entry`
  → `load_pool(provider).select()`).

## Verifying rotation actually works

Use the in-process probe in `scripts/verify_pool_rotation.py` — it drives the exact
same `load_pool()` + `select()` path the aux clients use:

```bash
cd /usr/local/lib/hermes-agent          # hermes source dir (editable install)
venv/bin/python ~/.hermes/skills/autonomous-ai-agents/llm-credential-pools/scripts/verify_pool_rotation.py nvidia 6
```

Expected with `round_robin` + 2 keys: picks alternate (KEY-A → KEY-B → KEY-A → …)
and the persisted priority order in auth.json flips every select. With `fill_first`,
every pick is entry #1.

## Pitfalls & notes

- Never hand-edit `auth.json` or `config.yaml` — use `hermes auth add` /
  `hermes config set`.
- A key that is ALSO exported in `~/.bashrc` (e.g. for shell tools/gbrain) and added
  to the pool is fine — pool `manual` entries are independent of shell env.
- OCR of base64 API keys is unreliable: always have the user paste the key text
  directly, never transcribe it from a screenshot.
- `request_count` persistence caveat: `least_used` increments in-memory only; expect
  frozen counters on disk for that strategy. `round_robin` is the observable one.
- nvidia provider defaults: base_url `https://integrate.api.nvidia.com/v1`, key env
  var `NVIDIA_API_KEY` (aliases: `nim` → `nvidia`).
- If a stored key becomes unusable: `hermes auth remove <provider> <id|label|index>`.

## Related

- `llm-provider-configuration` (bundled) covers provider setup/auth broadly; this
  skill is the multi-key pool mechanics + verification layer.