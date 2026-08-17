---
name: hormozi-advisor
description: Use when the user wants Alex Hormozi advice, drafts, or brainstorming grounded in the GBrain Hormozi expert notes. Invoke via /hormozi.
---

# Hormozi Advisor

RAG bot over the Alex Hormozi expert notes stored in GBrain (`experts/alex-hormozi/`).
Answers, drafts, and brainstorms are grounded ONLY in those notes; the bot cites
note slugs and marks any extension with [inference].

The adjacent experts distilled earlier from founder-playbook (Cialdini, SPIN,
Mom Test, etc.) were removed at the user's request — the bot is Hormozi-only again.

## When to use
- User asks "what would Hormozi say / recommend" about offers, sales, pricing, lead gen, focus.
- User wants copy/offer/email drafts using his frameworks.
- User wants to brainstorm grounded in his principles.

## How to run
The CLI lives at `/root/hormozi_bot/hormozi_bot.py`. The API key must be in the
environment as `OPENCODE_ZEN_API_KEY` (free `hy3-free` model via OpenCode Zen).
Without the key it still returns the raw matching notes (retrieval-only).

```bash
export PATH="$HOME/.bun/bin:$PATH"
export OPENCODE_ZEN_API_KEY="<set by user / Hermes credential pool>"
cd /root/hormozi_bot

# answer a question
python3 hormozi_bot.py ask "what is the CLOSER framework?"
# draft an asset
python3 hormozi_bot.py draft "a 3-email sequence selling a $2k coaching offer"
# brainstorm
python3 hormozi_bot.py brainstorm "lead magnet ideas for a fitness coach"
```

## Grounding rules (enforce these in output)
- Never present model output as Hormozi's literal words unless the note says so.
- Cite note slugs. Mark speculation with [inference].
- If the notes don't cover the ask, say so — do not invent.
