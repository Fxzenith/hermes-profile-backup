# Skill → Slash Command Registration — Source Map

Grounded in hermes-agent **v0.20.0** (install dir `/usr/local/lib/hermes-agent/` on this box).
Internals shift between versions — re-grep the installed tree before trusting details:

- `hermes_cli/commands.py`
  - `COMMAND_REGISTRY` — built-in commands only. Skills are NOT in this list; they are registered dynamically.
  - `_collect_gateway_skill_entries(platform, max_slots, ...)` — builds gateway slash menus: Tier 1 = plugin slash commands (never trimmed), Tier 2 = built-in skill commands (trimmed at the remaining slot cap, alphabetical). Telegram description cap 40 chars, Discord 100. Excludes `~/.hermes/skills/.hub/` skills and per-platform disabled skills (`get_disabled_skill_names(platform=...)`).
- `agent/skill_commands.py`
  - `scan_skill_commands()` — scans `~/.hermes/skills/` + `skills.external_dirs`; builds `_skill_commands` keyed by `cmd_key = f"/{cmd_name}"`.
  - `get_skill_commands()` — cached; re-scans ONLY when the cache is empty or the platform scope changed (`_resolve_skill_commands_platform()`). This is why a skill created mid-gateway-run silently 404s until `/reload-skills` or restart.
  - `resolve_skill_command_key(command)` — `f"/{command.replace('_', '-')}"`; the `_` → `-` normalization.
  - Dispatch path — when `/name` resolves, injects something like `[IMPORTANT: The user has invoked the "<name>" skill, indicating they want ...]` plus the remaining instruction text after the command.
  - `reload_skills()` — on-demand re-scan (`/reload-skills`); does NOT invalidate the skills system-prompt cache, so prefix caching survives.
- `hermes chat -q` one-shots are fresh processes — every call re-scans, no reload needed.
- `hermes skills list` reads disk (name/category/scope/status) — usable as verification from any session.