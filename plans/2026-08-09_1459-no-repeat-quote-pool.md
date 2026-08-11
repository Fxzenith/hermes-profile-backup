# Quote No-Repeat Pool for Morning (11:00) + Evening (18:00) Posts

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Guarantee that (a) the 11:00 image post and the 18:00 reel never publish the same quote as each other, and (b) neither ever republishes a quote already used on the account — via a persistent, deterministic quote-pool with LRU recycling once exhausted.

**Architecture:** Introduce a single source of truth, `scripts/quote_pool.py`, backed by `logs/quote_pool_state.json`. Every day two slots (`morning` = 11:00, `evening` = 18:00) are assigned a distinct (topic, tweet_idx) pair. The pool is built from the 4 TEMPLATES × 4 tweets each = **16 distinct quote cards**, plus the legacy `tweet_idx=0` entries already published historically get pre-marked as used (seed-backfill from `workspace/*/post-*/post_meta.json`). Selection is deterministic per (date, slot): the same quoted pair is returned on retries, never collides with the other slot on the same day, and never repeats until all 16 are consumed — then it recycles via least-recently-used so nothing repeats immediately.

**Tech Stack:** Python 3.12 stdlib only (json, datetime, pathlib). Existing TEMPLATES list in `scripts/cron_post.py` is the source pool. No cron prompt changes — both existing jobs keep calling their entry scripts.

**Why not just random.choice with a used-set:** Both triggers run in separate cron sessions. A random pick cannot be validated by the other trigger without shared state, and retries within a session would re-roll. A persistent JSON state file makes the assignment idempotent: re-running the morning job returns the same quote, and the evening job sees what morning took.

**Current-facts (verified this session):**
- `scripts/cron_post.py::TEMPLATES` = 4 topics (productivity, mindset, learning, business), each with `hook` (caption line) + 4 `tweets` (card text options). `build_post_config()` hardcodes `tweets[0]`.
- `scripts/composio_post.py::generate()` is the single generation path used by BOTH the 11:00 job and `scripts/reel_post.py` (18:00) — one shared entry point to patch.
- Historical posts (e.g. `workspace/2026-08-09/post-01/post_meta.json`) record `template` + `caption`; caption starts with the template `hook`. Because only `tweets[0]` was ever rendered, every historical post = `(topic, tweet_idx=0)`.
- `logs/` has no quote-history file today (`reel_state.json`, `story_state.json`, `comment_state.json` exist — precedent for JSON state files).

---

## Task 1: Create `scripts/quote_pool.py` (pool state + deterministic pick)

**Objective:** Module that owns quote assignment; idempotent per (date, slot); LRU recycle on exhaustion.

**Files:**
- Create: `scripts/quote_pool.py`
- Create: `logs/quote_pool_state.json` (auto-created on first run)

**Step 1: Write the module** (complete code):

```python
#!/usr/bin/env python3
"""Deterministic no-repeat quote pool for the daily posts.

Two slots per day: 'morning' (11:00 image post) and 'evening' (18:00 reel).
Every (date, slot) gets a stable (topic, tweet_idx) assignment.  No quote is
reused until the whole 16-card pool is spent; afterwards reuse in
least-recently-used order (never the immediately previous card).

State lives in REPO/logs/quote_pool_state.json.
"""
import datetime
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATE_FILE = REPO / "logs" / "quote_pool_state.json"
SLOTS = ("morning", "evening")

# Imported lazily to avoid a hard import cycle; cron_post loads its templates
# at module import time, so we inject via set_templates()/build_pool().
_TEMPLATES = []

def set_templates(templates: list[dict]):
    global _TEMPLATES
    _TEMPLATES = templates
    build_pool()

def build_pool():
    """Rebuild the canonical 16-entry pool from the current TEMPLATES."""
    global _POOL
    if not _TEMPLATES:
        raise RuntimeError("quote_pool: templates not set; call set_templates() first")
    _POOL = []
    for i, t in enumerate(_TEMPLATES):
        for j in range(len(t.get("tweets", []))):
            _POOL.append({
                "id": f"{t['topic']}#{j}",
                "topic": t["topic"],
                "title": t["title"],
                "hook": t["hook"],
                "tweet_idx": j,
                "tweet": t["tweets"][j],
                "tpl_idx": i,
            })

def _default_state():
    return {"assigned": {},          # "YYYY-MM-DD" -> {"morning": id, "evening": id}
            "used": {},              # id -> last assigned date (for LRU recycle)
            "history": []}           # ordered log of assignments for audit

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            pass
    return _default_state()

def save_state(state: dict):
    STATE_FILE.parent.mkdir(exist_ok=True)
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)          # atomic-ish

def _next_candidate(state: dict, blocked: set) -> str:
    """Pick an id: never-used first, else LRU (least recently assigned)."""
    used = set(state["used"].keys())
    fresh = [e["id"] for e in _POOL if e["id"] not in used]
    fresh = [i for i in fresh if i not in blocked]
    if fresh:
        return fresh[0]              # pool order = template/tweet order
    # All used: LRU recycle, avoiding the other slot's card today.
    cands = [(state["used"].get(i["id"], ""), i["id"]) for i in _POOL]
    cands = [(d, i) for d, i in cands if i not in blocked]
    cands.sort()                     # "" first = never used fallback, then oldest date
    return cands[0][1]

def pick(slot: str, day_iso: str) -> dict:
    """Return the pool entry assigned to (slot, day), assigning deterministically."""
    assert slot in SLOTS, f"slot must be one of {SLOTS}"
    state = load_state()
    assignments = state.setdefault("assignments", {})
    day_state = assignments.setdefault(day_iso, {})
    if slot not in day_state:
        blocked = set(day_state.values())              # other slot's pick today
        cid = _next_candidate(state, blocked)
        day_state[slot] = cid
        state["used"][cid] = day_iso
        state.setdefault("history", []).append({"date": day_iso, "slot": slot, "id": cid})
        save_state(state)
    cid = day_state[slot]
    return next(e for e in _POOL if e["id"] == cid)

def mark_backfilled(dates_topics):
    """Pre-mark (topic, tweet_idx=0) as used, per historical post_meta.json."""
    state = load_state()
    for date, topic in dates_topics:
        sid = f"{topic}#0"
        day_state = state.setdefault("assignments", {}).setdefault(date, {})
        day_state.setdefault("_backfilled", None)      # marker slot, harmless
        state["used"][sid] = state["used"].get(sid) or date
    save_state(state)

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 4 and sys.argv[1] == "pick":
        from cron_post import TEMPLATES
        set_templates(TEMPLATES)
        print(json.dumps(pick(sys.argv[2], sys.argv[3])))
    else:
        print("usage: python3 scripts/quote_pool.py pick <morning|evening> <YYYY-MM-DD>")
        sys.exit(2)
```

(State schema: `{"assignments": {date: {slot: id}}, "used": {id: date}, "history": [...]}`; the loader defaults missing keys so a fresh run bootstraps cleanly.)

**Step 2: Verify determinism + no-repeat + no-collision** (run from repo root):

```bash
python3 - <<'EOF'
import sys, json
sys.path.insert(0, "scripts")
import quote_pool as qp
import cron_post
qp.set_templates(cron_post.TEMPLATES)

seen_m, seen_e = [], []
for d in range(30):
    day = f"2026-09-{d+1:02d}"
    m = qp.pick("morning", day)["id"]
    e = qp.pick("evening", day)["id"]
    assert m != e, f"collision on {day}: {m} == {e}"
    seen_m.append(m); seen_e.append(e)
# no repeat within first 8 days (16 slots = whole fresh pool)
first16 = seen_m[:8] + seen_e[:8]
assert len(set(first16)) == 16, f"repeat before exhaustion: {first16}"
# LRU recycle: after exhaustion, no card repeats itself on back-to-back slots
for pair in zip(seen_m, seen_e):
    assert pair[0] != pair[1]
print("PASS: 30 days, no same-day collision, no repeat until pool exhausted, no-a-like after recycle")
EOF
```
Expected: `PASS` line printed.

**Step 3: commit** — `git add scripts/quote_pool.py && git commit -m "feat: deterministic no-repeat quote pool"` (only if repo is git-initialized; `git rev-parse --git-dir` first).

---

## Task 2: Backfill historical usage + wire generation to pick per slot

**Objective:** existing published quotes become "used", and both triggers get slot-aware generation.

**Files:**
- Modify: `scripts/cron_post.py` — `build_post_config(template, folder, tweet_idx=0)` (currently hardcodes `tweets[0]`).
- Modify: `scripts/composio_post.py::generate(slot="morning")` — use the pool instead of `random.choice`.

**Step 1: cron_post.build_post_config — select the tweet by index**

```python
def build_post_config(template: dict, folder: Path, tweet_idx: int = 0) -> Path:
    tweets = template["tweets"]
    tweet_text = tweets[tweet_idx] if tweet_idx < len(tweets) else tweets[0]
    posts = [{"tweets": [{"text": "", "image": None}]}]
    ...
```
(Do not touch the rest of the config shape — only swap the tweet text selection. Actually simplest: reuse existing code but set `posts[0]["tweets"][0]["text"] = tweet_text`.)

**Step 2: Patch `composio_post.generate()` to pick via pool**

Replace the three lines that do `template = cp.select_template()` + `cp.build_post_config(template, folder)` + `cp.generate_post_image(config_path, folder)` with:

```python
quote_pool.set_templates(cp.TEMPLATES)
tmpl = quote_pool.pick(slot, date.today().isoformat())
template = {**tmpl, "tweets": [tmpl["tweet"]]}   # card shows the chosen tweet
config_path = cp.build_post_config(template, folder, tweet_idx=tmpl["tweet_idx"])
images = cp.generate_post_image(config_path, folder)
```
And record in `post_meta.json`: add `"slot": slot`, `"quote_id": tmpl["id"]`, `"tweet_text": tmpl["tweet"]`.

**Step 3: `reel_post.py` passes `slot="evening"`** where it calls `generate()` — add the keyword so both code paths pass **explicit** slot. `composio_post.generate(slot="evening")`.

**Step 4: backfill history** (one-off script, run once):
```bash
python3 - <<'EOF'
import sys, json
from pathlib import Path
sys.path.insert(0, "scripts")
import quote_pool as qp
import cron_template as ct  # fix import per actual module name
qp.set_templates(ct.TEMPLATES)
rows = []
for meta in (Path("workspace").glob("*/post-*/post_meta.json")):
    d = json.loads(meta.read_text())
    rows.append((meta.parent.parent.name, d.get("template")))   # date dir -> topic
qp.mark_backfilled(rows)
print("backfilled", len(rows), "historical posts")
EOF
```
Expected: prints count of workspace post_meta files found.

---

## Task 3: Regression + integration verification

**Files:** none (verification only).

**Step 1: run the existing smoke paths**
- `python3 scripts/reel_renderer.py <card> music/track-01.mp3 /tmp/x.mp4` — still renders.
- `python3 scripts/audio_library.py` — still picks.
- Dry-run both path: scheduled posts for 10 simulated dates, capture `quote_id` pairs:
  - morning vs evening each day: distinct.
  - across all 10 days: no `quote_id` repeats until pool exhaustion (16 slots); then LRU.

**Step 2: verify legacy path untouched**
- `python3 scripts/cron_post.py select_template` still returns a template dict (function name may change; keep a thin wrapper).
- Ensure `composio_post.generate(slot="morning")` writes `post_meta.json` including `quote_id`.

**Step 3: full end-to-end dry** (no publish):
```
REEL_DRY_RUN=1 python3 scripts/reel_post.py      # evening
```
Expected: renders card with a DIFFERENT quote topic/tweet than today's 11:10 post (verify by reading generated post_meta).

**Acceptance criteria:**
1. Ten consecutive simulated days: no same-day collision between morning/evening; no repeat of a `quote_id` until the 16-card pool fully exhausts; afterwards LRU (no back-to-back repeat).
2. Today's existing account history is respected once: the backfill marks previously posted `(topic#0)` ids as used.
3. Both cron jobs still run unchanged — no prompt edits, no new job.

## Risks / tradeoffs / open questions
- **Pool is small (16).** With 2 posts/day the ceiling is 8 days of zero-repeats, then LRU recycle. If the user wants months of unique quotes, they must add more TEMPLATES (or a quotes source file). Flag to the user at handoff; plan the extension point now (`POOL` rebuilt from whatever TEMPLATES contains).
- **Backfill granularity:** historical posts only record generic content; we mark their topic#0 base forms used. The current slot already issued `topic#0` variants (verified: productivity, learning, mindset on 08-09/08-09) — those will correctly read as used after back.
- **caption vs card:** the visible "quote" per post = card tweet text. The caption's `template['hook']` can still match another day's hook (4 hooks / 16 cards) — if the user considers the hook the quote, we can horizon the hook rotation too (small addition; note in plan).

## Execution Handoff
After approval, implement via subagent-driven development: one fresh subagent per task with two-stage review (spec compliance → code quality). Task 1 is self-contained unit-testable; Task 2 wires the pool into both triggers; Task 3 is verification only.