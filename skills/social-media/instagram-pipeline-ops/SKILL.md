---
name: instagram-pipeline-ops
description: "IG daily pipeline: no-repeat quotes, black reel frames."
version: 0.1.0
author: Hermes
platforms: [linux]
metadata:
  hermes:
    tags: [Instagram, Reels, Automation, QuotePool]
---

# Instagram Auto-Poster Pipeline Ops

Maintains the daily @ze.nith001 auto-post pipeline at `/root/Instagram daily auto-post`: deterministic no-repeat quote cards for the 11:00 image post (`morning` slot) and 18:00 reel (`evening` slot), plus the reel frame renderer that must always produce a pure-black 1080×1920 background. Does NOT publish to Instagram itself — posting happens inside the pipeline scripts via Composio.

Deps: Pillow + numpy in the box's python; ffmpeg/ffprobe for reel encode and decoded-frame verification.

## When to Use
- "quotes keep repeating", "give 11:00 and 18:00 their own quotes", "do not repeat posts"
- "reel background is not pure black", "gray smudges around the card", card-edge screenshots with arrows
- "which quote posts next", "re-run the pool determinism test", "backfill pool history"
- "send a test reel" / "clean up test artifacts" after a render fix

## Prerequisites
- Repo root: `/root/Instagram daily auto-post` — all paths below are relative to it
- Cron source (do not guess IDs, `cronjob` action=list first): 11:00 SAST image post `18d280b4af39` (runs `scripts/composio_post.py`), 18:00 SAST reel `7a4c465fbd09` (runs `scripts/reel_post.py`)
- Credentials live in `.env` at repo root (Composio). PIXABAY_API_KEY stays in the pipeline `.env`.

## Quick Reference
| Item | Path / value |
|---|---|
| Quote pool state | `logs/quote_pool_state.json` |
| Pool module | `scripts/quote_pool.py` |
| Slots | `"morning"` (11:00), `"evening"` (18:00) |
| Pool cards | 32 = 4 topics × 8 tweets; id `f"{topic}#{tweet_idx}"` — 16 days before LRU recycle |
| Recycle policy | never-used first (pool order), then LRU by last-use date; blocked = same-day other slot; no back-to-back repeats |
| Pick audit | `logs/quote_pool.log` — every assignment logs date, slot, id, topic, reason (`fresh (never used)` / `LRU recycle (last used <date>)`); state history entries carry a `why` field |
| AM card theme | `cron_post.py` config `theme: "dark"` → `#000000` |
| Reel frame | `post_story.make_story_image()` — flat `#000000` canvas, PNG output |
| Reel encode | `reel_renderer.render(card.png, track.mp3, out.mp4)` |
| State guards | `logs/reel_state.json` (once/day), `logs/story_state.json` |

## How to Run
`composio_post.py generate(slot=...)` picks the quote from the `scripts/quote_pool.py` pool, `cron_post.py` builds the card (1080×1350), `reel_renderer.py` composes the 1080×1920 pure-black frame and burns the audio. Both cron jobs call the same `generate()` — the slot argument is what keeps the two quotes independent. Invoke everything through the `terminal` tool with cwd = repo root.

## Procedure (numbered)
1. **Pick a quote for a (slot, date)** — deterministic, idempotent: `python3 scripts/quote_pool.py pick morning 2026-08-10`. Same date+slot always returns the same card; retries never double-assign; the two slots never collide on a day.
2. **Wire a new post script**: copy the `generate(slot=...)` pattern — get pool entry, `build_post_config(template, folder, tweet_idx=tmpl["tweet_idx"])`, caption = `tmpl['tweet'] + render_hashtags(select_hashtags(topic))` (caption must use the pinned tweet, NOT `template['hook']`). Record `slot`, `quote_id`, `tweet_text` into `post_meta.json`.
3. **Backfill history** so the account's past isn't repeated: scan `workspace/*/post-*/post_meta.json`, and for each `template_or_topic` call `quote_pool.mark_backfilled([(date_dir, topic), ...])` — historically only `tweet_idx=0` was ever rendered, so it marks `topic#0` used.
4. **Reel frame black**: in `post_story.make_story_image()` the bg must be `Image.new("RGB", (1080, 1920), (0, 0, 0))` pasting the centered card. Never stretch+blur+darken a copy of the card as the backdrop (GaussianBlur → gray smears around the card) — that is the classic "not pure black" bug. Save composite as **PNG** (`reel_frame.png`), not JPEG.
5. **Encode**: `python3 scripts/reel_renderer.py <card.png> <track.mp3> <out.mp4>`. Duration = track length exactly (output `-t` + `-shortest`, verified ≤ 0.15 s drift).
6. **Verify** (see Verification).
7. **State guards**: `reel_state.json` / `story_state.json` keep one reel/story per day — reruns same day are silent no-ops (exit 0). Quote itself is locked per date so re-renders reuse the same card.

## Pitfalls
- **Never run pool sims or the CLI against the production `logs/quote_pool_state.json`**. The `pick` CLI writes real assignments. A 30-day simulation run this way polluted the state with fake future dates — had to roll back (`assignments`/`used`/`history` surgical `pop`). Set `quote_pool.STATE_FILE` to a scratch path in test harnesses.
- `tweets` are multi-line; comparing `caption.splitlines()[0]` to the full `tweet_text` field fails — use `tweet_text in caption` (in-substring).
- JPEG adds ±1..3 LSB noise on "pure black" regions; if the check must be byte-exact, keep the frame PNG at every stage.
- Card corners on the AM (`#000000`) vs reel frame margins: verify the *decoded* MP4 pixels, not just the PNG — H.264 yuv420p rounding can lift blacks.
- `reel_renderer.py` output must end `-movflags +faststart`; a missing `.mov` container confuses uploaded media.

## Verification
Run the shipped script (proves frame is truly black) and the 30-day sim (proves no-repeat/determinism):

```bash
python3 ~/.hermes/skills/instagram-pipeline-ops/scripts/verify_pure_black.py \
    "/root/Instagram daily auto-post/workspace/<date>/post-NN/reel_frame.png"
python3 ~/.hermes/skills/instagram-pipeline-ops/scripts/verify_pure_black.py \
    "/root/Instagram daily auto-post/workspace/<date>/reel.mp4"
```

Exits 0 only when all sampled margins (top/bottom 100px, left/right 40px) are `(0,0,0)`. Pair with the pool sim (`~/.hermes/skills/social-media/instagram-pipeline-ops/scripts/sim_quote_pool.py <repo_root> "" 100`) — 100 selections on a scratch STATE_FILE proving no-repeat-before-exhaustion, determinism, and per-pick `why` logging — without touching production state or the audit log.