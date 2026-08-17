# Instagram hashtag diet (Composio) — full recipe

Built Aug 2026 for @ze.nith001's daily auto-poster.
Engine: `/root/Instagram daily auto-post/scripts/hashtag_engine.py`.
Companion: see `references/instagram-comment-engagement.md` and
`references/instagram-engagement.md` for the rest of the pipeline.

## Why it exists

The old pipeline appended the SAME 6 tags (`#productivity #mindset #growth
#habits #success #motivation`) verbatim to every post. Identical tag sets on
every post read as automated spam to IG's detection and suppress reach. Also,
all 6 were huge-volume generic tags — maximum saturation, zero niche threads.

## The diet: tiered pools + date-seeded rotation

- Per-topic pools (productivity / mindset / learning / business — the account's
  templates): 3 tiers — BIG (broad reach, saturated), MEDIUM (engagement),
  NICHE (lower volume, high intent; where discovery actually happens).
- Pick per post: `{"big": 2, "medium": 3, "niche": 3}` + 2 brand evergreens
  (`#zenith`, `#dailyquote`, `#quoteoftheday`), hard-capped at `MAX_TOTAL = 9`.
- **Deterministic per (topic, day)**: `random.Random(f"{topic}:{day.isoformat()}")`
  → the same day always picks the same set (a retry of a failed post reproduces
  identical content), but consecutive days rotate — verified no two consecutive
  days share the full set. NEVER use a plain `random` call: non-determinism breaks
  idempotent retries.
- Wire-in: caption = `f"{hook}\n\n{render_hashtags(select_hashtags(topic))}"`.
  Both `composio_post.py` (active cron entry) and `cron_post.py` (legacy path)
  were patched — leaving the static string in the dormant path is how regressions
  start; grep for the old string after changing it.

## Pitfalls (hit live this session)

1. **Invented hashtags are worthless.** First draft had invented niche tags
   (`#compoundingknowing`, `#tuitionmissing`, `#executionissexy`) — zero
   searches = zero discovery. Only real, searchable tags count. Also caught
   typos of real tags (`#deeppwork`, `#deeperformance` vs `#deepwork`).
2. **`%23` vs literal `#` — verified live.** Meta's Graph API docs say to
   HTML-URL-encode hashtags (`#` → `%23`). BUT the composio execute path sends
   a JSON body (`-d`), not a query string — the account's live captions prove
   literal `#` renders correctly. `render_hashtags` just joins with `" "`.
   Do NOT encode; `%23` risks showing literally in the caption.
3. **Hashtags belong in the caption, not as a separate entity** — no separate
   "hashtag" tool exists; they're just text in `caption` on the container call.
4. Rotation check before declaring done: print 6 consecutive days for one topic
   and confirm sets spread (never a full repeat).

## The `%23` verification recipe (how to check any payload nuance)

Before trusting docs over the live API, read back what the account actually has:
`INSTAGRAM_GET_IG_USER_MEDIA --account <conn> -d '{"ig_user_id":"<id>","limit":1}'`
→ inspect `caption` of the newest item. The existing post showed literal
`#productivity #mindset ...` — ground truth beats documentation.

## Reuse

Copy `hashtag_engine.py` for any IG/other-platform content automation:
swap POOLS per niche, keep tiered selection + date-seeded determinism + hard cap.
