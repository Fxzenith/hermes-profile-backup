---
name: social-video-mastering
description: ffmpeg LUFS audio + ASS karaoke captions for 9:16 clips.
category: media
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [video, ffmpeg, shorts, reels, tiktok, captions, audio, lufs]
    related_skills: [video-use, better-icons]
---

# Social Video Mastering (short-form 9:16)

## When to Use
Use this skill when building or improving a short-form vertical video clipping
pipeline (YouTube Shorts / TikTok / IG Reels): quiet or distorted clip audio,
captions hidden behind platform UI, plain (non-highlighted) subtitles, 720p output
instead of native 1080×1920, or any "make this reel retain better" request. It
covers the four retention-critical engineering layers most clipping scripts skip.

Engineering layer between raw clip extraction and publish. Four retention layers
most clipping scripts skip: audio loudness, active-word caption highlight, platform
safe-zones, native resolution.

## When this applies
- Clip pipeline copies audio through (`-c:a copy`) with no loudness target.
- Captions plain white, no active-word emphasis.
- Subtitle `MarginV` sits inside platform UI occlusion band.
- Output 720×1280 but should be native 1080×1920.
- "quiet" / "muffled" / platform auto-lowers volume (YouTube -8 dB penalty).

## 1. Audio: LUFS loudness normalization (MOST-MISSED)
Platforms measure perceived loudness in LUFS and server-side ATTENUATE clips above
target — YouTube Shorts can drop ~8 dB if Integrated LUFS too hot. Normalize first.

**Integrated LUFS targets:** Shorts -14.0 (TP -1.0); TikTok/Reels -10..-12 (TP -1.5).
Master to Shorts -14 to avoid YT's -8 dB penalty (worst case); TikTok plays slightly
quiet but clean.

**Order:** spectral clean → compress → loudnorm → (TP inside loudnorm).
- `highpass=f=80` (rumble), `deesser` (5–8 kHz), `acompressor=ratio=3` (dialogue).
- **Two-pass `loudnorm`** REQUIRED: pass 1 `print_format=json` to MEASURE, pass 2 feed
  `measured_I/TP/LRA/thresh/offset` back so it hits the real target. Single-pass only
  approximates. Re-encode AAC `-ar 48000 -b:a 192k`, keep video `-c:v copy`.

See `references/lufs_master_recipe.md` for exact filters + parse logic (validated here:
loudnorm, highpass, deesser, acompressor, alimiter, afftdn all present).

## 2. ffmpeg in-place GOTCHA (cost one real bug)
ffmpeg cannot read+write the same path (`Output same as Input — exiting`). Stage via
sibling temp `in.audio_master.mp4` then `shutil.move(temp, in)`. Detect with
`Path(out).resolve() == Path(in).resolve()`.

## 3. Captions: karaoke active-word highlight (retention)
Guide's #1 caption rule: word-level timing + high-contrast active-word highlight.
- 1–3 words/cue (pipeline's WORDS_PER_CUE).
- Tint FIRST (active) word per cue: `{\c&HBBGGRR}`text`{\c&HFFFFFF}` (revert to white).
  Colour is `&HBBGGRR` (BGR). `#FFE600` → `&H00E6FF`. Helper:
  `r,g,b=hex[0:2],hex[2:4],hex[4:6]; return f"&H{b}{g}{r}"`.
- NEVER backslash inside an f-string expr (`f"{\c{x}}"` = SyntaxError); concatenate
  literals: `"{\\c"+hc+"}"+text+"{\\c&HFFFFFF}"`.

See `references/ass_karaoke_highlight.md`.

## 4. Platform safe-zones (don't bury captions under UI)
Bottom-margin fraction of canvas height (higher = text higher, clear of UI):
Shorts 0.22 / TikTok 0.27 / Reels 0.20; sides 0.08–0.10. Load from config, not hardcoded.
(Old values 0.12/0.18/0.20 let Reels/TikTok text collide with UI.)

## 5. Resolution
Render final 9:16 at NATIVE 1080×1920, not 720×1280. Reframe reads
`outputWidth/outputHeight` from config (default 1080×1920), not a module constant.

## Verification
- Audio: `--report` → measured I then target I match (e.g. -21.2 → -14.0). ffprobe output.
- Captions: grep burned ASS for highlight hex; one `Dialogue` per cue.
- Safe-zone: bottom N% of a rendered frame clear of text.
