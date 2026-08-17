---
name: gbrain-rag-bot
description: RAG GBrain notes into a Hermes advisor profile or CLI bot.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [gbrain, rag, advisor-bot, profile, knowledge, retrieval]
    related_skills: [hormozi-advisor, plan, note-taking]
---

# GBrain RAG Advisor Bot

## When to use
- User wants to "ask an expert" / draft / brainstorm grounded in notes already stored in GBrain (e.g. `experts/alex-hormozi/`).
- Building a lightweight, low-cost assistant with no new DB or server.
- User has a Hermes *profile* acting as a named expert agent and wants it to answer from GBrain, not a flat file.
- User says "give it its own brain / use gbrain instead of markdown" for an advisor agent.

## Architecture (recommended: live RAG, NOT a markdown dump)
A Hermes profile's `workspace/` dir auto-injects EVERY file into each session's context.
Dumping a 72KB knowledge file there works but wastes tokens and gives NO retrieval.
Instead, have the profile's skill call `gbrain query` and read only the top notes per question.

Two delivery shapes, same brain:
1. **Hermes profile agent (preferred for local use).** Put an advisor skill (e.g.
   `skills/hormozi-advisor/SKILL.md`) in the profile that runs `gbrain query` then
   `gbrain get`, then answers from retrieved text. The profile's `SOUL.md` sets the persona
   ("You are Alex Hormozi"). No duplication, notes stay single-source, new videos auto-seen.
2. **CLI bot (portable / reusable).** `retrieval.py` (gbrain query+get) + `llm.py`
   (OpenAI-compatible POST) + `hormozi_bot.py` (argparse ask/draft/brainstorm). Same brain.

## CRITICAL: embedding coverage — `query` silently misses un-embedded notes
`gbrain query` (hybrid/RRF) returns a note ONLY if it has a vector embedding.
`gbrain capture` saves the note but does NOT auto-embed it, and on boxes without
`NVIDIA_API_KEY` (this VPS) `gbrain embed` aborts — so coverage can sit near 1%.
A brand-new note is therefore INVISIBLE to `query` until someone embeds it.
**A retrieval layer built on `query` alone silently drops un-embedded notes.**
Fix (validated this session): merge `query` + `gbrain search` (keyword, no key) +
a per-note canonical-phrase fallback. See `references/retrieval-coverage-fallback.md`
for the parsers and `retrieve()` merge order. Symptom check: if a query returns only
older notes and misses a note you just captured, your path is `query`-only — add the
`search`+fallback merge.

## CRITICAL: `gbrain query` output format (easy to parse wrong)
`gbrain query "<q>" --limit 8` prints:
```
[2.0000] experts/alex-hormozi/closer-framework -- expert: Alex Hormozi
subtype: framework
principle: CLOSER: the 6-part sales-call script structure
```
There is a LEADING `[score]` prefix. Therefore:
- `grep '^experts/` matches NOTHING (line starts with `[`).
- `awk '{print $1}'` captures the SCORE, not the slug.

Correct slug extraction (see `references/gbrain-query-parsing.md`):
```bash
gbrain query "<q>" --limit 8 2>/dev/null \
  | grep 'experts/alex-hormozi/' \
  | sed -E 's/^\[[^]]*\] +//' \
  | awk '{print $1}'
```
Also strip the `UPGRADE_AVAILABLE ...` banner gbrain prints to stdout before parsing slugs.

## Generic-prompt fallback (fan-out)
Hybrid search returns NOTHING for generic phrasing ("email sequence for a coaching offer"
has no lexical match to a note about "three pillar pitch"). When the first query yields no
slugs, fan out over framework vocabulary and merge top results:
```bash
for d in offer "lead magnet" sales pricing value "three pillar pitch" "closer framework" "cta formula"; do
  gbrain query "$d" --limit 6 2>/dev/null | grep 'experts/alex-hormozi/' | sed -E 's/^\[[^]]*\] +//' | awk '{print $1}'
done
```
Dedupe, take top k (e.g. 6).

## LLM wiring (free model)
OpenCode Zen: base `https://opencode.ai/zen/v1`, model `hy3-free` (free, cost:0),
OpenAI-compatible `/chat/completions`. Key env var `OPENCODE_ZEN_API_KEY`.
- Set `requests` timeout to 180s — free models are SLOW (a brainstorm took ~5 min here).
- Run long prompts in background (terminal `background=true` + `notify_on_complete`).
- Graceful fallback: if key unset, return raw retrieved notes (retrieval-only mode).

## Grounding rules (enforce in system prompt / skill body)
1. Answer ONLY from retrieved notes. If uncovered, say so — never invent quotes/stats.
2. Cite source slug: `[experts/alex-hormozi/closer-framework]`.
3. Mark application/inference with `[inference]`; keep distinct from direct knowledge.
4. Draft: apply frameworks explicitly, cite which used, flag unsupported as `[inference]`.
5. Never impersonate the expert with fabricated words/opinions.

## Hosted Portal bot vs local Hermes profile (key distinction)
- A bot in the Nous Portal **BOTS tab** is hosted on Nous's side and CANNOT reach this VPS's
  local GBrain or run local scripts. For those, export notes to a text pack
  (`gbrain export --slug-prefix experts/alex-hormozi --dir ...` then `cat */*.md > knowledge.md`)
  and paste `knowledge.md` + a system prompt into the Portal bot's knowledge/instructions field.
- A **Hermes profile** (e.g. `hermes profile list` shows `alex-hormozi`) is LOCAL and can RAG
  the live GBrain directly — prefer this; it stays in sync automatically.

## Wiring a profile skill (cross-profile note)
If editing a profile's skill from the DEFAULT profile, the write is blocked by a soft guard;
pass `cross_profile=True`. The profile's `gbrain` is on PATH via
`export PATH="$HOME/.bun/bin:$PATH"` in the subprocess env.

## Verification
- `gbrain query "what is the CLOSER framework?"` → slug `experts/alex-hormozi/closer-framework`.
- Profile test: `hermes -p alex-hormozi chat -q "how to handle 'I need to think about it'?"`
  → retrieves stall-questions/aaa-method/all-purpose-closes, cites slugs, marks `[inference]`.
- CLI test: `python3 hormozi_bot.py ask "..."` → cites the right note.

## Files (reference layout)
- CLI variant: `/root/hormozi_bot/{retrieval,llm,hormozi_bot}.py`
- Profile: `/root/.hermes/profiles/<name>/skills/<name>-advisor/SKILL.md`
- Hosted-bot pack only: `/root/hormozi_bot/bot_pack/{hormozi_knowledge.md,HORMOZI_SYSTEM_PROMPT.md}`

## References
- `references/gbrain-query-parsing.md` — slug extraction from `gbrain query` output.
- `references/retrieval-coverage-fallback.md` — query+search+fallback merge pattern for boxes without embedding keys (validated: recovers un-embedded notes `query` drops).
