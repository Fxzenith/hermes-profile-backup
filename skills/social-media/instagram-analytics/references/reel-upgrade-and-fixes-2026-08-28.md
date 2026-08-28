# Reel Upgrade & Pipeline Fixes — 2026-08-28

Applies analytics findings to pipeline: morning IMAGE→REEL, 409 handling, comment CTA, pool ID fix.

## 1. Morning slot IMAGE → REEL (11.7× lift)

**File:** `scripts/composio_post.py`
- Added `import audio_library, reel_renderer` and flags `MORNING_AS_REEL=True`, `REEL_MAX_WAIT=300`, `REEL_POLL=10`
- New functions `create_reel_container()` / `publish_reel()` mirroring `reel_post.py` (`media_type: REELS`, `video_file`)
- `publish_reel()` treats `"already been published"` (409) as success (see §2)
- `notify_telegram()` now branches `sendVideo` vs `sendPhoto` by extension
- `main()` after `generate(slot="morning")`: select track `audio_library.select_track(date.today().isoformat())`, render `image.parent/reel/reel.mp4` via `reel_renderer.render()`, publish as reel, notify with video. Falls back to image if no audio.
- Verification: `python3 -c "from composio_post import generate; img,cap=generate('morning'); import audio_library,reel_renderer; track=audio_library.select_track(...); reel_renderer.render(img, ...)"` — produced 5.2s mp4 in test.

**Why:** Audit of 25 posts: reels avg 5.42 likes, images 0.46 (11.7×). All 0-like posts were images. Topic rank alone insufficient without format fix.

## 2. 409 Already-Published fix

**Files:** `scripts/reel_post.py` and `scripts/composio_post.py`

`INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` for REELS can return 409 with `Container ... has already been PUBLISHED` even though media is live (Composio polling race). Old code retried 3× and marked `error` while post was actually on Instagram. 

Fix:
```python
blob = json.dumps(parsed or {}).lower()
if "already been published" in blob:
    log("✅ Reel already published — treating as success", "WARN")
    return True  # or return container_id in reel_post.py
```

Apply before `NON_TEMPORARY` check. Affected job `7a4c465fbd09` on 2026-08-27 18:00.

## 3. Comment CTA rotation

**File:** `scripts/comment_loop.py`

Old `SELF_QUESTION_TEMPLATES` were Q&A (`What's the ONE habit...`, `Which habit are you building...`) — 0 organic replies in 22/25 posts.

New savable CTAs (from 3 organic `"Send me this post"` saves):
```python
SELF_QUESTION_TEMPLATES = [
    "Save this for your next low day 🔖",
    "Send this to someone who needs it today 📩",
    "Save this — you'll want it on a hard day 💪",
    "Drop a 🔥 if you needed this today.",
    "Comment 'READY' if you're committing to this starting today 💪",
]
```

## 4. Quote pool — distinct topics & hashtag alias

**Files:** `scripts/cron_post.py`, `scripts/hashtag_engine.py`

- Pool ID is `f"{topic}#{tweet_idx}"`. Two templates sharing `topic="business"` collided — second template's tweets were never returned. Fixed by using distinct topics `money` (Money Truths clone) and `harsh` (Harsh Truths clone) and adding alias pools:
  - `hashtag_engine.POOLS["money"]` → wealth/moneymindset/cashflow + niche moneytruths
  - `hashtag_engine.POOLS["harsh"]` → discipline/harshTruths + niche disciplineequalsfreedom
- Templates expanded 4×8=32 → 6×8=47 (one tweet excluded as self-authored `learning#1`). New templates copy winners' formula (≤22 words, number/contrarian claim).

## 5. State cleanup after testing

`quote_pool.pick()` writes to `logs/quote_pool_state.json`. Test harnesses that call `pick()` for future dates pollute `assignments`/`used`/`history` with fake future dates. Always snapshot `STATE_FILE` and restore, or set `quote_pool.STATE_FILE` to scratch path in tests. On 2026-08-28 a 30-day sim left 2026-08-29..09-02 assignments that had to be surgically removed (`date <= "2026-08-27"` filter).

See also `references/performance-baseline-2026-08-28.md` for ranked table.
