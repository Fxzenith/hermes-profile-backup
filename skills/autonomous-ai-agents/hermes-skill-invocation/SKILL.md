---
name: hermes-skill-invocation
description: "Trigger Hermes skills as /slash commands on gateways."
version: 0.1.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [hermes, skills, slash-commands, gateway, verification]
    related_skills: [hermes-agent-skill-authoring]
---

# Hermes Skill Invocation

How installed user-local skills become `/slash` commands on gateway platforms (Telegram, Discord), how to make a brand-new skill live on a running gateway, and how to prove a skill works end-to-end from a clean session. Mechanics are grounded in hermes-agent v0.20.0 source — see `references/source-map.md` for the exact code locations and re-verify against the installed version when in doubt.

## When to Use

- User asks "how do I trigger this skill / what slash command do I use" right after a skill was created
- You just created or edited a user-local skill and it must be invocable on the live gateway
- A skill command 404s or is missing from the Telegram/Discord `/` menu
- You need to prove a new skill is self-contained and invocable exactly as the user will invoke it

## How Skills Become Slash Commands

- Every user-local skill (SKILL.md under `~/.hermes/skills/` with frontmatter `name`) auto-registers a gateway command. No registry edits, no config.
- Command key: `/<name>`, with underscores normalized to hyphens (`my_skill` → `/my-skill`).
- Text typed after the command becomes the skill's instruction: `/clipping https://youtu.be/... 2` dispatches the `clipping` skill with `https://youtu.be/... 2` as its task.
- `hermes skills list` is the ground-truth check that a skill is installed and enabled. Run it from any session — it reads disk, not the session cache.

## Making a New Skill Live on a Running Gateway

- The gateway **caches the skill-command map** at session/platform start; `get_skill_commands()` re-scans only when the cache is empty or the platform scope changes. A skill created AFTER the gateway started will NOT dispatch until one of:
  1. the user sends `/reload-skills` in the chat (re-scans the skills dir; does NOT invalidate the skills system-prompt cache — safe), or
  2. the gateway restarts.
- Tell the user plainly: "send `/reload-skills` once, then `/clipping <url> [n]` works."
- **CLI one-shots need no reload** — `hermes chat -q` is a fresh process that re-scans every call.
- `/` menu participation is separate from dispatch: `_collect_gateway_skill_entries()` fills remaining menu slots after core commands, alphabetical; Telegram truncates descriptions at 40 chars (Discord 100); hub-installed and per-platform-disabled skills are excluded from the menu.

## Verification — Fresh-Session Proof

The definitive test that a skill is self-contained and dispatchable:

```bash
terminal(command="cd /root && hermes chat -q \"/<skillname> <real args>\"", background=true, notify_on_complete=true)
```

- Runs the skill in a zero-context session through the real dispatch path; the skill's own artifacts (files, media) are the proof.
- Wait for the completion notification — do not poll. Pipelines (transcript → extract → render → export) take 10+ minutes.
- Why not test in the current session: this session's skill loader AND command map are cached at session start; a just-created skill is invisible to both (`skill_view` fails, `/name` 404s). Only a fresh process re-scans.

## Pitfalls

- Creating a skill and expecting it in THIS session's `skills_list`: won't appear until the next session — by design, not a bug.
- Assuming the gateway auto-picks-up new skills: it does not; `/reload-skills` or a restart is required.
- Underscores in skill names: the command uses hyphens — always quote the exact `/<name-with-hyphens>` form to the user.
- Telegram menu shows only commands registered at connect time; a skill created mid-gateway-run silently stays out of the menu until reload — say so instead of letting the user hunt for it.
- A fresh-session proof that never finishes is not proof: pipelines that hit an interactive `ENTER` gate hang forever headlessly — the skill must bypass prompt gates (run stages directly) or the proof will stall.
- Description velocity: keep skill descriptions ≤ ~57 chars so the trigger survives Telegram's 40-char menu truncation and the system-prompt index window.

## Verification Checklist

- [ ] `hermes skills list` shows the skill enabled
- [ ] User-facing command name stated as `/<name-with-hyphens>` with a concrete example including args
- [ ] `/reload-skills` told to the user if the gateway was running when the skill was created
- [ ] Fresh-session proof `hermes chat -q "/<name> <real args>"` produced the expected artifact