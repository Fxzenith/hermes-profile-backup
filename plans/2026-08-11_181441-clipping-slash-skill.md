# `/clipping` Slash Skill Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Create a reusable Hermes skill named `clipping` so the user can run `/clipping <youtube_url> <clip_count>` in chat and get that many finished Shorts clips (9:16, face-tracked, subtitled, end-carded) delivered to Telegram via the existing YT Clipper pipeline at `/root/autoclipping`.

**Architecture:** A SKILL.md at `~/.hermes/skills/media/clipping/SKILL.md` (name: `clipping`) whose trigger description makes the skill auto-load when the user types `/clipping <url> <n>`. The skill instructs the agent to run the pipeline **stage commands directly** (never `main.js`, which has an interactive ENTER gate) and to do clip selection itself (the agent IS the LLM — it reads `data/transcript.json` and writes `data/clips.json` with exactly N clips). Two bugs found during the 2026-08-11 dry run must be fixed first so the skill's output is correct: (1) export.js's Rule-#12 resume check skips the burn for the default `shorts` platform because its output path equals the reframed input path, shipping a raw no-subtitle file; (2) verify_clip_sync.py mis-parses the emitter's ASS Dialogue lines (it read the header `0,0,153,,` as text) producing a false Rule-2 FAIL.

**Tech Stack:** Hermes skill system (SKILL.md + frontmatter), Node.js stage scripts (`scripts/extract.js`, `scripts/render.js`, `scripts/export.js`), Python (`uv run python`), ffmpeg, Telegram MEDIA: native delivery.

---

## Current Context (verified 2026-08-11)

| Fact | Value |
|---|---|
| Pipeline root | `/root/autoclipping` (Node orchestrator `main.js` + uv-managed Python) |
| Trigger example | `/clipping https://youtu.be/YGAjgLtJJFI?si=41CLUuEhloEDddUw 2` |
| `main.js` | Interactive `Press ENTER` gate at "clip selection" — **do not use** in the skill |
| Working stage commands | `uv run python python/transcript.py --url "<URL>"` → `node scripts/extract.js "<URL>"` → `node scripts/render.js` → `node scripts/export.js` |
| Clip selection | `clip_selector.py` needs an OpenAI/Anthropic key; **none configured** → the agent reads the transcript and writes `data/clips.json` itself (schema: start/end/title/hook/reason, 10–600s, no overlap) |
| Default platform | `DEFAULT_PLATFORM = 'shorts'` in `scripts/export.js:39` |
| BUG A (export.js) | `scripts/export.js` ~line 155: `if (fs.existsSync(outPath)) { ... if (outM >= inM) { variants.push(outPath); return; } }` — for the default platform `outPath` IS the reframed file, so `outM >= inM` is always true → burn skipped → no-suffix `NN_slug.mp4` ships as raw reframe. Observed: `01_..._certificates.mp4` last frame = 617KB speaker frame vs `_tiktok` = 15KB endcard. |
| BUG B (verifier) | `/root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py:77-79` — `l.split(",", 5)[:2]` + `l.split(",,", 1)[1]` grabs the ASS header, not the cue text → false Rule-2 FAIL (last cue printed as `0,0,153,,It's`). Direct parse with `parts = l.split(',', 9); text = parts[9]` (strip `{\fad(...)}`) works and shows the cue text matches the transcript exactly. |
| Outputs to deliver | `Outputs/NN_slug.mp4` must be the burned shorts variant (after BUG A fix) — deliver via `MEDIA:/abs/path` in the final response |
| Env | Telegram delivery is native MEDIA: (no bot API call needed when Hermes itself sends); Bot API reference exists in the shorts-clipping-pipeline skill if needed |

## Task 1: Fix export.js default-platform resume bug (BUG A)

**Objective:** Make the default (`shorts`, no-suffix) export always burn subtitles + end-card instead of being skipped by the Rule-#12 resume check that compares the output against itself.

**Files:**
- Modify: `/root/autoclipping/scripts/export.js` (the `if (fs.existsSync(outPath))` block inside `main()`, ~line 155)

**Step 1: Read the exact block**

```bash
sed -n '148,175p' /root/autoclipping/scripts/export.js
```

**Step 2: Apply the fix — skip resume only for non-default variants**

The resume check must compare against a DIFFERENT file (the reframed input) — but for the default platform `outPath === reframed`, so the check is tautological. Skip the resume shortcut entirely when `isDefault` is true (always re-burn the default variant; burns are idempotent and cheap):

```js
// Rule #12 resume: skip only for NON-default variants. For the default
// platform outPath === the reframed input, so mtime comparison is
// tautological (outM >= inM always true) — that silently shipped an
// UNSUBTLED reframe as the shorts final. Default always re-burns.
if (!isDefault && fs.existsSync(outPath)) {
  const inM = fs.statSync(reframed).mtimeMs, outM = fs.statSync(outPath).mtimeMs;
  if (outM >= inM) { variants.push(outPath); return; }
}
```

**Step 3: Verify**

```bash
# needs a fresh-ish state: data/clips.json + data/transcript.json + assets/clip_*.mp4 existing
rm -f Outputs/*.mp4
node scripts/render.js && node scripts/export.js
# last frame of the NO-SUFFIX file must be a solid endcard (~15KB), not a speaker frame
n=$(ffprobe -v error -count_frames -select_streams v:0 -show_entries stream=nb_read_frames -of csv=p=0 "Outputs/01_*.mp4" | tr -d '\r')
ffmpeg -v error -y -i "Outputs/01_*.mp4" -update 1 -frames:v 1 -vf "select=eq(n\,$((n-2)))" /tmp/chk.png && stat -c%s /tmp/chk.png
```

Expected: sub-40KB (solid black end-card frame). Before the fix it was ~600KB (speaker frame).

**Step 4: Commit**

```bash
cd /root/autoclipping && git add scripts/export.js && git commit -m "fix(export): always burn default (shorts) variant — resume check was tautological"
```

## Task 2: Fix verify_clip_sync.py ASS parser (BUG B)

**Objective:** Correct the cue parsing so the skill's built-in sync verification passes on real output.

**Files:**
- Modify: `/root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py:76-80`

**Step 1: Apply the fix — parse by 9th comma, strip inline tags**

Replace the broken head/text splitting with a standard ASS field split:

```python
        # ASS Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        parts = l.split(',', 9)
        if len(parts) < 10:
            continue
        start_s = to_sec(parts[1])
        end_s = to_sec(parts[2])
        txt = re.sub(r"\{\\fad\([^)]*\)\}", "", parts[9]).strip()
        rows.append((start_s, end_s, txt))
```

**Step 2: Verify**

```bash
cd /root/autoclipping
uv run python /root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py --clip 1
uv run python /root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py --clip 2
```

Expected: ALL CHECKS PASSED for both (last-cue check must now show real text like `It's` / `low carb,` matching the transcript window).

**Step 3: Commit**

```bash
cd /root/.hermes/skills && git add media/shorts-clipping-pipeline/scripts/verify_clip_sync.py && git commit -m "fix(verify): parse ASS Dialogue by 9th comma, not ',, ' split"
```

## Task 3: Create the `clipping` skill

**Objective:** Create `~/.hermes/skills/media/clipping/SKILL.md` with name `clipping`, description trigger "Use when the user runs /clipping..." so typing `/clipping <url> <n>` auto-loads it, and full runbook inside.

**Files:**
- Create: `/root/.hermes/skills/media/clipping/SKILL.md`

**Step 1: Write the SKILL.md** (frontmatter name MUST be `clipping` so the slash command resolves; description's first ~57 chars must contain the trigger "Use when the user runs /clipping"). Minimal viable content below — see "Full Skill Body" section at the bottom of this plan for the copy-pasteable complete text.

**Step 2: Verify the skill loads**

```bash
hermes skills list 2>&1 | grep -i clipping
# or skill_view(name='clipping') from a fresh session
```

Expected: `clipping` present with the trigger description.

**Step 3: Commit**

```bash
cd /root/.hermes/skills && git add media/clipping/SKILL.md && git commit -m "feat(skills): add /clipping slash skill"
```

## Task 4: Fresh-session end-to-end verification

**Objective:** Prove `/clipping <url> <n>` works from zero context, exactly as the user will run it.

**Step 1: Run in a genuine fresh session**

```bash
cd /root && hermes chat -q "/clipping https://youtu.be/YGAjgLtJJFI 2" 2>&1 | tail -40
```

Expected: skill auto-loads, transcript fetched, 2 clips selected by the agent, `assets/clip_01.mp4` + `clip_02.mp4` extracted, `Outputs/01_*.mp4` + `02_*.mp4` rendered 720x1280, both burned (last-frame endcard ~15KB), and the final message contains `MEDIA:/root/autoclipping/Outputs/...` lines for both clips.

**Step 2: Verify artifacts manually**

```bash
ls -la /root/autoclipping/Outputs/*.mp4
for f in /root/autoclipping/Outputs/0*.mp4; do ...endcard-frame probe as in Task 1...; done
```

Expected: 2 (or N) no-suffix `.mp4` files, each ending in a solid endcard frame.

**Step 3: Cross-check the board**

```bash
hermes kanban list
```

Expected: clipping:1–4 all `done` with summaries.

## Full Skill Body (for Task 3)

````markdown
---
name: clipping
description: Use when the user runs /clipping with a YouTube URL and a clip count — clip that video into vertical Shorts with subtitles and send them to Telegram.
platforms: [linux]
---

# /clipping — YouTube → N Shorts via the YT Clipper pipeline

Triggers: `clipping`, `/clipping`. Usage: `/clipping <youtube_url> <clip_count>`
(e.g. `/clipping https://youtu.be/YGAjgLtJJFI 2`). Produce exactly N finished
shorts-clips and deliver them as MEDIA: paths in the final reply.

Pipeline root: `/root/autoclipping`. Run all commands from there.
NEVER use `main.js` (interactive ENTER gate). Run the stage commands directly.

## Steps

1. **Transcript** — `cd /root/autoclipping && uv run python python/transcript.py --url "<URL>"`
   → writes `data/transcript.json`.
2. **Select exactly N clips (YOU are the selector)** — read `data/transcript.json`
   (merge overlapping segments mentally), pick N high-retention windows:
   - 10–600s each (prefer 25–55s), no overlap (1–2s gap), sorted ascending.
   - Payoff ending (reveal/conclusion/number/cliffhanger — NEVER a dangling tail).
   - Concrete story beats (names, numbers, "but", quotes) over abstract advice.
   - Write `data/clips.json` `{"clips":[{start,end,title,hook,reason}]}` and
     `data/clips_review.md` (both required by extraction).
3. **Extract** — `node scripts/extract.js "<URL>"` → `assets/clip_NN.mp4`
   (resumable, retries once).
4. **Render 9:16 face-tracked** — `node scripts/render.js` → `Outputs/NN_slug.mp4`.
5. **Burn + end-card** — `node scripts/export.js` → `Outputs/NN_slug.mp4`
   (shorts default; add `--platforms shorts,tiktok,reels` for all variants).
6. **Verify** — for each `Outputs/NN_slug.mp4`: probe frame count, then grab
   frame N-2: it must be a small (~15KB) solid endcard, NOT a ~600KB speaker
   frame (concat verification, rule #6). Optionally
   `uv run python /root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py --clip 1`.
7. **Deliver** — end the reply with a `MEDIA:/root/autoclipping/Outputs/NN_slug.mp4`
   line per clip (native Telegram video delivery). Caption each with title + hook.

## Pitfalls (all learned on this box)

- `main.js` has a `Press ENTER` gate → always run `transcript.py` /
  `extract.js` / `render.js` / `export.js` directly.
- export.js default (`shorts`) output path == reframed input → resume check was
  tautological and shipped an UNSUBTLED reframe. Fixed 2026-08-11: default
  always re-burns. If you ever see a no-suffix mp4 whose last frame is a
  speaker (~600KB), the burn was skipped — re-run `node scripts/export.js`.
- `/tmp` is ephemeral on this VPS — stage verification frames under the
  project dir, not `/tmp`.
- Python is PEP-668: always `uv run python`, never bare pip.
- Stale `NN_*.mp4` from an earlier, longer run linger in Outputs — start only
  from `data/clips.json`, clean stale files before re-running.
- MEDIA: delivery is the native path; the Bot-API fallback (reference in the
  shorts-clipping-pipeline skill) is only needed for channel posting.
````

## Files Likely to Change

- Modify: `/root/autoclipping/scripts/export.js` (Task 1)
- Modify: `/root/.hermes/skills/media/shorts-clipping-pipeline/scripts/verify_clip_sync.py` (Task 2)
- Create: `/root/.hermes/skills/media/clipping/SKILL.md` (Task 3)
- Generated (not committed): `data/transcript.json`, `data/clips.json`, `assets/clip_*.mp4`, `Outputs/*.mp4`

## Tests / Validation

1. Task 1: endcard-frame probe on no-suffix output → <40KB PNG (was ~600KB).
2. Task 2: `verify_clip_sync.py --clip 1/2` → ALL CHECKS PASSED.
3. Task 3: `skill_view(name='clipping')` loads the runbook.
4. Task 4: fresh `hermes chat -q "/clipping <url> 2"` produces exactly 2 burned
   clips + MEDIA: lines; `hermes kanban list` shows clipping:1–4 done.

## Risks & Tradeoffs

- **Clip quality is agent-judgment** (no clip_selector LLM configured). Mitigation:
  the skill's selection criteria mirror clip_selector's scoring (payoff,
  concreteness, hooks). If the user ever configures `OPENAI_API_KEY`, switch
  Task 2 to `clip_selector.py --out data/clips.json` for consistency.
- **Long videos** (10+ min) take a while to extract (yt-dlp full download +
  per-clip cut). Acceptable; extraction is resumable and retries once.
- **export.js default re-burn** means repeated `/clipping` runs redo the shorts
  burn every time — cheap (one ffmpeg pass per clip), kept simple on purpose.
- The skill lives in the `media` category alongside `shorts-clipping-pipeline`;
  no name conflicts.

## Open Questions

1. Should `/clipping` support an optional platform flag later
   (`/clipping <url> <n> --tiktok`)? YAGNI — skipped for now, `--platforms` is
   documented in the skill body.
2. Want the skill to also deliver `_tiktok`/`_reels` variants by default? Current
   design: shorts only (the no-suffix file), matching the user's Telegram use case.

## Execution Handoff

After approval: implement Task 1 → 4 in order (each verified before the next),
then report the fresh-session `/clipping` run's MEDIA: output and the board
state. Tasks 1–2 are tiny (one block each); Task 3 is the bulk; Task 4 is the
proof.