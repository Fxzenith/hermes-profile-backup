---
name: autoclipping
description: Convert YouTube video to face-tracked 9:16 Shorts/Reels.
---

# autoclipping — YouTube → Face-Tracked Vertical Shorts

Local repo at `/root/projects/autoclipping` (origin: Fxzenith/autoclipping). Pipeline converts a long YouTube video into vertical 9:16 Shorts with face-tracked reframe and synced single-line burned subtitles, then exports per-platform variants (shorts/tiktok/reels).

## Stack / where things live
- Orchestrator: `main.js` (Node). Runs the 6 steps below.
- Python deps are uv-managed in `.venv` at repo root — **always** run Python via `uv run python …` from the repo dir, never bare `python3` (system python lacks deps).
- JS deps installed via `npm install` (only `ffmpeg-static`; system `ffmpeg`/`yt-dlp` are used).
- MediaPipe model already downloaded to `models/face_detector.task`.
- Secrets in `.env` (OPENAI_API_KEY optional for AI clip selection; HF_TOKEN optional for multi-speaker tracking).

## Full pipeline (one command)
```bash
cd /root/projects/autoclipping
node main.js "<YOUTUBE_URL>" --approve
```
Steps executed by `main.js`:
1. **Fetch transcript** → `uv run python python/transcript.py --url "<URL>"` → `data/transcript.json`
2. **Clip selection** (manual/AI) — create `data/clips.json` + `data/clips_review.md`. Fields per clip: `start`, `end`, `title`, `hook` (first 3s quote), `reason`. The `--approve` flag skips the interactive gate; otherwise it pauses for ENTER then a yes/no prompt.
3. **Approval gate** — validates clips.json schema (title+hook required, 1–20 clips, 10s–600s each).
4. **Download + cut** → `node scripts/extract.js "<URL>"` → `assets/clip_NN.mp4` (720p, sentence-boundary snapped, resumable — skips already-cut clips; `--force` to re-cut).
5. **Face-tracked reframe** → `node scripts/render.js` → calls `scripts/face_reframe.py` (MediaPipe FaceMesh + Kalman smoothing, 9:16 720×1280, face in upper third, falls back to center crop) → `Outputs/NN_slug.mp4`.
6. **Multi-platform export** → `node scripts/export.js` → burns subtitles per platform (`scripts/subtitles_oneline.py --face-track`), appends CTA end-card, writes `data/titles.md` (A/B hook variants) + `data/run_manifest.json` (resume), output `Outputs/NN_slug[_platform].mp4`.

## Common one-shot commands
```bash
# transcript only
uv run python python/transcript.py --url "<URL>" --out data/transcript.json
# AI clip selection (needs OPENAI_API_KEY in .env)
uv run python python/clip_selector.py --transcript data/transcript.json --out data/clips.json
# cut clips only (resumes)
node scripts/extract.js "<URL>"
# reframe all clips
node scripts/render.js
# burn subtitles for one clip
CLIP_INDEX=0 uv run python scripts/subtitles_oneline.py --burn Outputs/01_clip.mp4 --burn-out Outputs/01_clip_final.mp4 --face-track
# multi-speaker track (needs HF_TOKEN)
uv run python scripts/face_reframe.py --speaker-track
# Ken Burns zoom on reframe
uv run python scripts/face_reframe.py --broll-zoom 1.12
```

## Pitfalls (verified from source)
- Folder is `video/` NOT `videos/`.
- Review file is `data/clips_review.md` NOT `review.md`.
- Every clip MUST have `title` + `hook` or render/export silently throws.
- `scripts/extract.js` enforces YouTube-only URLs and snaps clip `end` to the nearest sentence boundary (±5s) — expect clip end times to shift slightly from `clips.json`.
- yt-dlp needs a JS runtime: set `--js-runtimes node` in `~/.config/yt-dlp/config` (or it falls back to python module / npx).
- `face_reframe.py` validates all paths against ALLOWED_ROOTS (assets/Outputs/data/video/models) — don't pass absolute paths outside the repo.
- Box has limited disk (~12G free); the full download is ~190MB and lives in `video/`. Clean `video/full.mp4` between runs if space is tight.
- `main.js` pauses for ENTER between transcript fetch and approval even with `--approve` (the clip-selection step is manual/AI, not automatic).

## Raw-reframe artifact (Aug 2026)
`face_reframe.py` writes `Outputs/NN_slug.raw.mp4` (untouched 9:16 reframe). `export.js` burns ALL platform variants — including the canonical no-suffix `NN_slug.mp4` — from that raw file. Never burn in place: the canonical path is a *final* (subtitled + end-card), not a source. Resume = mtime(out) >= mtime(raw) per variant; re-rendering a clip deletes only its stale `.raw.mp4`, never finals.

## FaceMesh engine on this box
MediaPipe here (0.10.35, py3.12) has NO `mp.solutions` — face tracking runs via Tasks-API `vision.FaceLandmarker` with `models/face_landmarker.task` (setup.sh downloads it; legacy FaceMesh still preferred when importable). Symptom if both engines fail: log says "using BlazeFace fallback" and crop quality drops to single-point tracking.

## Face-tracked subtitles semantics
Safe-zone MarginV is the hard floor. Only when the sampled face sits abnormally low (nfy >= 0.45) does the caption lift above it (`HEIGHT*(nfy+0.10)`). Don't clamp tracked values TO the safe-zone floor — that disables the feature entirely.

## Verification contract
The real end-to-end test is `node scripts/export.js --platforms shorts` after assets exist, run TWICE: second run must burn nothing (resume proof). Full chain: `node main.js "<URL>" --approve`. Offline checks: transcript fetch writes `data/transcript.json`; deps check `uv run python -c "import youtube_transcript_api,yt_dlp,cv2,mediapipe,PIL,pydub"`; syntax sweep `uv run python -W error::SyntaxWarning -m py_compile scripts/*.py python/*.py && node --check main.js scripts/*.js`.
