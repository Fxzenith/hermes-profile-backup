# Pool & Posting Gotchas — Deep Detail

Companion to SKILL.md for the Instagram daily quote-post pipeline. Loaded on
demand when you need the exact architecture or the precise filter diff.

## Architecture (verified by tracing the imports)

```
logs/quote_pool_state.json   <- deterministic no-repeat state (date+slot -> quote id)
scripts/quote_pool.py         set_templates() builds _POOL; pick() assigns
scripts/cron_post.py          TEMPLATES (4 topics x 8 tweets) = the pool source
scripts/composio_post.py      THE daily driver: quote_pool.pick('morning'|'evening', date)
                              -> build_post_config() -> thread-to-image.py -> Instagram
scripts/cron_post.py:run_cron_job()   legacy/alternate path; uses random select_template()
```

- `composio_post.py:generate()` (line ~92) does: load `cron_post` module,
  `quote_pool.set_templates(cp.TEMPLATES)`, `tmpl = quote_pool.pick(slot, date)`,
  `template = cp.TEMPLATES[tmpl["tpl_idx"]]`,
  `cp.build_post_config(template, folder, tweet_idx=tmpl["tweet_idx"])`.
- Caption uses `tmpl["tweet"]` + hashtags. `post_meta.json` records `quote_id`,
  `tweet_text`, `topic`, `title`.
- So edits must land in `cron_post.TEMPLATES` and `quote_pool` (shared); editing
  `run_cron_job`'s random path changes nothing for the daily post.

## The exclusion filter (exact diff, in quote_pool.set_templates)

```python
import re
SELF_AUTHORS = {"ze nith", "@zenith", "zenith", "zenith"}
_LISTICLE_RE = re.compile(r"(?m)^\s*\d+[\.\)]|step\s+\d+", re.IGNORECASE)

def _is_listicle(text: str) -> bool:
    return bool(_LISTICLE_RE.search(text or ""))

def set_templates(templates: list[dict]):
    global _TEMPLATES, _POOL
    _TEMPLATES = templates
    _POOL = []
    for i, t in enumerate(templates):
        for j, tw in enumerate(t.get("tweets", [])):
            text = tw["text"] if isinstance(tw, dict) else tw
            author = (tw.get("author", "") if isinstance(tw, dict) else "").strip().lower()
            if author in SELF_AUTHORS:
                continue          # owner's own quote -> exclude
            if _is_listicle(text):
                continue          # listicle / step format -> exclude
            _POOL.append({... "tweet": text, "author": author, ...})
```

Effect: 32 -> 31 entries; `learning#1` (owner's "Step 1..." listicle) dropped.
`test_quote_exclude.py` asserts `learning#1` not in pool and no self/listicle leak.
`test_quote_pool.py` still asserts `pool_size >= 30` (31 passes).

## Tweet shape migration (the string->dict gotcha)

Before: `tweets: ["plain string", ...]`.
After:  `tweets: [{"text": "...", "author": "..."}, ...]`.

`build_post_config` in cron_post.py MUST read `.text`:
```python
tweet = tweets[tweet_idx] if 0 <= tweet_idx < len(tweets) else tweets[0]
tweet_text = tweet["text"] if isinstance(tweet, dict) else tweet
```
Without this, post time throws `TypeError: string indices must be integers`
because `tweets[tweet_idx]["text"]` on a plain string fails.

## Test layout

- `test_quote_pool.py` — 50 days x 2 slots = 100 picks on a SCRATCH state/log
  (never touches production logs). Asserts: no repeat before exhaustion, no
  same-day collision, deterministic re-pick, LRU no back-to-back, every pick
  logged. Pool floor `assert pool_size >= 30`.
- `test_quote_exclude.py` — SCRATCH state; asserts no SELF_AUTHORS leak, no
  listicle leak, `learning#1` absent.

Both run via `PYTHONPATH=scripts python3 scripts/<name>.py` from project root.

## Author-attribution policy (important)

Empty `author` = kept (unknown third-party). Do NOT fabricate real author names
for the 31 untagged quotes — leaving `""` is the safe default; the bot only
avoids the owner's own quotes (`Ze Nith`/`@zenith`). If the user later wants
strict "third-party only, drop all untagged", flip `_POOL` to also skip
`author == ""`.
