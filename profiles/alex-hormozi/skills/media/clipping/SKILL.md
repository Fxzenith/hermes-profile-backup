---
name: clipping
description: "Use when the user runs /clipping with a YouTube URL."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [media, video, youtube, shorts, clipping]
    related_skills: [shorts-clipping-pipeline]
---

# /clipping — cut a YouTube video into N Shorts clips

## When to use

User invokes `/clipping <youtube-url> [n]` (e.g. `/clipping https://youtu.be/YGAjgLtJJFI 2`). Produce **exactly n** 9:16 clips with burned subtitles + end-card from that video and deliver them to the chat. Pipeline lives in `/root/autoclipping` — run every command from that directory.

## Workflow (headless — NEVER use main.js)

`main.js` blocks on an interactive `Press ENTER...` readline gate and exits in a non-TTY; `--approve` does NOT skip it. Run the stage commands directly; they read/write the same `data/` files.

```bash
cd /root/autoclipping
```

### 1. Parse the invocation
- URL = first token; strip `?si=` / tracking query params before passing to yt-dlp (`url.split('?')[0]`).
- n = second token if present, else **2**. Clamp to 1..5 (pipeline allows up to 20; stay practical).

### 2. Fetch transcript
```bash
uv run python python/transcript.py --url "<URL>"   # → data/transcript.json
```

### 3. Select exactly n clips (agent-side — no LLM key needed)
Read `data/transcript.json` and pick **n** segments yourself (you ARE the selector; `clip_selector.py` needs an API key that isn't configured on this box). Criteria:
- **Payoff endings** > abstract advice: a clip should end on a punchline, a number, a reveal, or a cliffhanger question — not tail off ("so yeah", "and stuff").
- **Concrete > abstract**: stats, proper nouns, stories, contrasts.
- 25–45s ideal; minimum 10s; max 600s; no time overlap between clips.
- Open with a hook: first ~3s should grab attention.

Write `data/clips.json`:
```json
{"clips": [{"start": 154.5, "end": 183.9, "title": "Only 18% of Blue Zone Centenarians Had Birth Certificates", "hook": "The Blue Zone data was never verified — 82% lacked birth certificates", "reason": "payoff: concrete 18% stat"}]}
```
Validate: `end > start`, every clip has `title` + `hook`. Also write `data/clips_review.md` (one line per clip: times, title, why it works).

### 4. Clean stale artifacts
```bash
rm -f assets/clip_*.mp4 Outputs/*.mp4 Outputs/frames/*.png data/run_manifest.json data/subtitles_oneline_clip*.ass
```
(Fresh run only — never skip this: stale `NN_*` from a previous run with different clip counts breaks the resume manifest.)

### 5. Extract → render → export
```bash
node scripts/extract.js "<URL>"     # → assets/clip_NN.mp4
node scripts/render.js              # → Outputs/NN_slug.mp4 (MediaPipe 9:16 face-track reframes)
node scripts/export.js              # → burned + end-carded finals, per platform
```
- `export.js` burns the canonical no-suffix file (shorts) LAST and resumes from the manifest — the path-collision bug is fixed; don't "work around" it by delivering only `_tiktok` variants.
- Default platforms from config: `shorts, tiktok, reels`. For faster runs pass `--platforms shorts`.

### 6. Verify before delivering (non-negotiable)
```bash
# a) ASS sync per clip — must print "ALL CHECKS PASSED" (rc=0)
uv run python /root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py --clip 1
uv run python /root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py --clip 2

# b) end-card present: last frame of each final must be a ~15KB solid card,
#    NOT a ~600KB+ speaker frame (raw reframe shipped by the old bug)
for f in Outputs/0*_*.mp4; do
  n=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "$f")
  last=$((n-2))
  sz=$(ffmpeg -v error -y -i "$f" -update 1 -frames:v 1 -vf "select=eq(n\,${last})" -f image2 /root/autoclipping/_chk_last.png 2>/dev/null && stat -c%s /root/autoclipping/_chk_last.png)
  echo "$f: frames=$n lastframe_bytes=$sz"
done
```
Any final whose last frame is large (>100KB) → re-run `node scripts/export.js` after deleting `data/run_manifest.json` and re-check. All outputs must pass both checks.

### 7. Deliver to chat
Attach the no-suffix (shorts) finals — one per clip, inline `MEDIA:/root/autoclipping/Outputs/NN_slug.mp4` paths, with a one-line label each (title + duration). If the user asked for a specific platform variant, deliver the `_<platform>` files instead.

## Pitfalls
- **uv, not pip/system python** — PEP 668 externally-managed; everything runs `uv run python`.
- **/tmp is NOT durable on this VPS** — probe frames go to `/root/autoclipping/_chk_last.png`, never /tmp.
- **SyntaxWarnings from subtitles_oneline.py are harmless** (invalid escape sequences in docstrings) — ignore.
- **MediaPipe** may be missing `mp.solutions` on newer wheels; the pipeline carries a BlazeFace fallback.
- **Manifest schema collision (fixed 2026-08-11)**: `extract.js` and `export.js` share `data/run_manifest.json` but write different schemas (extract: `{clips:[...]}`, export expects `{entries:{...}}`). Empty-clip resume crashed export with `Cannot read properties of undefined (reading '0')`. export.js `loadManifest()` now normalizes foreign schemas to `{updatedAt, entries:{}}`. Symptom to watch: export crashing right after the `N clip(s) x platforms` line while `data/run_manifest.json` exists.
- **Clip count**: user's "a couple" = n=2. Count in the invocation wins (`/clipping <url> 3` → exactly 3).
- Always verify with the frame probe — a file can play fine with the end-card missing (duration looks right, frames aren't there).

## Support
Deep-dive on the underlying engine: `skill_view` the `shorts-clipping-pipeline` skill (all rules #1–#12, ASS formats, clip scoring criteria).