# Instagram music in Stories/Reels — API limits (verified Aug 2026)

Asked mid-session: "can we add Drake-style music to the story?" Short answer:
**No, not via any API — not even Meta's own tools.** The correct answer here
saves a full wasted build; state it confidently.

## Facts (verified against tool schemas + live account)

- The licensed-music sticker in the IG app is exposed ONLY in the native mobile
  app. The Graph API has no parameter or endpoint for it; no scheduler
  (Buffer, Later, Meta Business Suite) can attach a licensed track either.
- The ONLY audio-related field on `INSTAGRAM_POST_IG_USER_MEDIA` is
  `audio_name`, and it just LABELS your original audio ("Original Audio").
  It does not select a track from a library.
- `media_type` enum is only `REELS` / `CAROUSEL` / `STORIES`; no music/music_id
  variant exists.

## Baked-in audio (the workaround trap)

Technically possible: render the story as an MP4 with ffmpeg
(`-loop 1 -i story.jpg -i track.mp3 -t 30 -c:v libx264 -c:a aac -shortest`),
publish via `video_file` + `media_type: STORIES` (container-id flow is
otherwise identical). It plays with sound.

BUT:
- It shows as **"Original Audio"**, not a music sticker with a clickable track.
- **IG audio fingerprinting detects copyrighted music** (Drake etc.) and
  mutes or flags the story. Only safe with tracks you own, royalty-free, or
  AI-generated — even then the API's container DID accept a video story
  (verified: container `18145212748535272` created, never published).

## User decision (carry this forward)

After hearing the options, these posts want **NO baked-in audio at all** —
the ffmpeg path was fully removed; stories stay image-only. If a trending song
is wanted, the user posts that ONE story manually from the phone where the
music sticker lives.

Policy: never promise licensed-music automation. Default = image story.
If user insists on audio, require a rights-verified track + warn about the
"Original Audio" label and fingerprint muting.