# Worked example: autoclipping approval-gate test

From the session that built an interactive approval gate into `main.js` (YouTube → Shorts clip pipeline). The gate pre-flights clip hooks against the transcript, scores each clip, then loops per-clip: `[a]pprove [e]dit [d]rop [all] [q]`. Edits/drops are written back to `data/clips.json`.

## What the test proves (7 cases)
1. pre-flight PASS — valid hooks + in-bounds + non-overlapping
2. pre-flight FAIL — hook absent from transcript (throws with "hook not found")
3. pre-flight FAIL — clip window beyond video duration
4. pre-flight FAIL — overlapping clips
5. `scoreClip` — 10-25s ideal scores 100, long scores 1, very short 65
6. `estimateDownload` — 70s → ~70 MB
7. interactive loop — fed `['e','e','8','d']` → edits clip 1 end to 8s, drops clip 2, persists 1 clip to clips.json

## Key snippets
```js
const readline = require('readline');
let QUEUE = [];
readline.createInterface = () => ({
  question(q, cb) { cb(QUEUE.shift() ?? ''); },
  close() {},
});

// make main.js importable
if (require.main === module) { main().catch(e => { console.error(e.message||e); process.exit(1); }); }
module.exports = { waitForApproval, validateClipsSchema, validateClipsAgainstTranscript, scoreClip, estimateDownload };
```

## Run
```bash
cd /root/projects/autoclipping
node test_approval_gate.js
# -> ALL APPROVAL-GATE TESTS PASSED
```

## Lesson
Assert on the rewritten file (`clips.json`), not on the printed prompt. The pipeline's `extract.js` reads that file next step — so the test proves the edit/drop actually reaches the download stage.
