# Multi-platform export, styled captions, end-card, audio & trend-aware selection

Session-specific implementation detail added to `/root/autoclipping` (all verified working in
a single run: 6/6 checks + a real `node scripts/export.js` that produced `_tiktok`/`_reels`
variants, end-cards, titles.md, run_manifest.json).

## New files
- `scripts/export.js` — orchestrator for step 6. Per clip: burn subtitles per platform via
  `subtitles_oneline.py --platform P --face-track`, optionally append end-card, write titles.md
  + run_manifest.json. Resume: skip a platform output when it exists and is newer than its input.
- `scripts/endcard.js` — `--in X.mp4 --out Y.mp4`. Two-pass ffmpeg: (1) render a solid-color +
  centered-text card at the source's w/h/fps via lavfi `color=` + `filter_complex` drawtext,
  with `anullsrc` silent audio; (2) concatenate source + card using the **concat FILTER**
  (decode + remux), NOT the `-f concat` demuxer and NOT `-c copy`. The source clips carry
  SAR 404:405 (from `extract.js`'s `pad`) vs the card's SAR 1:1 — both the demuxer-`-c copy`
  AND the demuxer-re-encode paths **silently truncate the video track** (file plays, duration
  looks +1s, but the card frames are absent). Normalize both streams first:
  `[0:v]scale,setsar=1,fps=30,setpts=PTS-STARTPTS[va]; [1:v]setsar=1,fps=30,setpts=PTS-STARTPTS+durS/TB[vb]; [va][vb]concat; [0:a]aformat=48000/stereo; [1:a]aformat=...; concat audio`. Verify the card landed via **frame count / last-frame extract (~15KB PNG)**, never duration alone. See Rule 6 in SKILL.md.
- `scripts/speaker_diarize.py` — `diarize(video)` → `[{start,end,speaker}]` or None. Needs
  `HF_TOKEN` (`pyannote/speaker-diarization-3.1` is gated) + `--speaker-track` flag.
- `subtitles_oneline.py` added `--platform`, `--no-keyword`, `--no-emoji`; safe-zone margins,
  keyword/emoji styling, per-segment `trailing_silence_ratio`.
- `face_reframe.py` added `--speaker-track`, `--broll-zoom` (Ken Burns zoompan).
- `clip_selector.py` added `--audio` (per-clip RMS scoring) and `--trends` (web topic fetch).

## Config keys (config.json)
```json
"subtitleConfig": { "platforms": ["shorts","tiktok","reels"], "safeZones": {...},
  "keywordEmphasis": true, "keywordEmoji": true, "trailingSilencePerSegment": true },
"endCard": { "enabled": true, "durationMs": 1000, "text": "Follow for more",
  "backgroundColor": "#000000", "textColor": "#FFFFFF" },
"bRoll": { "enabled": false, "zoomRatio": 1.12 },
"export": { "titlesFile": "data/titles.md", "hookVariants": 3, "manifestFile": "data/run_manifest.json" }
```
`render.js` auto-injects `--broll-zoom` (if bRoll.enabled) and `--speaker-track` (if `HF_TOKEN` set).

## Keyword/emoji styling (cheap heuristics, no NLP)
- Bold: numbers, `$`-amounts (`_looks_big_number` regex), and KEYWORD_HINTS
  (`secret, million, strategy, market, wait, never, beat, why, how, first, real...`).
- Emoji: dict `{win:🏆, money:💰, profit:📈, loss:📉, secret:🤫, board:💎, wait:⏳, ...}` — prepend
  one glyph before the first matched word per cue.

## Trend fetch (Jina via `r.jina.ai/FINANCE_URL`)
- Strip text up to the first `Markdown Content` marker (page chrome).
- Aggressive stopword list, require `len(tok)>=4`.
- **Keep only tokens seen ≥3×** — that single rule turns boilerplate noise into real tickers
  (`nvda, intc, goog, amzn, aapl`). Raw top-N would return `title/latest/source`.

## Resume/manifest
- `extract.js` cuts write `data/run_manifest.json`; per-clip retry once on transient ffmpeg
  failure; `--force` re-cuts; skip asset when newer than the `full.*` source.
- Clean stale `NN_*` in Outputs before runs (outputs are indexed by clips.json, and old higher
  indices linger when clips shrink).