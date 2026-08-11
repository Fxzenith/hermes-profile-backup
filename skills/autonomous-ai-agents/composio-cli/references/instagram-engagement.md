# Instagram Story-after-every-post (Composio) — full recipe

Built Aug 2026 for @ze.nith001 (IG user 28532466729677348, connection `instagram_magog-daroo`).
Script: `/root/Instagram daily auto-post/scripts/post_story.py`. State: `logs/story_state.json`.
Companion: see `references/instagram-comment-engagement.md` for the reply loop + sweep + watchdog.

## Key discovery

**Instagram Stories reuse the SAME post-media tool chain as feed posts.** No separate
"story" tool exists:
1. `INSTAGRAM_POST_IG_USER_MEDIA` with **`media_type: "STORIES"`** + `image_file` (local
   path — Composio auto-uploads it to a temp public URL) → returns `creation_id`.
2. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` with `{ig_user_id, creation_id,
   max_wait_seconds: 120, poll_interval_seconds: 5}` → returns the published media id.
3. Verify (don't trust the script): `INSTAGRAM_GET_IG_USER_STORIES` `{ig_user_id}`
   → `data.data[]` items show `id`, `media_type: IMAGE`, `timestamp`.

`media_type` enum: `REELS` (video), `CAROUSEL` (children), `STORIES`. Also check
`INSTAGRAM_GET_IG_USER_CONTENT_PUBLISHING_LIMIT` before bursts (default quota 100/day).

## Story image formatting

IG stories are 1080×1920 (9:16). A square quote card posted raw gets letterboxed/ugly.
Render the classic look with Pillow:
```python
from PIL import Image, ImageFilter
STORY_W, STORY_H = 1080, 1920
bg = Image.open(src).convert("RGB")                    # square quote card
back = bg.resize((STORY_W, STORY_H)).filter(ImageFilter.GaussianBlur(40))
back = back.point(lambda p: int(p * 0.55))             # darken → foreground pops
fg = bg.copy(); fg.thumbnail((STORY_W - 120, STORY_H - 320), Image.Resampling.LANCZOS)
back.paste(fg, ((STORY_W - fg.width) // 2, (STORY_H - fg.height) // 2))
back.save(out, "JPEG", quality=92)
```
Verified visually before the first live publish — blurred+darkened backdrop with the
centered card is the standard legible story look.

## One-per-day idempotency

State file `logs/story_state.json`:
```json
{ "last_story_date": "2026-08-09" }
```
Skip when `last_story_date == date.today()` — exit 0 silently (safe for daily cron:
a second run same day must be a no-op, never a duplicate story).

## Wiring

Daily job prompt (cron jobs.json) has `STEP 3c — STORY AFTER EVERY POST`, running right
after the comment loop: post → engage comments → story → notify Telegram. Story step is
OPTIONAL and non-blocking: on failure retry once, log, continue — never fail the post.

## Pitfalls

1. **`image_file` accepts a LOCAL path** for stories — no external host needed.
2. **Always set `max_wait_seconds > 0`** on publish — avoids error 9007 publish-too-soon.
3. Reuse the newest generated `post.png` (workspace/*/post-*/post_meta.json sibling) so the
   story matches what just went live on the feed.
4. Publish returns a story media id, not a permanent permalink — verification is via
   `INSTAGRAM_GET_IG_USER_STORIES`, not link lookups.
5. Downsize to ~85KB JPEG keeps container-create fast.