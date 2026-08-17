---
name: hackernews
description: 'Use when user asks for /hackernews or HN trending.'
version: 1.0.0
author: hermes
license: MIT
metadata:
  tags: [hackernews, composio, trending, news]
  related_skills: [composio]
---

# Hacker News top N trending

Fetches the current Hacker News front page (top N stories, default 15) using Composio's Hacker News tools and formats them for the user.

## When to Use
User says "/hackernews", "/hackernews N" (e.g. `/hackernews 1` or `/hackernews 3`), "top HN stories", "top N HN stories", "what's trending on Hacker News", "HN front page", etc.

## Steps

1. **Parse the count** — if the user typed `/hackernews N`, capture N. The default is 15.
2. **Run the fetch script** (does everything: top stories + per-story details; pass the user's count as the only argument):
   ```bash
   python3 ~/.hermes/skills/social-media/hackernews/scripts/top15.py        # top 15 (default)
   python3 ~/.hermes/skills/social-media/hackernews/scripts/top15.py 1      # top 1
   python3 ~/.hermes/skills/social-media/hackernews/scripts/top15.py 5      # top 5
   ```
   The script shells out to the Composio CLI (`HACKERNEWS_GET_TOP_STORIES` for the ranked ID list, then `HACKERNEWS_GET_ITEM` per story) and prints a ready-formatted numbered top-N list. It validates the count itself: non-numeric or <1 exits 1 with an ERROR on stderr, >500 clamps to 500 with a note. The output order from the script IS the front-page rank — preserve it.

3. **Present the result** — relay the script's output directly as a numbered list. Keep each line as:
   `**N. Title** — NNN pts, NN comments · [source](url)`
   Use `https://news.ycombinator.com/item?id=<id>` as the URL when a story has no external link (Ask HN / Show HN text posts).

4. **Add a one-line "Theme of the day"** — glance at the N titles and note any cluster (e.g. "3 of top 5 are AI-model stories"). Keep it to one sentence.

5. **Offer a follow-up** — e.g. "Want me to summarize the top discussion thread or dump all 500 stories to a file?"

## Why this approach

- `composio search "hacker news"` only surfaces the generic `composio_search` news toolkit — it does NOT find the Hacker News app. The dedicated tools are `HACKERNEWS_GET_TOP_STORIES` (returns 500 ranked story IDs; `{"print":"pretty"}` for readable JSON) and `HACKERNEWS_GET_ITEM` (takes `{"id": <int>}`). Both need `export PATH="$HOME/.composio:$PATH"` or the absolute binary path.
- The tool slugs are case-sensitive and validate on dry-run: `composio execute HACKERNEWS_GET_TOP_STORIES --dry-run -d '{}'`.
- `composio execute` stdout can carry banner prose before the JSON — always walk to the first `{` before parsing.

## Pitfalls

- **No OAuth needed** — Hacker News is a public API; there is no connection to link, but the CLI must be logged in (`composio whoami`). `composio link hackernews` exits 0 with no output — that's normal/fine, don't chase it.
- **N sequential CLI calls, ~0.1 min each (15 ≈ 2 min)** — smaller counts are proportionally faster; do NOT run the item fetches inline one-by-one in the agent loop; always use the script. Don't bump the per-call timeout above 60s.
- **Invalid count handling** — `top15.py abc` exits 1 with an ERROR on stderr; relay that message verbatim instead of fabricating a list.
- **Don't re-sort the list** — the ID order from `GET_TOP_STORIES` IS the front-page rank. Preserve it.
- **Stories sometimes lack `url`** — fall back to the HN item URL.

## Verification

- Script prints exactly N numbered entries (15 when run with no argument) with title, points, comments, source link, author.
- `/hackernews N` returns N entries; the rank-1 story matches the rank-1 of a full 15 run (order preserved, not re-sorted).
- Sanity: rank-1 story should have the highest score among the top few (algorithm noise aside).