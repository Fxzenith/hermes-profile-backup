# Quote Pool: Exclude Self-Authored & Listicle Quotes

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Stop the daily Instagram bot from posting listicle/step-format quotes and any quotes authored by the user (Ze Nith / @zenith); keep only third-party-attributed quotes.

**Architecture:** The pool is built in `scripts/quote_pool.py:set_templates()` from `cron_post.TEMPLATES` (4 topics × 8 tweets). We add an `author` field to every tweet and an exclusion filter inside `set_templates()` that drops (a) listicle/numbered-step text and (b) tweets whose author is in a SELF-authored denylist. The existing `test_quote_pool.py` is extended to assert excluded entries never surface. No repeat / LRU logic in `pick()` is touched.

**Tech Stack:** Python 3, stdlib only (`re`, `json`). Repo: `/root/projects/Instagram daily auto-post`.

---

## Current context (verified)

- `cron_post.TEMPLATES` has 4 templates: `productivity`, `mindset`, `learning`, `business`. Each: `{topic, title, hook, tweets:[str], theme}`. **No `author` field exists.**
- The offending post = `learning` template, tweet index `1` = "Step 1: Deconstruct the skill … Step 2 …" (numbered listicle). Matches the user's screenshot exactly.
- `_POOL` is built in `set_templates()` (quote_pool.py:38-53) — one entry per `(topic, tweet_idx)`. This is the only place to filter.
- Validator `scripts/test_quote_pool.py` builds a scratch pool and asserts no-repeat/LRU; it does NOT currently check content type or author.

## Assumptions

- "Self-authored" = author in `{"Ze Nith", "@zenith", "zenith", "ZeNith"}` (case-insensitive compare). Extend as needed.
- Third-party = any `author` NOT in the self set. Tweets with a missing/empty `author` are treated as **excluded** (safe default: keep only verifiable third-party quotes — matches the user's rule "keep only third-party quotes").
- Listicle = text contains a leading numbered step (`^\s*\d+[\.\)]`) OR a `step \d+` token (case-insensitive). This catches the `learning#1` post and any future step lists.

---

## Task 1: Add `author` field to every tweet in `cron_post.TEMPLATES`

**Objective:** Give each quote an `author` so self-vs-third-party can be filtered.

**Files:**
- Modify: `/root/projects/Instagram daily auto-post/scripts/cron_post.py` (the `TEMPLATES` list)

**Step 1:** Convert each tweet entry from a plain `str` to a dict `{"text": str, "author": str}`.
- For the offending `learning` tweet `[1]` (the listicle), set `"author": "Ze Nith"`.
- Assign a verifiable third-party author to every other tweet (e.g. the well-known source for each line), OR if unknown, set `"author": ""` (which the filter will exclude — user must fill these in). Do NOT leave as a bare string.

Example shape (apply to all 32 tweets):
```python
TEMPLATES = [
    {
        "topic": "productivity",
        "title": "The Compound Effect",
        "hook": "Small habits create massive results over time.",
        "theme": "light",
        "tweets": [
            {"text": "Most people overestimate what they can do in a day.\n\nAnd underestimate what they can do in a year.", "author": "Darren Hardy"},
            # ... remaining 7 ...
        ],
    },
    # mindset, learning, business ...
]
```

**Step 2:** Update `set_templates()` reader so it still works after the shape change (see Task 2 — the dict has `text`, not a bare string).

**Step 3:** Quick sanity import
Run: `cd "/root/projects/Instagram daily auto-post" && PYTHONPATH=scripts python3 -c "import cron_post; print(len(cron_post.TEMPLATES[0]['tweets']), cron_post.TEMPLATES[0]['tweets'][0])"`
Expected: prints `8 {'text': '...', 'author': '...'}`

**Step 4:** Commit
```bash
git add scripts/cron_post.py
git commit -m "feat: add author field to quote pool templates"
```

## Task 2: Add exclusion filter in `quote_pool.set_templates()`

**Objective:** Drop self-authored and listicle entries when building `_POOL`.

**Files:**
- Modify: `/root/projects/Instagram daily auto-post/scripts/quote_pool.py:38-53`

**Step 1: Write failing test** (new file `scripts/test_quote_exclude.py`)
```python
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import quote_pool as qp
import cron_post

def test_no_self_or_listicle_in_pool():
    qp.set_templates(cron_post.TEMPLATES)
    pool_authors = {e["author"].lower() for e in qp._POOL}
    self_authors = {"ze nith", "@zenith", "zenith", "zenith"}
    assert not (pool_authors & self_authors), f"self author leaked: {pool_authors & self_authors}"
    for e in qp._POOL:
        assert not qp._is_listicle(e["tweet"]), f"listicle leaked: {e['id']}"

if __name__ == "__main__":
    test_no_self_or_listicle_in_pool()
    print("PASS: no self-authored or listicle quotes in pool")
```

**Step 2: Run test to verify failure**
Run: `cd "/root/projects/Instagram daily auto-post" && PYTHONPATH=scripts python3 scripts/test_quote_exclude.py`
Expected: FAIL — `AttributeError` (tweets are now dicts) or assertion on listicle/self leak.

**Step 3: Implement the filter** — replace the `set_templates()` body (quote_pool.py:38-53):
```python
SELF_AUTHORS = {"ze nith", "@zenith", "zenith", "zenith"}
_LISTICLE_RE = re.compile(r"(?m)^\s*\d+[\.\)]|step\s+\d+", re.IGNORECASE)

def _is_listicle(text: str) -> bool:
    return bool(_LISTICLE_RE.search(text or ""))

def set_templates(templates: list[dict]):
    """Inject TEMPLATES and rebuild the canonical pool, excluding
    self-authored and listicle/step-format quotes."""
    global _TEMPLATES, _POOL
    _TEMPLATES = templates
    _POOL = []
    for i, t in enumerate(templates):
        for j, tw in enumerate(t.get("tweets", [])):
            text = tw["text"] if isinstance(tw, dict) else tw
            author = (tw.get("author", "") if isinstance(tw, dict) else "").strip().lower()
            if author in SELF_AUTHORS:
                continue                       # self-authored -> drop
            if _is_listicle(text):
                continue                       # listicle/step format -> drop
            _POOL.append({
                "id": f"{t['topic']}#{j}",
                "topic": t["topic"],
                "title": t["title"],
                "hook": t["hook"],
                "tweet_idx": j,
                "tweet": text,
                "author": author,
                "tpl_idx": i,
            })
```
Also add `import re` at the top of quote_pool.py.

**Step 4: Run test to verify pass**
Run: `cd "/root/projects/Instagram daily auto-post" && PYTHONPATH=scripts python3 scripts/test_quote_exclude.py`
Expected: PASS — "no self-authored or listicle quotes in pool"

**Step 5: Commit**
```bash
git add scripts/quote_pool.py scripts/test_quote_exclude.py
git commit -m "feat: exclude self-authored and listicle quotes from pool"
```

## Task 3: Keep `pick()`/validators compatible with the new tweet shape

**Objective:** Ensure `_next_candidate`, `pick`, and `test_quote_pool.py` read `e["tweet"]` (not a bare string) and the pool size assertion still holds.

**Files:**
- Modify: `/root/projects/Instagram daily auto-post/scripts/quote_pool.py` (lines referencing `t["tweets"][j]` already in set_templates — done in Task 2)
- Check: `scripts/test_quote_pool.py` — pool built via `qp.set_templates(cron_post.TEMPLATES)`; if `cron_post.TEMPLATES` still exposes `tweets` as dicts, no change needed. Verify it imports.

**Step 1: Run the existing validator**
Run: `cd "/root/projects/Instagram daily auto-post" && PYTHONPATH=scripts python3 scripts/test_quote_pool.py`
Expected: PASS — "100 selections, N-card pool: no repeat before exhaustion …" (N is now smaller because listicle/self entries were dropped; the `assert pool_size >= 30` in the test may now FAIL if the pool shrank below 30 — see Task 4).

**Step 2: If pool_size < 30**, adjust the assertion threshold in `test_quote_pool.py:41` to the real post-filter size (e.g. `>= 20`) and note it. Do NOT pad the pool with self/listicle quotes to satisfy the old threshold.

**Step 3: Commit**
```bash
git add scripts/test_quote_pool.py
git commit -m "test: relax pool-size floor after self/listicle exclusion"
```

## Task 4: Re-tag remaining tweets with real third-party authors

**Objective:** Every kept tweet has a verifiable third-party `author` (no empty strings), so the "third-party only" rule holds.

**Files:**
- Modify: `/root/projects/Instagram daily auto-post/scripts/cron_post.py`

**Step 1:** For each tweet whose `author` is `""`, assign the actual source author (book/person). If genuinely unknown, either drop the tweet or set a clearly-third-party placeholder the user approves.

**Step 2: Re-run both tests**
Run: `cd "/root/projects/Instagram daily auto-post" && PYTHONPATH=scripts python3 scripts/test_quote_exclude.py && PYTHONPATH=scripts python3 scripts/test_quote_pool.py`
Expected: both PASS; no empty authors remain in `_POOL`.

**Step 3: Commit**
```bash
git add scripts/cron_post.py
git commit -m "feat: attribute all pool quotes to third-party sources"
```

---

## Verification (full)

```bash
cd "/root/projects/Instagram daily auto-post"
PYTHONPATH=scripts python3 scripts/test_quote_exclude.py   # no self/listicle leak
PYTHONPATH=scripts python3 scripts/test_quote_pool.py      # no-repeat + LRU still hold
# Confirm the exact offending post is gone:
PYTHONPATH=scripts python3 -c "import quote_pool as qp, cron_post; qp.set_templates(cron_post.TEMPLATES); ids=[e['id'] for e in qp._POOL]; print('learning#1 present?', 'learning#1' in ids)"
# Expected: learning#1 present? False
```

## Risks / tradeoffs

- Dropping listicle + self tweets shrinks the pool; if it falls below daily volume needs, add more third-party quotes rather than re-enabling excluded types.
- Listicle regex is heuristic — a quote that happens to start a line with "1." (e.g. a dated fact) could be dropped. Review `test_quote_exclude.py` output if a wanted quote vanishes.
- The `author` field is now required on every tweet; `cron_post.TEMPLATES` edits must keep the dict shape or `set_templates()` will KeyError.

## Open questions

- Should empty `author` tweets be excluded (current plan) or kept? User said "keep only third-party quotes" → exclude empties.
- Does the user want the same filter applied to the YouTube-Shorts pipeline (`/root/projects/autoclipping`)? That pipeline uses `clips.json`/Claude selection, not this pool — out of scope unless confirmed.
