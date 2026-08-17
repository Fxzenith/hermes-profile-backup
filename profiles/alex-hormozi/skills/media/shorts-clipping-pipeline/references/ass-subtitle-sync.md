# ASS Subtitle Sync — field semantics, bugs, and verification (2026-08 session)

Session context: `/root/autoclipping` YT Clipper; user hit two distinct sync bugs in
`scripts/subtitles_oneline.py` + one duplicate-burn bug in `main.js`.

## ASS Style line field order (Aegisub/libass)

```
Style: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,
       Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,
       BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
```

- **Alignment**: 1-3 = bottom, 4-6 = middle, 7-9 = top; 2 = bottom-center (correct for
  shorts subtitles), 5 = middle-center (WRONG — text lands ~45-52% of frame height,
  over the face when face-tracked).
- **MarginV**: pixels from the bottom edge (for bottom-anchored). Face-tracking
  computes margin_v from face position (lower third when face is high in the crop;
  `MARGIN_V` fallback = 10% of height).
- Toggling: `BorderStyle=4` (round) + `Outline` + `Shadow`; large shadow (e.g. 7)
  commonly used.

Valid emitted template (placeholders substituted by `build_ass` — assert against the
RENDERED line, not the template strings):
```
Style: Base,Sans,48,&H00FFFFFF,&H000000FF,&H00000000,&H70000000,1,0,0,0,100,100,0,0,4,7,0,2,72,72,128,1
```

## Bug 2 — wrong clip's subtitles (CLIP_INDEX default)

Old: `idx = os.environ.get("CLIP_INDEX", "0")` in `main()`.
Burn for clip 2 used clip 0's transcript. `main.js` never set CLIP_INDEX → pipeline-wide.

Fix — `resolve_clip_index(burn_path, clips)`:
```
1. re.match(r"^(\d{2})_", basename) → int(group(1)) - 1   (filename is 1-based)
   (bounds-checked against len(clips); ValueError if out of range)
2. CLIP_INDEX env isdigit + in range
3. len(clips) == 1 → 0
4. else ValueError("cannot determine clip ...") — never default to 0
```

Detection symptom: vision reads clip-01 catchphrases on clip-02 video; ASS cue dump
shows wrong words but plausible timing. The ASS cue dump against source transcript is
the definitive check: `source_t = clip.start + cue_t`.

## Bug 3 — missing opening subtitles (window filter)

Old: `if ts < cs or ts >= ce: continue` — dropped any segment starting before clip
start. First cue appeared at 2.36s instead of 0.00s.

Fix: overlap-window filter `if te <= cs or ts >= ce: continue` + existing clamp
`ws0 = max(0.0, ts - cs)`. Verified: first cue at 0:00:00.00.

## Bug 4 — double burn / in-place overwrite

- ffmpeg errors "Error opening output file ... Invalid argument" when input==output
  path. Burn to temp, `mv -f` over.
- Idempotency (main.js): if output `_subtitled.mp4` exists and `mtime >= input
  mtime`, skip the burn (log "already subtitled").
- Also: don't rename/mass-overwrite the source reframe file after subtitling if the
  pipeline should be re-runnable (write `NN_slug_subtitled.mp4` and keep inputs).

## Verification without a vision model

1. Rebuild ASS in-process (no burn): `build_ass(transcript, [clip], face_track=False)`
2. `[l for l in ass.split("\n") if l.startswith("Dialogue")]` → parse `start,end,text`
   (`l.split(",",5)`, strip `{\fad(...)}` tags with regex).
3. assert: first cue near 0; cue text matches transcript at `clip.start + cue_t`;
   coverage of clip duration high.
4. Extract frames with `ffmpeg -ss <t> -i <clip> -frames:v 1 <dir>/f.png` (project
   dir, NOT /tmp — /tmp vanished across tool calls this session and vision returned
   "media file not found" for files that existed two calls earlier).

Note: `clip_selector.py` scoring (payoff/concreteness) also lives in the pipeline and
must be reflected in the LLM prompt criteria (user drives this — see SKILL.md).