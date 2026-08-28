---
name: instagram-analytics
description: "Use when auditing Instagram post performance via Composio."
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [instagram, analytics, composio, engagement, reels]
---

# Instagram Analytics via Composio

Audit @ze.nith001 (IG user `28532466729677348`, Composio account `instagram_magog-daroo`) performance: enumerate all media, hydrate like/comment counts, pull organic comments, fetch reach, and translate into content decisions. Discovered 2026-08-28 on 25-post audit.

## When to Use
- "check every post that was posted", "which posts got most likes/views"
- "audit Instagram engagement", "compare reels vs images"
- "use data to improve content similar to top performers"
- "fetch Instagram insights / reach / comments via Composio"

## Prerequisites
- Composio CLI at `~/.composio/composio`, account `instagram_magog-daroo` ACTIVE (`composio connections list`)
- IG Business Account ID `28532466729677348` (not a placeholder from `.env` — `.env` on this box has `your_instagram_business_account_id_here` and an invalid token; live auth lives in Composio)
- Media collection lives double-nested: `data.data` under Composio wrapper; large payloads set `storedInFile=true` + `outputFilePath` — read that file

## Quick Reference
| Task | Tool / path |
|------|-------------|
| List all media | `INSTAGRAM_GET_IG_USER_MEDIA --account instagram_magog-daroo -d '{"ig_user_id":"28532466729677348"}'` → parse `outputFilePath` |
| Hydrate likes/comments | `INSTAGRAM_GET_IG_MEDIA --account instagram_magog-daroo -d '{"ig_media_id":"<id>","fields":"id,caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp,thumbnail_url,username,shortcode"}'` |
| Comments (organic vs self) | `INSTAGRAM_GET_IG_MEDIA_COMMENTS --account ... -d '{"ig_media_id":"<id>"}'` — `from.username=="ze.nith001"` is self |
| Account info | `INSTAGRAM_GET_USER_INFO --account ... -d '{}'` |
| Reach (daily) | `INSTAGRAM_GET_USER_INSIGHTS --account ... -d '{"ig_user_id":"28532466729677348","metric":["reach"],"period":"day","since":<int>,"until":<int>}'` |
| Workspace mapping | `/root/projects/Instagram daily auto-post/workspace/*/post-*/post_meta.json` + `config.json` |

## Procedure

1. **Enumerate media** via `INSTAGRAM_GET_IG_USER_MEDIA`. Unwrap `data.data` (or `data.data.data`) and handle `storedInFile`. Save IDs + `timestamp` + `caption` preview. 2026-08-28: 25 objects found (59 total on account, 25 in window).
2. **Hydrate engagement** — loop `INSTAGRAM_GET_IG_MEDIA` per ID with explicit `fields` param (see Pitfalls). Do NOT use defaults. Collect `like_count`, `comments_count`, `media_type`. Throttle ~0.7s between calls.
3. **Fetch comments** for top/bottom N to distinguish organic vs self. Self comments are the bot's daily question (`from.id=="17841416058149055"`). Organic signal is rare — only 3/25 had a real user comment (`"Send me this post"` from pods).
4. **Fetch reach** via `INSTAGRAM_GET_USER_INSIGHTS` with integer Unix timestamps (seconds). Convert dates: `int(datetime(YYYY,MM,DD).timestamp())`. Only `reach` reliably returns data; `likes/views/comments` often omitted when no activity.
5. **Join with workspace** — map `post_meta.json` (`slot`, `topic`, `tweet_text`) to IG `timestamp` by date to attribute topic performance.
6. **Analyze & recommend** using the 2026-08-28 findings as baseline (see References).

## Content Insights (2026-08-28 baseline, 71 followers — applied 2026-08-28)
- **Reels crush images: 5.4 vs 0.46 avg likes (11.7×).** All top-12 posts are reels; all 0-like posts are images. **Fixed 2026-08-28: 11:00 slot converted from IMAGE to REEL** (`composio_post.py:MORNING_AS_REEL=True` via `reel_renderer` + `audio_library` — both slots now reels) and pool re-weighted (see below).
- **Topic rank:** business contrarian (`Boring businesses print money` 9 likes) ≈ harsh mindset (`Nobody is coming 9`) > productivity math (`1% better 7`) >>> learning/education (`Learn in public 2`, `Immersion 0`). **Applied: pool expanded 4×8=32 → 6×8=47** with clones `money` (Money Truths) and `harsh` (Harsh Truths) using same winners' formula; `learning` de-prioritized to last. Duplicate topic IDs caused shadowing — fixed by distinct `money`/`harsh` topics.
- **Winners formula:** ≤22 words, specific number or contrarian money claim, 1-2 short sentences. Flops avg 38 words, vague `You don't need X` hooks (0 likes twice) — replaced with `Consistency is the cheat code...`.
- **Only savable one-liners drove organic saves:** `Perfectionism is just fear in a tuxedo`, `Hard choices, easy life`, `Progress > Perfection` — each triggered a real `"Send me this post"` DM. Self-questions (`Drop a 🔥`, `Comment READY`) drove 0 organic replies. **Fixed: `comment_loop.py:SELF_QUESTION_TEMPLATES` rotated to savable CTAs `Save this for your next low day 🔖` / `Send this to someone...`** instead of Q&A.
- **Reach peak** 237 (Aug 17, `Hard choices`), 178 (Aug 16, `Nobody coming`), 158 (Aug 23, `Boring businesses`) — reach tracks harsh/contrarian, not educational.

## Pitfalls
- **409 Already-Published on REELS** — `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` for REELS can return `409 Container ... has already been PUBLISHED` even though the publish succeeded (Composio polling race). Treat `"already been published"` as success, not a fatal error; do not retry 3×. Fixed 2026-08-28 in both `reel_post.py:publish_reel()` and `composio_post.py:publish_reel()` by returning success on that substring. Without it the 2026-08-27 evening reel marked `error` while the media was actually live.
- **Default `fields` on `INSTAGRAM_GET_IG_MEDIA` includes `total_views_count` etc which are NOT on Media node → 400 `Tried accessing nonexisting field`. Always override with `id,caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp,thumbnail_url,username,shortcode`.**
- **`INSTAGRAM_GET_USER_INSIGHTS` expects integer timestamps**, not ISO strings — string → validation error. Pass `since`/`until` as `int`.
- **`storedInFile` large responses** — when `tokenCount > ~15k`, Composio writes to `/tmp/composio/adhoc_*/...json` and returns only a pointer. Read `outputFilePath`.
- **`.env` on this box is placeholder tokens** — direct `graph.facebook.com` calls with it return `OAuthException 190`. Use Composio instead.
- **`GET_IG_USER_MEDIA` listing omits `like_count/comments_count`** (null) — must hydrate per-media via `GET_IG_MEDIA`.
- **Self vs organic comments** — 22/25 posts have exactly 1 comment and it is the bot's own question. Check `from.username` before counting engagement.
- **Rate & pagination** — `GET_IG_MEDIA` per-ID loop needs sleep; `GET_IG_USER_MEDIA` pagination uses `paging.cursors.after`, not `paging.next` URL.

## Verification
```bash
# 1. List + unwrap
~/.composio/composio execute INSTAGRAM_GET_IG_USER_MEDIA --account instagram_magog-daroo -d '{"ig_user_id":"28532466729677348"}'
# check outputFilePath, count data.data length

# 2. Hydrate one (must return like_count, not 400)
~/.composio/composio execute INSTAGRAM_GET_IG_MEDIA --account instagram_magog-daroo -d '{"ig_media_id":"18010728056939771","fields":"id,caption,like_count,comments_count,media_type,permalink,timestamp"}'

# 3. Reach last 14 days
python3 -c "from datetime import datetime; print(int(datetime(2026,8,14).timestamp()), int(datetime(2026,8,28).timestamp()))"
~/.composio/composio execute INSTAGRAM_GET_USER_INSIGHTS --account instagram_magog-daroo -d '{"ig_user_id":"28532466729677348","metric":["reach"],"period":"day","since":1786658400,"until":1787868000}'
```

References: `references/performance-baseline-2026-08-28.md`, `references/composio-field-pitfalls.md`, `references/reel-upgrade-and-fixes-2026-08-28.md`.
