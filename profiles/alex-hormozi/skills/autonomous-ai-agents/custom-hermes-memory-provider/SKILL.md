---
name: custom-hermes-memory-provider
description: "Use when building a custom Hermes memory provider plugin."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, plugins, memory, memory-provider, gbrain, backend-integration]
    related_skills: [hermes-agent]
---

# Custom Hermes Memory Provider Plugin

## When to Use

- User asks to connect a second brain / knowledge base / memory backend to Hermes as its memory provider (gbrain, Notion, a vector DB, an API-backed memory service, etc.).
- User asks why a memory provider plugin is (not) being discovered, loaded, or active.
- User wants an existing provider's recall, capture, mirroring, or backup behavior extended.

Produces a drop-in plugin under `$HERMES_HOME/plugins/<name>/` that the `MemoryProvider` ABC discovers and `memory.provider` activates. Proven on this box: the gbrain provider at `/root/.hermes/plugins/gbrain/` (per-turn hybrid recall + capture, active in production).

## How discovery works (critical)

- **Locations scanned** (bundled first, bundled wins name collisions):
  1. `plugins/memory/<name>/` — shipped with hermes-agent (bundled)
  2. `$HERMES_HOME/plugins/<name>/` — user-installed (resolve via `get_hermes_home()`, never hardcode `~/.hermes`)
- **Discovery heuristic** (`plugins/memory/__init__.py`): the plugin's `__init__.py` must contain `"register_memory_provider"` or `"MemoryProvider"` in its first 8192 chars — cheap text scan, no import.
- **Two acceptable load patterns** (`_load_provider_from_dir`):
  - `register(ctx)` function calling `ctx.register_memory_provider(provider)` — the plugin-style pattern, preferred.
  - A top-level `MemoryProvider` subclass — auto-instantiated as fallback.
- **Relative imports inside the plugin work** (submodules in the same dir are pre-registered; user plugins load under a synthetic `_hermes_user_memory.<name>` namespace).
- **Only ONE external provider active at a time**, selected via `memory.provider` in config.yaml. Built-in MEMORY.md/USER.md is always active alongside.
- Optional `plugin.yaml` (name, version, description) — description is surfaced in `hermes memory setup` and `hermes doctor`; `cli.py` with `register_cli(subparser)` adds a `hermes memory <name>` subcommand.

## Build workflow (numbered)

1. **Scaffold the plugin dir**
   ```bash
   mkdir -p "$HERMES_HOME/plugins/<name>"
   cd "$HERMES_HOME/plugins/<name>"
   ```
   Write `plugin.yaml` (name/version/description) and `__init__.py` from `templates/provider_template.py`.

2. **Implement the ABC contract** (`agent/memory_provider.py` — read it first if adding optional hooks). Core (abstract): `name`, `is_available()`, `initialize(session_id, **kwargs)`, `get_tool_schemas()`. Everything else is optional, override to opt in:
   - `system_prompt_block()` → static instructions injected into the system prompt
   - `prefetch(query, *, session_id="")` → recall block injected before each turn (return formatted text or "")
   - `queue_prefetch(query, ...)` → background recall for next turn (default no-op)
   - `sync_turn(user, asst, *, session_id, messages)` → persist a completed turn (keep non-blocking)
   - `handle_tool_call(name, args)` → must return a JSON string; raise NotImplementedError for unknown tools
   - `shutdown()` → flush/close
   - `on_memory_write(action, target, content, metadata)` → mirror built-in memory tool writes into your backend
   - `on_session_end(messages)`, `on_session_switch(new_id, ...)`, `on_pre_compress(messages)`, `on_delegation(task, result, ...)`
   - `get_config_schema()` + `save_config(values, hermes_home)` → fields for `hermes memory setup` (schema fields: key, description, secret, required, default, choices, type, minimum, maximum, step, url, env_var). MUST implement one of: native-file `save_config()`, OR env-var-only fields with `env_var` set.
   - `backup_paths()` → absolute paths OUTSIDE `$HERMES_HOME` that `hermes backup` must capture (state dirs like `~/.gbrain`). Must be callable before `initialize()`.

3. **Know the `initialize()` kwargs contract**:
   - Always: `hermes_home` (profile-scoped path — use it), `platform` ("cli", "telegram", "discord", "cron", ...).
   - Maybe: `agent_context` ("primary" | "subagent" | "cron" | "flush"), `agent_identity`, `agent_workspace`, `parent_session_id`, `user_id`, `user_id_alt`.
   - **Writability gate**: only `"primary"` and `"flush"` contexts should write — cron/subagent system prompts would corrupt user representations. Store `self._writable = agent_context in ("primary", "flush")` and short-circuit writes when False.

4. **Beware the trivial-prompt gate**: `agent/memory_provider.py` has `TRIVIAL_PROMPT_RE` / `is_trivial_prompt()` — one-word replies ("yep", "hi", "ok") and slash commands SKIP provider prefetch entirely. Don't debug a missing recall block on trivial turns; test with a substantive query.

5. **Prefer shelling out over SDKs**: a subprocess to the backend's own CLI (`_run()` helper) avoids dependency pain and keeps `is_available()` a pure file/binary existence check — it must NOT make network calls (called during agent init, decides activation).

6. **Activate**:
   ```bash
   hermes memory setup        # interactive picker, walks get_config_schema() fields
   # or non-interactive:
   hermes config set memory.provider <name>
   ```

7. **Verify**:
   ```bash
   hermes memory status       # shows active provider
   hermes doctor              # checks provider loaded + available
   hermes chat -q "check <backend> for X"   # observe GBRAIN RECALL-style block in reply / logs
   ```
   Confirm recall fires on a substantive query, capture lands in the backend (query it directly), and that `hermes backup` includes any `backup_paths()`.

## Pitfalls

- `is_available()` must be side-effect-free and fast — it runs at every agent init and during `discover_memory_providers()`.
- STDERR/noise from the backend CLI (`UPGRADE_AVAILABLE` lines, version banners) will corrupt recall parsing — filter them in `_format()` before scanning for `[score] slug -- title` hits.
- `handle_tool_call()` results must be valid JSON strings — the model parses them.
- If your backend goes down, return a graceful fallback (`{"error": ...}` or empty list), never raise out of the tool call.
- One-provider limit: activating a new provider silently replaces the old — check `hermes memory status` when behavior changes.
- Don't put secrets in `plugin.yaml` or `save_config` (save_config receives only non-secret values; secrets go to `.env` via `env_var`).
- User-installed plugin dirs are scanned for ALL plugins — a non-provider plugin's `__init__.py` mentioning "MemoryProvider" in a comment would be misdetected, so keep unrelated plugins' init files clean.
- Provider module imports `from agent.memory_provider import MemoryProvider` and `from hermes_cli.config import cfg_get` — these live in hermes-agent's own runtime, no pip install needed.

## Reference: gbrain (production example)

Full working provider: `/root/.hermes/plugins/gbrain/` — `__init__.py` (GBrainProvider), `plugin.yaml`. Notable choices:
- recall = `gbrain query "<msg>" --limit N` with `search` fallback; block formatted as `GBRAIN RECALL (query: ...):` with `- slug: title` bullets
- capture = `gbrain capture "[hermes:<target>] <content>" --quiet --json` (mirrors memory tool writes)
- backups: `backup_paths()` returns `[self._dir]` so `~/.gbrain` rides along in `hermes backup`
- `on_memory_write` gated by `self._writable` (the agent_context gate from step 3)