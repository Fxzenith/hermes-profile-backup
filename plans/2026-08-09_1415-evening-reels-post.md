# Evening Reels Post (18:00) — Parallel to the 11:00 Image Post — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Keep the existing 11:00 daily IMAGE post untouched, and add a NEW daily trigger at 18:00 that posts a vertical REELS video (quote card + one of the user's 11 downloaded audio clips) via the same Composio connection.

**Architecture:** Two independent daily posts, not a switch. The 11:00 job (`18d280b4af39`) stays exactly as-is. A new cron job at 18:00 runs a new script `reel_post.py` which reuses the existing quote-generation pipeline (`composio_post.generate()` → card PNG), composes a 1080×1920 vertical frame (blurred background + centered card, same visual language as `post_story.make_story_image`), burns one audio clip into it with ffmpeg, and publishes via Composio `INSTAGRAM_POST_IG_USER_MEDIA` with `media_type=REELS` + `video_file`. Reels failure does NOT fall back to image (the day already has an image post; skipping keeps exactly-one-media-per-type semantics).

**Tech Stack:** ffmpeg 6.1.1 (installed, verified), Pillow (installed), Composio CLI `~/.composio/composio` (connection `instagram_magog-daroo` verified ACTIVE), Python 3.12, existing `scripts/composio_post.py` / `scripts/post_story.py` / `scripts/cron_post.py` building blocks, Hermes cron (cronjob tool).

**Current facts (verified this session):**
- 11 audio tracks in `music/track-01.mp3` … `track-11.mp3` — all unique (md5-checked), MP3 64 kbps 44.1 kHz, durations **5.22s – 15.10s** (all meet the 3–45s reel window, no trimming needed), **no ID3 tags**, registered in `music/manifest.json` (11 tracks, `license: user-provided`, `attribution_needed: false`).
- `music/manifest.json` is the single source of truth for the library.
- Cron state: job `18d280b4af39` = 11:00 image post + comment loop + story (SAST, server `+02:00`). Comment sweep `e96e49118730` also fires at 18:00 (independent, no conflict — it's a comment watchdog, not a poster).
- Reel publishing works through the same two Composio actions the image path already uses; REELS is a `media_type` value on `INSTAGRAM_POST_IG_USER_MEDIA` (confirmed enum in previous session).

---

## Task 1: `scripts/audio_library.py` — manifest-backed track picker

**Objective:** Given a date, deterministically pick one valid track from the 11-clip manifest. Safe to run with zero audio.

**Files:** Create `scripts/audio_library.py` (repo root: `/root/Instagram daily auto-post/`)

**Step 1: Write the script**

```python
#!/usr/bin/env python3
"""Audio library manager for the evening Reel. Manifest + deterministic pick."""
import json, random, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "music" / "manifest.json"
AUDIO_DIR = REPO / "music"

def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"tracks": []}

def select_track(day_iso: str) -> dict | None:
    """Deterministic daily pick (stable per day) from available tracks."""
    tracks = [t for t in load_manifest()["tracks"] if (AUDIO_DIR / t["file"]).exists()]
    if not tracks:
        return None
    return random.Random(f"reel:{day_iso}").choice(tracks)

def main() -> int:
    day = sys.argv[1] if len(sys.argv) > 1 else None
    import datetime
    t = select_track(day or datetime.date.today().isoformat())
    print(json.dumps(t) if t else "NO AUDIO AVAILABLE (library empty)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Verify picker**
Run: `python3 scripts/audio_library.py 2026-08-09`
Expected: JSON line with `"file": "clip-XX.mp3"` for some XX. Run twice with same date → identical (deterministic). Run with a different date → possibly different track.

---

## Task 2: `scripts/reel_renderer.py` — card + audio → 1080×1920 MP4

**Objective:** Square card PNG + MP3 → vertical reel MP4 (H.264 + AAC, Ken Burns zoom), deterministic, atomic output.

**Files:** Create `scripts/reel_renderer.py`

**Step 1: Write the renderer** — reuse `post_story.make_story_image` for the 1080×1920 composite, then ffmpeg:

```python
#!/usr/bin/env python3
"""Reel renderer: card PNG + audio MP3 -> 1080x1920 H.264+AAC MP4."""
import subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from post_story import make_story_image  # shared composite (blurred bg + centered card)

def render(card_img: Path, audio_mp3: Path, out_mp4: Path) -> float:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    composite = out_mp4.parent / "reel_frame.jpg"
    make_story_image(card_img, composite)          # 1080x1920 JPEG

    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", str(audio_mp3)], capture_output=True, text=True)
    dur = float(probe.stdout.strip())
    if dur < 3:                                     # IG rejects reels < 3s
        raise RuntimeError(f"audio too short for reel: {dur:.1f}s")

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", str(composite),
           "-i", str(audio_mp3),
           "-vf", ("zoompan=z='min(zoom+0.0009,1.15)':x='iw/2-(iw/zoom/2)':"
                   "y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,format=yuv420p"),
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
           str(out_mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-800:]}")
    return dur

if __name__ == "__main__":
    # quick smoke: reel_renderer.py <card.png> <audio.mp3> <out.mp4>
    render(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
    print("rendered OK")
```

**Step 2: Smoke-test with a real card + clip**
Run:
```bash
cd "/root/Instagram daily auto-post"
python3 -c "import scripts.reel_renderer as rr; print('import ok')"
IMG=$(ls -t workspace/*/post-*/post.png | head -1)
python3 scripts/reel_renderer.py "$IMG" music/track-01.mp3 /tmp/test_reel.mp4 && \
ffprobe -v error -show_entries stream=codec_name,width,height -of default=noprint_wrappers=1 /tmp/test_reel.mp4
```
Expected: `codec_name=h264 … 1080x1920`, audio stream `aac`, duration ≈ clip duration.
Note: `/tmp` is ephemeral on this box — only for the throwaway smoke test; the pipeline writes under `workspace/` for keepers.

---

## Task 3: `scripts/reel_post.py` — the 18:00 entry point

**Objective:** generate quote card → pick track → render → publish REELS via Composio → notify Telegram; idempotent per day, one reel only.

**Files:** Create `scripts/reel_post.py`

**Step 1: Write the script** (modeled on `composio_post.py`'s structure — copy its `load_env/log/run/parse_execute_json`, reuse `generate()` from `composio_post.py` for the card + caption):

```python
#!/usr/bin/env python3
"""18:00 evening Reels poster. ONE reel per day, state-tracked."""
import json, os, subprocess, sys, time
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import audio_library, reel_renderer
from composio_post import load_env, log, run, parse_execute_json, generate, IG_USER_ID, ACCOUNT

STATE_FILE = REPO / "logs" / "reel_state.json"
COMPOSIO_BIN = str(Path.home() / ".composio" / "composio")
MAX_WAIT = 300; POLL = 10  # video transcoding is slow

def load_state():
    if STATE_FILE.exists():
        try: return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, ValueError): pass
    return {}
def save_state(s): STATE_FILE.write_text(json.dumps(s, indent=2))

def create_reel_container(video_path, caption, attempts=3):
    data = {"ig_user_id": IG_USER_ID, "caption": caption,
            "media_type": "REELS", "video_file": str(video_path)}
    last_err = None
    for i in range(1, attempts+1):
        res = run([COMPOSIO_BIN, "execute", "INSTAGRAM_POST_IG_USER_MEDIA",
                   "--account", ACCOUNT, "-d", json.dumps(data)])
        parsed = parse_execute_json(res["out"]) if res["code"]==0 else None
        if parsed and parsed.get("successful"):
            cid = str(parsed["data"]["id"]); log(f"Reel container created: {cid}")
            return cid
        last_err = f"create failed: {parsed or res['out'][-300:]}"
        if i < attempts: time.sleep(10*i)
    raise RuntimeError(f"reel container creation failed: {last_err}")

def publish_reel(cid, attempts=3):
    data = {"ig_user_id": IG_USER_ID, "creation_id": cid,
            "max_wait_seconds": MAX_WAIT, "poll_interval_seconds": POLL}
    for i in range(1, attempts+1):
        res = run([COMPOSIO_BIN, "execute", "INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH",
                   "--account", ACCOUNT, "-d", json.dumps(data)])
        parsed = parse_json_output(res["out"]) if res["code"]==0 else None
        if parsed and parsed.get("successful"):
            return str(parsed.get("data", {}).get("id", ""))
        if i < attempts: time.sleep(15*i)
    raise RuntimeError("reel publish failed after retries")
```

(also add `main()`: guard `state.get("last_reel_date") == today` → exit 0; `image, caption = generate()`; `track = audio_library.select_track(today)`; if no track → log WARN, return 3 (no library yet, don't post); folder = REPO/workspace/.../reel/; `reel_renderer.render(image, track file, reel.mp4)`; caption += hash tags (already in `generate()`); publish; write `last_reel_date` + track/file + media id; exit 0. On any permanent error: log ERROR, exit 1 — **no image fallback**.)

**Step 2: dry-run smoke (no publish)**
```bash
cd "/root/Instagram daily auto-post" && REEL_DRY_RUN=1 python3 scripts/reel_post.py
```
Expected: renders `workspace/<date>/post-NN/reel/reel.mp4`, logs track chosen, does NOT hit Composio. Verify with ffprobe: `h264 + aac + dur≈clip`.

**Step 3: live smoke (ONE real reel)**
Run once with `REEL_FORCE=1`: `cd "/root/Instagram daily auto-post" && REEL_FORCE=1 python3 scripts/reel_post.py` — expected: reel appears on @ze.nith001 (Reels tile, audio present, correct caption). Verify via `composio execute INSTAGRAM_GET_IG_USER_MEDIA`. This is the go/no-go gate before creating the cron.

---

## Task 4 — Create the 18:00 cron trigger

**Objective:** a new Hermes cron job fires `reel_post.py` daily at 18:00.

**Files:** none on disk — use the `cronjob` tool (action=create) at execution time:

- **name:** `IG evening reel (18:00)`
- **schedule:** `0 18 * * *`  (server TZ is `+02:00` = SAST; same clock as the 11:00 job)
- **workdir**: `/root/Instagram daily auto-post`
- **script**: none — LLM job whose prompt runs the pipeline (keeps the self-healing pattern of the 11:00 job)
- **prompt** (concise, self-healing):
  > You are the evening Reel driver for @ze.nith001 (IG user 28532466729677348, Composio connection instagram_magog-daroo). Work from /root/Instagram daily auto-post.
  > STEP 1: pre-flight `python3 scripts/self_heal.py` — exit 0 → proceed; exit 2/3 → report to user, do not post.
  > STEP 2: run `python3 scripts/reel_post.py` (it self-guards one-reel-per-day via logs/reel_state.json).
  > STEP 3: on nonzero exit, read logs/cron.log, fix the cause, retry once (missing fonts → scripts/install-fonts.sh; PIL missing → pip install --break-system-packages -r requirements.txt).
  > STEP 4: verify with `~/.composio/composio execute INSTAGRAM_GET_IG_USER_MEDIA --account instagram_magog-daroo -d '{"ig_user_id":"28532466729677348"}'` — a new REELS media with today's timestamp must appear. Report: media id, track used, duration.
  > Escalate to the user ONLY on permanent auth failure.
- **skills**: `[]`
- **deliver**: `telegram:-1003938786142` (same conference room as the 11:00 job — consistent notifications)

(Note: the 2-hourly comment sweep `e69e0149…` runs at 18:00 too — it touches comments only, so no collision with the reel publish.)

---

## Task 5: Regression checks + acceptance

**Objective:** both daily posts coexist; nothing about the 11:00 job changes.

**Files:** none modified beyond Tasks 1–4 (the 11:00 job's prompt, scripts and schedule stay byte-identical).

**Checks:**
1. `python3 scripts/audio_library.py` — returns a clip for today.
2. Reelonch the runner 3 consecutive days' worth (dry-run with dates) — each picks a valid clip deterministically (may repeat — fine).
3. `ffprobe` the rendered `reel.mp4`: h264 / aac / 1080x1920 / duration within 3–15s.
4. Confirm `logs/reel_state.json` has `last_reel_date` after the live smoke test and that a second forced run is a no-op (idempotent).
5. Confirm the 11:00 job object in `cron` still shows `schedule: 0 11 * * *` and `enabled: true` — untouched.

**Acceptance criteria:**
1. Daily: image post 11:00 (unchanged) + reel 18:00 (new), both publishing successfully.
2. Reel = vertical 1080×1920 H.264+AAC, audio from `music/` rotation, caption = quote hook + hashtags.
3. One reel per day max (state guard), no double posts.
4. No fallback to image on reel failure (day already has image) — a failed reel just logs and escalates if permanent.
5. `logs/cron.log` auditable for both jobs' runs.

---

## Risks / tradeoffs / open questions

- **Audio licensing:** the 11 clips are `user-provided` (no source documented). If they're trending/studio tracks, IG's own audio-sync may mute the reel on detection. The one live smoke test (Task 3 Step 3) will surface this immediately — if muted, we swap in royalty-free CC-BY tracks (archive.org Kevin MacLeod, attribution line auto-added) or ask user for the file origins.
- **Bitrate:** clips are 64 kbps — audible but acceptable for quote reels; no re-encode of source, ffmpeg just transcribes to AAC 128k.
- **Short clips (5–15s):** all above the 3s IG minimum. No padding needed.
- **18:00 coincides with the comment sweep** — distinct jobs, no shared state, safe.
- **Open question:** keep 18:00 or shift to 19:00–20:00 (evening prime-time for reels)? Easy cron change either way — default is 18:00 per user's request.

## Execution handoff

Plan complete and saved. Ready to execute using subagent-driven-development — a fresh subagent per task with two-stage review (spec compliance then code quality). Shall I proceed?