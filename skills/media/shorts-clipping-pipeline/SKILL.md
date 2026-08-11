---
name: shorts-clipping-pipeline
description: "Use when building/fixing YouTube Shorts clipping pipelines."
platforms: [linux]
---

# Shorts YouTube-Clipping Pipeline

## When to use

Working on any automated "YouTube video → Short clips" pipeline: cutting clips from a transcript, face-tracked 9:16 reframes, burning synced subtitles, or fixing clip sync/quality/timing. Reference project: `/root/autoclipping` (user's YT Clipper).

## Architecture (reference: /root/autoclipping)

```
1. python/transcript.py        → data/transcript.json            (youtube-transcript-api)
2. clip selection (LLM)        → data/clips.json                 (python/clip_selector.py, JSON-schema validated)
3. node scripts/extract.js     → assets/clip_NNN.mp4             (yt-dlp + ffmpeg cut)
4. scripts/face_reframe.py     → video/ or Outputs/NN_slug.mp4   (MediaPipe → 9:16 face-tracked crop)
5. scripts/subtitles_oneline.py → Outputs/NN_slug.mp4            (burned ASS, one-line, faded)
```
Orchestrator: `main.js` (Node); `scripts/render.js` wraps the Python reframe. All Python runs via `uv run python` (uv venv; system pip is PEP 668-externally managed on this box). Subtitle engine is ASS + ffmpeg subtitles filter; clip scoring lives in `python/clip_selector.py`, grading report in `data/clips_quality.md`.

### Optional added stages (all config-gated, all verified working)
- `scripts/export.js` — multi-platform publisher: burns a **safe-zone-aware** subtitle variant per platform (`_shorts/_tiktok/_reels`), optionally appends a CTA **end-card**, writes `data/titles.md` (A/B hooks) and `data/run_manifest.json` (resume). Replaces `main.js`'s inline `burnSubtitles` (step 6).
- `scripts/endcard.js` — branded `Follow for more` tail (~1s) appended to a clip.
- `scripts/speaker_diarize.py` — optional pyannote.audio diarization for **multi-speaker** tracking (`--speaker-track` / `HF_TOKEN`); degrades to largest-face when deps/token absent.
- `--audio <assets dir>` on clip_selector — **emotion/silence** audio scoring (Munch-style prosody) per clip.
- `--trends` on clip_selector — **trend-aware selection** (pull live market tickers via web/Jina and lean the LLM prompt toward them).

## Subtitle-burn rules (each of these was a real bug this session — don't repeat)

### Rule 1: ASS Alignment must be 2 (bottom-center), never 5 (middle-center)
MarginV face-tracking (pushing text up off the face) only works for bottom-anchored text. Alignment=5 renders subtitles at ~45-52% of frame height — smack on the speaker's face. In the ASS Style line, Alignment is the field right before `MarginL,MarginR,MarginV`:
```
Style: Base,<font>,<size>,PCol,SCol,OCol,BCol,Bold,Ital,UL,S0,SX,SY,Sp,Ang,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
```
Check the *rendered* style line (template placeholders like `{MARGIN_V}` get substituted by build_ass): e.g. `...,0,2,72,72,128,1` — Alignment field = 2 (bottom-center). Valid one-line style: `Style: Base,Sans,48,&H00FFFFFF,&H000000FF,&H00000000,&H70000000,1,0,0,0,100,100,0,0,4,7,0,2,72,72,128,1`.

### Rule 2: per-clip transcript index must come from the filename, never an env default
The old code read `CLIP_INDEX` env with a silent `"0"` default → every non-first clip got clip #1's words burned on top of its own audio (correct-looking times, totally wrong content). Correct resolution order:
1. `NN_` prefix of the burn input filename (`02_boring….mp4` → index 1)
2. `CLIP_INDEX` env var as explicit override
3. if only one clip → 0
4. else raise a clear error — **never silently default**.

### Rule 3: clip transcript windowing must use overlap, not "start inside"
Filter `ts < cs → drop` loses audio present at the clip's opening (segment starts before cs still overlaps the clip) → ~2.3s of missing subtitles at the start. Correct filter: keep segment when `te > cs and ts < ce`, then clamp cue offset `ws0 = max(0, ts - cs)`.

### Rule 4: burns must be idempotent; never overwrite input in place
- Re-running a pipeline must not burn on top of already-burned subtitles: skip the burn when the `_subtitled` output exists and is newer than the input (mtime-based idempotency).
- ffmpeg cannot read and write the same path (`Error opening output file`): burn to temp, then mv over.

### Rule 5: ffmpeg `-vf` after a SECOND `-i` attaches to THAT input, not the source
Classic end-card bug: `-f lavfi -i color=... -vf drawtext -f lavfi -i anullsrc=...` → `-vf` binds to the *next* input (`anullsrc`), so the text draw never applies to the video and ffmpeg errors (`Option vf ... cannot be applied to input url anullsrc`). Fix: put the effect in a `filter_complex` (`[0:v]drawtext=...[v]`, then `-map '[v]'`), or place `-vf` immediately after the input it belongs to. Multi-input ffmpeg builds belong in `filter_complex`, not interleaved `-vf`.

### Rule 6: appending an end-card = use the **concat FILTER**, not `-c copy` and not even `-f concat` demuxer
The old-source clip and the generated end-card differ in fps/resolution/codec params **and in pixel aspect ratio** (SAR). Two failure modes seen in practice:
1. `-f concat -c copy` on mismatched streams → glitches or silent drops.
2. Crucial: even `-f concat` + re-encode (`-c:v libx264 -c:a aac`) **silently truncates the video track** — the concat demuxer can't reconcile source SAR **404:405** (produced by `extract.js`'s `pad` filter) with the end-card's **SAR 1:1**, so you get a ~17s video track paired with an 18-19s audio track. The file *plays* and the duration *looks* right, but the end-card video frames simply aren't there (last frame is still the speaker, ~700KB instead of a ~15KB solid card). Checking only duration hides this.

Correct fix — the **concat filter** (decode + remux, one ffmpeg pass), normalizing both streams to common SAR/fps/timebase first:
```
ffmpeg -y -i in.mp4 -i endcard.mp4 -filter_complex \
  "[0:v]scale=w=iw:h=ih,setsar=1,fps=30,setpts=PTS-STARTPTS[va]; \
   [1:v]setsar=1,fps=30,setpts=PTS-STARTPTS+${durS}/TB[vb]; \
   [va][vb]concat=n=2:v=1:a=0[outv]; \
   [0:a]aformat=sample_rates=48000:channel_layouts=stereo[a0]; \
   [1:a]aformat=sample_rates=48000:channel_layouts=stereo[a1]; \
   [a0][a1]concat=n=2:v=0:a=1[aout]" \
  -map "[outv]" -map "[aout]" -c:v libx264 -preset fast -crf 20 -c:a aac out.mp4
```
Notes: `fps=30` normalization is what lets mismatched optional-fps sources (23.976 vs 30) concat; the video+audio `concat` filters both require identical SAR/size/pix_fmt and sample rate/channels/layout respectively — normalize BOTH or the filter refuses to configure (`Failed to configure output pad` / `Input link ... SAR 1:1) do not match ... SAR 404:405`). `durS` = end-card length; offset the end-card video PTS by `durS/TB` so it lands *after* the source.
**Verify by frame count, not duration:** `ffmpeg -count_frames` (or `nb_read_frames`) — can a solid end-card frame be extracted near the last frame (`-update 1 -frames:v 1 -vf "select=eq(n\,N-2)"`)? Expect a small ~15KB PNG. A speaker-frame (~700KB) at frame N-2 means the end-card never got muxed in; re-check the concat filter, don't trust the +1s duration growth.

### Rule 7: platform safe-zones change ASS margins (tiktok/reels are not shorts)
Each platform's UI covers a different bottom/side. The Style MarginL/MarginR *and* per-cue MarginV must move when targeting a different platform. `shorts ~ 10%`, `tiktok ~ 12-18%`, `reels ~ 20%`. Verify on the *emitted* Style line: for `--platform tiktok` you should see `...,0,2,86,86,0,1` (int(720*0.12)=86 side margins), not the shorts default `72,72,128`.

### Rule 8: styled captions (keyword bold + emoji) = ASS inline tags
Bold a keyword with `{\b1}word{\b0}` per word; prepend one emoji per cue. Emit each word ASS-escaped individually. Esports/numbers/`$`-amounts and power verbs (`secret`, `wait`, `never`, `beat`, `why`...) get `{\b1}`. A dict `{word: emoji}` prepends the glyph once before the first matching word so it reads naturally (`1️⃣ {\b1}first{\b0} investor`).

### Rule 9: multi-speaker = diarize first, then cluster face centers
Largest-face crop fails on panels. Optional: run pyannote diarization → time ranges per speaker; k-means cluster the sampled face centers into N centroids (N = speakers); at each frame pick the face whose center is nearest the *active* speaker's centroid. Keep it a graceful fallback — if pyannote/`HF_TOKEN`/CUDA are missing, return the largest face. Diarization is CPU-ok; call `pipeline.to(torch.device('cpu'))` when no CUDA. Face re-ID networks are overkill — center proximity to a diarized-speaker centroid is enough.

### Rule 10: emotion/silence audio scoring via RMS (text markers miss prosody)
`clip_selector`'s payoff/concreteness heuristics only guess from text — the audio half is invisible. Add a pydub pass: sample RMS dB ~50 Hz, split into 5 chunks, reward a clip whose *tail* holds energy (normalized tail mean high, near-silence <25%) vs fizzle (quiet dangling tail). Peak dBFS and an end-silence spike add signal. Score post-extraction `--audio assets/` maps each `clip_NN.mp4` to its own clip.

### Rule 11: trend-aware selection via web — boilerplate kills the signal
Pulling "trending topics" from a Jina-reader page returns `title / latest / markdown / source` garbage unless you (a) strip the Jina header up to the `Markdown Content` marker, (b) drop an aggressive stopword list, and (c) **only keep tokens seen ≥3×** — real story/recurring keywords survive, single-occurrence chrome doesn't. Verified: returns real tickers (`nvda`, `intc`, `goog`). Don't feed raw top-`n` tokens to the LLM without this filter.

## Sync verification without vision

1. Dump ASS cues: iterate `ass.splitlines()` filtering `startswith("Dialogue")`, parse `start,end,text`.
2. Map clip cue time → source time: `source_t = clip.start + cue_t`, confirm text matches the transcript at that window.
3. Coverage: first cue should start near clip t=0; a big gap at clip start = Rule 3 violation; wrong text = Rule 2 violation.
Vision reads are a *secondary* confirmation — the actual ASS cue dump against the source transcript is primary proof.

Extracting a specific frame (e.g. an end-card / subtitle check) on a concat or re-encoded file: probe the *real* frame count first (`ffmpeg -count_frames` / `ffprobe nb_read_frames`; don't assume 30fps or derive from duration), then grab `-update 1 -frames:v 1 -vf "select=eq(n\,N-2)"` by absolute frame index. `-ss` time-seeks against a timeline that no longer matches the container can return `Output file is empty, nothing was encoded` even on a valid file — a broken concat produces exactly this wrong-layout symptom. Use writers `/root/…png` (no image-sequence pattern or add `-update 1`).

## Clip selection scoring (user's explicit direction: payoffs > abstract)

- `score_payoff()`: last ~4s of the clip; payoff/cliffhanger markers (`"that's why"`, `"turned out"`, `"and that's"`, ending `?`) add; dangling tails (`"and then"`, `"so yeah"`, `"and stuff"`, `"because"`) subtract. Labels: payoff ≥0.6 / weak ≥0.2 / dangling.
- `score_concreteness()`: numbers, proper nouns, quotes/"said", story markers, contrasts lift; abstract-advice markers (`you should...`, `hard work pays off`) lower. Labels: story ≥0.6 / mixed ≥0.4 / abstract.
- CLI: `uv run python python/clip_selector.py --transcript data/transcript.json --out data/clips.json --score-only [--min-payoff 0.6]` → writes `data/clips_quality.md`; rc=0 ok, rc=1 error, rc=2 = below min-payoff gate. In LLM mode, min-payoff failures feed back into the retry loop.
- LLM system prompt must rank "Payoff ending" and "Concrete story > abstract advice" near the top of the criteria.

## Pitfalls

- `jsonschema` isn't guaranteed installed → `import jsonschema` must be inside try/except ImportError with manual fallback; unguarded import crashs validation on any venv lacking it.
- dev marker lists must not overlap (same phrase in both payoff and dangling lists nets the score to ~0).
- MediaPipe: newer wheels dropped `mp.solutions` — carry a BlazeFace tasks fallback or pin `<1.0`.
- `/tmp` on this VPS is not durable across tool calls: extract verification frames to a project-local dir (e.g. `_chk/`) before vision-analyzing, or get "media file not found"; change path/strategy instead of retrying the same call (tool-loop guard).
- When a tool fails repeatedly, read the latest error before retrying — root cause often changed (this session: retired Gemini vision model 404, not bad file paths).
- **Patching a raw-string regex through the patch tool can double-escape it.** `r"[$\\d]"` written in a source edit can land as `r"[$\\\\d]"` → literal backslash + `d`, *silently* no longer matching digits. After any patch to a regex, verify the actual on-disk content (read the line), not just that the diff applied. A broken `\d`/`\s` class fails silently (no exception — just never matches).
- **Resume-mismatch: files per clip index vs the clips.json length.** `face_reframe`/`export` key outputs by `clips.json` index (0-based), but stale `NN_*.mp4` from an earlier run with *more* clips linger in Outputs. When clips shrink, the old high-index files stay and the manifest (written from the *current* clips) can't account for them. Clean stale `NN_*` before a new run, and don't trust old Outputs file names as ground truth — always start from `clips.json`.
- **`uv sync` with pyannote/torch is a large install** but works headless. pyannote's `Pipeline.from_pretrained(use_auth_token=token)` may raise portability lint; wrap the whole diarization block in try/except so a token/dep failure degrades to the existing largest-face path instead of crashing the reframe.

## Support files
- `scripts/verify_clip_sync.py` — dump + check ASS cue sync without burning (content matches source window, coverage, first-cue gap).
- `references/ass-subtitle-sync.md` — deeper detail: ASS field semantics, clip-index resolution, missing-segment root cause, emitted-style validation.
- `references/multiplatform-export-styled-captions.md` — platform-specific ASS margin calculations, emoji/keyword styling, end-card concat filter.
- `references/telegram-distribution.md` — sending final clips to Telegram channel via Bot API; token extraction, chat ID config, curl patterns, pitfalls.