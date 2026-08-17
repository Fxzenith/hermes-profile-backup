---
name: gbrain-advisor-bot
description: Build a grounded RAG advisor bot over GBrain expert notes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gbrain, rag, advisor-bot, expert-council, note-taking]
    related_skills: [youtube-content, plan]
---

# GBrain Advisor Bot

Build a queryable "expert advisor" that answers / drafts / brainstorms strictly from
notes stored in GBrain (e.g. `experts/alex-hormozi/`), with an LLM synthesizing
grounded replies. Use for any expert in the Advisory Council pattern (Hormozi,
Naval, Munger, …), or any "ask the captured expert" use case.

## When to use
- User wants to "ask an expert" / draft / brainstorm grounded in GBrain notes.
- Turning a captured expert into a chat-able bot (CLI, in-profile skill, or Portal bot).
- Building low-cost assistants: free model + retrieval-only fallback if no key.

## Architecture (3 thin files)
1. `retrieval.py` — `gbrain query` + `gbrain get`, scoped to a slug prefix.
2. `llm.py` — POST to OpenAI-compatible `/chat/completions`; key from env var.
3. `bot.py` — argparse subcommands `ask` / `draft` / `brainstorm`.

## Critical gotchas (each has burned a session — read before coding)
- **gbrain needs PATH**: set `export PATH="$HOME/.bun/bin:$PATH"` in every
  subprocess env (gbrain is a bun CLI, not on default PATH).
- **gbrain query output format**: lines look like
  `[2.0000] experts/alex-hormozi/closer-framework -- expert: Alex Hormozi`.
  Parse slugs with:
  `gbrain query "$q" --limit 8 2>/dev/null | grep 'PREFIX/' | sed -E 's/^\[[^]]*\] +//' | awk '{print $1}'`
  A naive `awk '{print $1}'` grabs the SCORE, not the slug.
- **Hybrid search returns NOTHING for generic phrasing** ("email sequence for
  coaching" won't lexically match a note). When the literal query yields no slugs,
  fan out over framework vocabulary and merge: loop `offer`, `lead magnet`,
  `sales`, `pricing`, `value`, `focus`, `three pillar pitch`, `closer framework`,
  `cta formula`; take top 6; dedup with `sort -u`.
- **Free models are SLOW** (hy3-free via OpenCode Zen). Set `requests` timeout to
  180s and run long prompts in background (`terminal` background=true). A 3-email
  draft can take 3–5 min.
- **UPGRADE_AVAILABLE banner**: `gbrain` may print an upgrade notice to stdout —
  filter it (grep the slug prefix, not the whole line) before parsing.
- **Cross-profile writes**: editing another profile's skills/files from the default
  profile triggers a soft guard. Pass `cross_profile=True` to write_file, or use
  terminal. The target profile's own sessions supply its `.env` keys automatically.
- **Slash command = skill name**: a profile skill's `name` becomes its `/slash`
  trigger. Name it `hormozi` (not `hormozi-advisor`) so `/hormozi` fires it.
  Rebuild the skill snapshot if the rename isn't picked up.

## LLM endpoint (verified 2026-08-17)
- OpenCode Zen: base `https://opencode.ai/zen/v1`, model `hy3-free` (free, cost 0),
  OpenAI-compatible. Key env var `OPENCODE_ZEN_API_KEY`. Resolve from Hermes
  credential pool (`hermes auth add opencode-zen`) — never hardcode in source.
- Retrieval-only fallback: if key unset, print the raw retrieved notes.

## Grounding rules (MANDATORY in the system prompt)
1. Answer ONLY from retrieved notes. If uncovered, say so — don't invent quotes/stats.
2. Cite note slug: `[experts/alex-hormozi/closer-framework]`.
3. Mark application to the user's situation with `[inference]`.
4. Drafts cite which frameworks were applied; flag unsupported parts `[inference]`.
5. Never impersonate the expert with fabricated quotes/opinions.

## Hosted Portal bot (can't reach local GBrain)
For a Nous Portal BOTS-tab bot, export notes to one markdown file
(`gbrain export --slug-prefix experts/alex-hormozi --dir ./out`) + a persona system
prompt, then paste both into the Portal bot's config. Re-export to re-sync.

## Files / references
- `references/gotchas.md` — exact command snippets & the slow-model symptom.
- `templates/system_prompt.md` — copy-paste grounding system prompt.
- `templates/bot_files.md` — retrieval.py / llm.py / bot.py skeletons.
