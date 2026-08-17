# Worked examples — two repo-as-skill installs (2026-08-09)

Both repos were added in one session via the workflow in SKILL.md.

## 1. markitdown — plain tool repo (Path B)

- **Repo:** microsoft/markitdown — "convert files to Markdown for LLM pipelines"
- **Clone:** `/root/markitdown`
- **Install:** `python3 -m venv /root/.venvs/markitdown && /root/.venvs/markitdown/bin/pip install --no-cache-dir 'markitdown[all]'` (first attempt got SIGTERM'd mid-install at 91% disk — retried with `--no-cache-dir`, succeeded; installed v0.1.7)
- **Skill:** `skill_manage(action='create')` — the first three attempts were rejected for description > 60 chars (142, 103, 86), the third rejection tripped `same_tool_failure_halt`. Final: `Use when converting files to Markdown for LLM ingestion.` (56 chars) → accepted.
- **Verify:** generated fixtures with python-pptx + openpyxl; CLI converted HTML → headings/table, XLSX → markdown table, PPTX → slide markers. All rc=0.
- **Quirk captured:** every run prints an onnxruntime warning (`Failed to detect devices under "/sys/class/drm/card0"`) on GPU-less VPSes — harmless; noted in the skill's Pitfalls.
- **CLI path:** `/root/.venvs/markitdown/bin/markitdown` (not on PATH).

## 2. browser-use/video-use — skill-first repo (Path A)

- **Repo:** browser-use/video-use — "Edit videos with coding agents" (20k★). Ships its own SKILL.md (322 lines: 12 hard ffmpeg rules, cut craft, EDL format) + `helpers/` (transcribe.py, pack_transcripts.py, timeline_view.py, render.py, grade.py, transcribe_batch.py). README's setup prompt says to register the skill with whatever agent you run under.
- **Clone:** `/root/video-use` → `ln -sfn /root/video-use /root/.hermes/skills/video-use`
- **Install:** repo-local venv: `cd /root/video-use && uv venv --python 3.12 .venv && uv pip install -e .` (36 packages: requests, librosa, matplotlib, pillow, numpy, scipy, numba, llvmlite…). ffmpeg 6.1.1 / ffprobe / yt-dlp already present.
- **.env:** `cp -n .env.example .env` — `ELEVENLABS_API_KEY=` left empty; Scribe transcription needs it, user pastes when first editing footage.
- **Verify (real commands, real file):** generated 6s testsrc+sinetone clip via ffmpeg; `grade.py --preset warm_cinematic` → graded.mp4 ✓; `timeline_view.py` initially failed.
- **Upstream bug found & fixed locally:** `timeline_view.py::extract_frames` samples the last frame at exactly `end`; `ffmpeg -ss <EOF>` emits 0 frames with exit 0 → PIL FileNotFoundError on the missing frame. Patched: clamp every seek to `max(start, end - 0.05)`. Verified with a tempfile-based ad-hoc script (9/9 PASS: mocked-seek unit asserts + real-clip integration). **Re-apply after any `git pull`** (saved in memory).
- **Note:** upstream-ownedship — video-use's SKILL.md is the repo's, not curator-managed; local code fixes are the only permitted surface.
