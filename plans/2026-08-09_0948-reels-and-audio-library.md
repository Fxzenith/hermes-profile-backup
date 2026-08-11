# Reels Switch + Motivational Audio Library Implementation Plan

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task (two-stage review per task).

**Goal:** Convert the daily Instagram pipeline from image posts to short vertical Reels (video quote card + motivational audio), seeded from a locally-curated, legally-licensed audio library.

**Architecture:** Keep the existing quote-template → card-PNG generation. Replace the IMAGE container publish with a REELS container publish: render the card + audio into a 1080×1920 MP4 (ffmpeg), upload via Composio `video_file`, publish with a longer readiness poll (video transcoding), fall back to the current IMAGE path on permanent Reels failure so no day is ever lost.

**Tech Stack:** ffmpeg 6.1.1 (installed), Pillow (installed), Composio `INSTAGRAM_POST_IG_USER_MEDIA`/`_PUBLISH` (REELS in `media_type` enum confirmed), Python 3.12, existing `scripts/composio_post.py`.

---
**HARD CONSTRAINT (read first):** The audio in the reference screenshot is licensed trending music. Instagram/TikTok expose **zero** legal API to download it, and even Meta's own Reels API cannot attach licensed tracks (same limitation as stories). This plan sources *equivalent-style* audio legally: Pixabay Content License tracks (free, no attribution) and Kevin MacLeod CC-BY tracks (attribution required). No scraping, no ripping.

---

## Task 1: Audio library core (`scripts/audio_library.py`)

**Objective:** Manifest-driven audio library with validation; safe to run with zero audio present.

**Files:**
- Create: `scripts/audio_library.py`
- Create: `assets/audio/manifest.json` (empty `{"tracks": []}`)
- Create: `assets/audio/` dir

**Step 1: Write `audio_library.py`**

```python
#!/usr/bin/env python3
"""Audio library manager for the daily Reel. Manifest + validation + fetch."""
import json, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "assets" / "audio" / "manifest.json"
AUDIO_DIR = REPO / "assets" / "audio"
TRACK_FIELDS = {"file", "title", "energy", "license", "attribution_needed", "source"}

def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"tracks": []}

def select_track(day_iso: str = None) -> dict | None:
    """Deterministic daily pick (stable per day) from available tracks."""
    import random
    tracks = [t for t in load_manifest()["tracks"] if (AUDIO_DIR / t["file"]).exists()]
    if not tracks:
        return None
    rng = random.Random(day_iso)
    return rng.choice(tracks)

def validate() -> list[str]:
    """Check manifest entries: required fields, file exists, ffprobe-duratable. Return problems."""
    problems = []
    for t in load_manifest()["tracks"]:
        missing = LIST_FIELDS - set(t)
        if missing:
            problems.append(f"{t.get('file')}: missing {sorted(missing)}")
            continue
        f = AUDIO_DIR / t["file"]
        if not f.exists():
            problems.append(f"{t['file']}: file missing")
            continue
        r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                            "-of","csv=p=0",str(f)], capture_output=True, text=True)
        try:
            if float(r.stdout.strip()) < 5 or float(r.stdout.strip()) > 45:
                problems.append(f"{t['file']}: duration {r.stdout.strip()}s outside 5-45s")
        except ValueError:
            problems.append(f"{t['file']}: unreadable audio")
    return problems

def add_track(file: str, title: str, energy: str, license: str, attribution_needed: bool, source: str):
    m = load_manifest()
    m["tracks"] = [t for t in m["tracks"] if t["file"] != file]
    m["tracks"].append({"file": file, "title": title, "energy": energy,
                        "license": license, "attribution_needed": attribution_needed, "source": source})
    MANIFEST.write_text(json.dumps(m, indent=2))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "validate"
    if mode == "validate":
        problems = validate()
        print("OK — all tracks playable" if not problems else "PROBLEMS:\n" + "\n".join(problems))
        print("library size:", len(load_manifest()["tracks"]))
    elif mode == "pick":
        t = select_track()
        print(json.dumps(t) if t else "NO AUDIO AVAILABLE")
```

**Step 2: Pick track** — run `python3 scripts/audio_library.py pick`; expected: `none` (empty manifest).

**Step 3: Validate** — run `python3 scripts/audio_library.py validate`; expected: "VALIDATION…". Track-agnostic, no failure.

---

## Task 2: Seed the library — archive.org Kevin MacLeod CC-BY (VERIFIED WORKING)

**Objective:** Populate 5-10 motivational/cinematic tracks from Kevin MacLeod's CC-BY catalog on archive.org, with attribution metadata.

**Status note (verified with the live Pixabay key):** Pixabay's public API covers **images and videos only** — the `/api/music/` path returns an HTML/Cloudflare wall, not JSON. There is no music API. Do NOT spend time on it. (The `PIXABAY_API_KEY` in `.env` is still useful if we ever add image-search features, but audio comes from archive.org.)

**Why archive.org:** bulk-download friendly, direct MP3s, Kevin MacLeod is CC-BY 3.0 (attribution required), scriptable via the classic-API JSON + `dnNNN.ca.archive.org` node mirrors (the main `/download/` path 302s and can 500 — follow Location headers or resolve the node directly).

**Files:**
- Modify: `assets/audio/` (downloaded MP3s), `assets/audio/manifest.json`

**Step 1: Add `fetch_archive_org()` to `audio_library.py`** — search `archive.org/advancedsearch.php` q=`creator:"Kevin MacLeod" mediatype:audio AND (title:epic OR title:rising OR title:achievement OR title:crusade OR title:impact OR title:inspire ...)`, `fl[]=identifier`, `rows=20`; resolve node via `metadata` API; download direct.

**Step 2: Fetch a curated shortlist** (epic/orchestral/motivational vibe):
- `rising-tide-faster-by-kevin-macleod` (verified working, 241s orchestral — RenderStep clips to ≤34s)
- `Kevin-MacLeod_Impact_2014_FullAlbum` (select a track within)
- `kevin-macleod-msm` (Monkeys Spinning Monkeys — upbeat, optional)
- A few more from archive.org search, tune q for "epic", "achievement", "inspire"

**Step 3:** `add_track(... license="CC-BY 3.0", attribution_needed=True, source="incompetech.com (via archive.org)")` for each.

**Step 4: Verify:** `python3 scripts/audio_library.py validate` → 0 problems; durations 8-45s after any trimming (or let the renderer clip).

> The Reel caption MUST carry attribution when `attribution_needed`: `Audio: <title> — Kevin MacLeod (incompetech.com)` (Task 4 handles this automatically).

---

## Task 3: Reel renderer (`scripts/reel_renderer.py`)

**Objective:** card PNG + audio MP3 → 1080×1920 reels MP4 with subtle Ken Burns zoom; deterministic, fast, atomic output.

**Files:**
- Create: `scripts/reel_renderer.py`

**Step 1: Write renderer** — reuse `post_story.py#make_story_image` composition (blurred bg + centered card) as the base 1080×1920 composite, then:

```bash
ffmpeg -y -loglevel error \
  -loop 1 -framerate 30 -t <dur> -i story_composite.jpg \
  -i track.mp3 \
  -vf "zoompan=z='min(zoom+0.0009,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,format=yuv420p" \
  -c:v libx264 -preset medium -crf 20 \
  -c:a aac -b:a 128k -shortest -movflags +faststart reel_batch.mp4
```

- `dur = min(track_duration, 34)` (reels up to 90s, keep snappy; hooks are short). Hard floor: if track <8s, loop image only to 13s with no audio fade-out = fine.
- Output to `workspace/<date>/post-NN/reel.mp4`.
- Return (path, duration) or raise with ffmpeg stderr.

**Step 2: Test with a real track** — `python3 -c "from reel_renderer import render; print(render(<last_post_img>, <any_manifest_track>))"`.
**Step 3: ffprobe the output**: hit `h264 1080x1920` + `aac` + dur ≈ audio. Verify plays (local).

**Step 4: Verify "no track" fallback** — render with `track=None` → silent 13s MP4 (still a valid reel). This keeps the pipeline alive pre-library.

---

## Task 4: Wire Reel into `composio_post.py` (image → reel switch + fallback)

**Objective:** daily a reel; if Reels fails permanently, post the old image (never lose a day).

**Files:**
- Modify: `scripts/composio_post.py`

**Step 1:** In `generate()` (returns today's card PNG + caption) — unchanged. Add caption attribution suffix when the picked track has `attribution_needed == True`: append `Audio: <title> — <source>` as a second caption line. Keep hashtag diet caption = quote hook + NEWLINE + attribution + NEWLINE + hashtags.

**Step 2:** Track selection in main: `track = audio_library.select_track(today)` → `render_reel()` if track else `render_reel(track=None)`.

**Step 3: New pair of publish functions** (keep old image ones intact):

```python
def create_reel_container(video_path: Path, caption: str, attempts: int = 3, poll_long=True):
    data = {"ig_user_id": IG_USER_ID, "caption": caption,
            "media_type": "REELS", "video_file": str(video_path)}
    # same retry wrapper as create_container — but 3 retries, longer backoff (video upload is slow)
    # on permanent error (auth/permission) raise; on transient (9007/rate) retry.

def publish_reel(container_id: str, attempts: int = 3) -> bool:
    # poll with MAX_WAIT_SECONDS = 300, POLL_INTERVAL = 10 (video transcoding is slow)
    # reuse existing retry/publish logic, just longer wait + retryable classification unchanged
```

**Step 4:** In main: `try: cid = create_reel_video(reel_path, caption); publish_reel(cid)` → success path → notify + mark `logs/reel_state.json` (date + media id + track title). `except` → log, then **fallback**: `create_container(image, caption)` + `publish_container` (image mode, old code) so posting still succeeds. Final state records which mode ran.

**Step 5: Dry/verify run** (does NOT post): `python3 -c "import composio_post; print(composio_post.reel_smoke_test())"` — render only + report caption/track. Expected: clean render, correct caption with attribution/hashtags, no publish.

**Step 6: Live smoke test (ONE reel):** set env `REEL_FORCE=1` and run once manually to publish a real reel; verify on profile (Reel tile, audio plays, caption correct). Then `git` commit. This is the go/no-go gate before enabling cron.

---

## Task 5: Enable in cron + cleanup

**Objective:** cron 18d280b4af39 posts reel daily; auto-fallback documented.

**Files:**
- Modify: `/root/.hermes/cron/jobs.json` prompt STEP 2 text: "posts REELS video (audio library) with automatic fallback to IMAGE on permanent Reels failure; keeps posting exactly ONE media per run."
- Modify: `scripts/comment_loop.py` — no change (Reels comments same API).
- Modify: `scripts/post_story.py` — unchanged (separate story; still the square card as story).

**Regression checks:**
- `python3 scripts/audio_library.py validate` → 0 problems
- dry-run render for each topic template (4) → ffprobe OK
- cron prompt: verify one-post-per-run guard intact (STEP 3 verify timestamp)
- Run the whole pipeline in `--dry-run` mode for scheduling a feed.

**Acceptance criteria:**
1. Daily 11:00 cron publishes a REELS video (verified `media_type = REELS` via `INSTAGRAM_GET_IG_USER_MEDIA`), duration 10–30s, audio present, caption with hashtag diet + attribution (where applicable).
2. Fallback proven: with `REELS` forced-fail (simulate by removing `video_file`), pipeline publishes IMAGE and records it.
3. `assets/audio/` has ≥5 validated tracks from Pixabay (or CC-BY fallback, attributed).
4. `logs/reel_state.json` tracks last media_id/track/date; no double-posting.

**Risks / tradeoffs:**
- **API audio limit:** track is "Original Audio" attribution due the same API limitation as stores — legally clean, no triggers.
- **Transcoding wait:** video publish can take 30–120s+ on IG; long-poll timeouts raised; fallback saves the post if IG rejects the mp4 (e.g. codec probe).
- **Ken Burns only:** v1 motion is subtle zoom; larger edits (lower-third caption crawl, punch-ins on hooks) = future iteration, deliberately YAGNI now.
- **Pixabay key is user-actionable** — if they refuse, the CC-BY fallback works; attribution line makes it compliant.

**Open question for user (optional):**
1. Duration preference: keep ~13s (hook-friendly, trendy) or lengthen to 30s?
2. Do you want the quote card *animated* (`zoompan` only) or a static card with audio timeline offset?
3. Reel→feed share toggle: 'share to feed' (bigger reach but noise) vs Reels tab only?

---

## Execution Handoff

After approval, implement Task-by-Task via `subagent-driven-development`: fresh `delegate_task` per task, with full pipeline context, spec-compliance review then code-quality review before moving on. Task 2 requires the user's Pixabay key paste (can't be automated) — queue it for the manual step.