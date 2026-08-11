# Instagram Reels + audio sourcing (verified Aug 2026)

Companion to `instagram-music-limits.md` (what CANNOT be done) and
`instagram-hashtag-diet.md`. This file is the POSITIVE half: how to actually
get audio + ship Reels for the daily auto-poster.

## Architecture decision Aug 2026 (USER's call — do not re-litigate)

- **DO NOT switch** the 11:00 daily image post to Reels. Keep the image post
  exactly as-is (cron `18d280b4af39`).
- **ADD a second daily trigger at 18:00** that posts a Reels video (quote card
  + one of the user's own audio tracks). Plan:
  `/root/.hermes/plans/2026-08-09_1415-evening-reels-post.md`.
- Reels failure does **NOT** fall back to image — the day already has an image
  post; a failed reel just logs/escalates.
- **STATUS: BUILT AND LIVE (verified Aug 2026).** All three scripts exist and
  ran end-to-end; a real reel was published to @ze.nith001 and verified via the
  Graph API (media id `18082374416276979`, permalink
  `https://www.instagram.com/reel/Db0eXyHnHbr/`, `media_type=VIDEO` in the GET
  response — reels surface as VIDEO with a `/reel/` permalink, not `REELS`).
- Scripts (LIVE, in `scripts/`): `audio_library.py` (deterministic daily pick
  via `random.Random(f"reel:{day}")` over the manifest; CLI: `python3
  scripts/audio_library.py [date]` prints the pick), `reel_renderer.py` (reuse
  `post_story.make_story_image` 1080×1920 + ffmpeg zoompan; `dur = audio
  duration`, min 3s guard; CLI: `<card.png> <audio.mp3> <out.mp4>`),
  `reel_post.py` (one reel/day via `logs/reel_state.json`; `REEL_FORCE=1` to
  override for a live smoke test, `REEL_DRY_RUN=1` render-only; exits 0/1/3
  like the image poster; on success writes state + notifies Telegram with the
  MP4 via `sendVideo`).
- **New cron job `7a4c465fbd09` "IG evening reel (18:00)" — `0 18 * * *`**
  (SAST, same TZ as the 11:00 job), workdir `/root/Instagram daily
  auto-post`, delivers to `telegram:-1003938786142`. Self-healing prompt
  mirrors the 11:00 job (run self_heal.py → run reel_post.py → verify via
  INSTAGRAM_GET_IG_USER_MEDIA). The 2-hourly comment sweep fires at 18:00 too
  — different job, comments only, no conflict.

## Audio library location + naming (USER-corrected Aug 2026)

- Dedicated folder at repo ROOT, NOT under `assets/`: **`music/`**
  (`/root/Instagram daily auto-post/music/`) with `manifest.json` inside.
  The `assets/audio/` dir no longer exists — do not create it.
- **Call the files TRACKS, never "clips".** User explicitly corrected this
  (`track-01.mp3` … `track-11.mp3` — currently 11 tracks, 5.2–15.2 s, 64 kbps,
  44.1 kHz, no ID3 tags, md5-unique; all fit the 3–45 s reel window untouched).
- Manifest schema per track:
  ```json
  {"file": "track-01.mp3", "title": "Track 01", "energy": "medium",
   "license": "user-provided", "attribution_needed": false, "source": "user download"}
  ```
- Never leave orphan files: a removed track must also be dropped from the manifest.

## Verified: Pixabay has NO music API (tested with a real key Aug 2026)

- `https://pixabay.com/api/music/?key=<KEY>&q=...` returns an **HTML/Cloudflare
  bot-wall page, not JSON**. There is no `/api/music/` JSON endpoint.
- The public API covers **images and videos only** — `media_type=music` is ignored.
- Don't chase the "Request full API access" modal: it's for hi-res IMAGE URLs
  (`fullHDURL` etc.), its ToS clause 3 forbids automated requests, and it does
  NOT unlock audio.
- The Pixabay key is still fine for image search (100 req/60 s; `per_page` ≥3).

## archive.org + Kevin MacLeod CC-BY — MECHANICS work, but USER REJECTED it

The download recipe below is verified (9.6 MB MP3, HTTP 200, 241 s orchestral).
**However the user rejected the archive.org tracks** (these MP3s would not play
for him) — user-provided downloaded tracks are THE source going forward. Don't
re-source from archive.org/Pixabay unless the user asks.

```bash
# 1. find items (advancedsearch is a public JSON API, no key)
curl "https://archive.org/advancedsearch.php?q=creator%3A%22Kevin+MacLeod%22+AND+mediatype%3Aaudio&fl%5B%5D=identifier&rows=10&output=json"
# 2. list files in an item
curl "https://archive.org/metadata/<identifier>"   # files[].name → *.mp3
# 3. download — PITFALL: /download/ 302-redirects to a ca.archive.org node and
#    can 500. Resolve the redirect and fetch the node directly:
curl -sIL -A "Mozilla/5.0" "https://archive.org/download/<id>/<file>.mp3" \
  | grep -i location   # → dnNNN.ca.archive.org/0/items/...  ← download THAT
```

CC BY 3.0 would require caption attribution (`Audio: <title> — Kevin MacLeod
(incompetech.com)`) — not needed for user-provided tracks (`attribution_needed:
false`).

## Reels posting mechanics

- Same container flow as image: `INSTAGRAM_POST_IG_USER_MEDIA` with
  `media_type: REELS` + `video_file` (local MP4 path) + `caption`, then
  `_PUBLISH` with `max_wait_seconds` ~300 and `poll_interval_seconds` ~10
  (video transcoding is slower than image).
- Cover: optional via `cover_url`, else IG uses first frame; a Ken-Burns render
  over the quote card starts on the card, so no cover needed.
- Render: ffmpeg `zoompan` Ken Burns 1080×1920,
  `-c:v libx264 -crf 20 -c:a aac -movflags +faststart`; `dur = clip duration`
  (all user tracks are 5–15 s), hard floor 3 s.
- Original audio label: the reel shows **"Original Audio"** — safe, it's the
  user's own track, no fingerprinting risk (vs baked copyrighted music).

## User-provided audio ingestion workflow (validated Aug 2026)

1. **Telegram MP3s land in** `/root/.hermes/cache/audio/audio_<hash>.mp3` — probe before copying:
   ```bash
   file "$f" && ffprobe -v error -show_entries format=duration,bit_rate -of default=noprint_wrappers=1 "$f"
   ffprobe -v error -show_entries format_tags=title,artist -of default=noprint_wrappers=1 "$f"   # ID3 tags
   md5sum "$f"   # detect duplicates — two files can share duration but differ by md5
   ```
   Some files carry real ID3 title/artist (use them in the manifest); others have
   none — use a slug placeholder and tell the user it's registered as `Track N`.
2. Copy with a readable slug name into `music/<slug>.mp3`.
3. Register in `music/manifest.json` (schema above), `attribution_needed:
   false` unless the user says otherwise — unknown license.
4. **User curation pattern:** the user sends batches, listens, then says
   "remove all of those, I'll give you the best ones" — on that instruction
   DELETE every track + reset the manifest to `{"tracks": []}` cleanly, then
   ingest the new batch. Do not argue the previous ones were fine.
5. Never leave orphaned files: removed/archived tracks must also be dropped.

## Files / state

- Implementation plan: `/root/.hermes/plans/2026-08-09_1415-evening-reels-post.md`
  (supersedes `..._0948-reels-and-audio-library.md` which called for switching
  the image post to Reels — that switch is NOT happening).
- Scripts (`scripts/` in `/root/Instagram daily auto-post`) — ALL LIVE:
  - `audio_library.py` — deterministic track picker (verified: same date →
    same track, different date → different track).
  - `reel_renderer.py` — card + MP3 → 1080×1920 H.264+AAC reel (verified: all
    11 tracks render clean, `ffprobe` shows h264/1080x1920/aac).
  - `reel_post.py` — full pipeline (generate → pick → render → publish REELS →
    Telegram `sendVideo` notify).
- Cron: image at `0 11 * * *` (18d280b4af39, untouched), reel at
  `0 18 * * *` (7a4c465fbd09, created Aug 2026).
- State files: `logs/reel_state.json` (date + media id + track + duration).

## Tooling pitfalls hit on this workflow

- The gateway blocks terminal commands that look like they restart/stop the
  gateway (false positive on `python3 - <<'EOF'` heredocs that write files) —
  split: `cp` via terminal, JSON via the `write_file` tool, not heredocs.
- `hermes_tools.read_file` in execute_code returns `{'status','message',
  'dedup',...}` WITHOUT content when the file was already read earlier in the
  session — fetch via terminal/`cat`-style or read_file with fresh args instead
  of treating the stub as content (writing it back corrupts the file).
- The repo path has SPACES (`/root/Instagram daily auto-post`) — always quote it.
- `/tmp` on this VPS is ephemeral — keep keeper artifacts under `workspace/`.