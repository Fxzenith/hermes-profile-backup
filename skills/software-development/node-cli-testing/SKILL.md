---
name: node-cli-testing
description: Test interactive Node.js readline CLIs without a TTY.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [testing, node, cli, readline, tdd]
    related_skills: [test-driven-development, repo-as-skill]
---

# Testing Interactive Node.js CLIs (readline prompt loops)

Unit-test a CLI orchestrator that gates the user with `readline.createInterface({...}).question(...)` — without a terminal, without firing the network pipeline.

## When to use
- A Node CLI has an interactive approval/edit/prompt loop (e.g. `node main.js <url>` pausing for yes/no, per-item review).
- You want a regression test that proves edits/drops/persisted state actually flow to the next pipeline step.
- Companion to test-driven-development: apply RED-GREEN-REFACTOR; this skill covers the *mechanics* of driving the loop.

## The trap (read this first)
`process.stdin` is **READ-ONLY** in Node 22+. You CANNOT reassign it (`process.stdin = fakeStream` throws "Cannot set property stdin ... which has only a getter"). `readline` reads the stream via internal `'line'` events, so a plain async-iterator stub won't drive it either. **Monkeypatch `readline.createInterface` instead.**

## Step 1 — make the CLI importable
Wrap the top-level run so `require()` doesn't execute the pipeline:

```js
if (require.main === module) {
  main().catch(err => { console.error(err.message || err); process.exit(1); });
}
module.exports = { waitForApproval, validateClipsSchema, scoreClip, estimateDownload };
```

## Step 2 — drive the loop from a queue
```js
const readline = require('readline');
let QUEUE = [];
readline.createInterface = () => ({
  question(q, cb) { cb(QUEUE.shift() ?? ''); }, // one entry per question() call, in order
  close() {},
});
// per test:  QUEUE = ['e', 'e', '8', 'd'];   // edit field=end, value=8, then drop
//            await m.waitForApproval(false);
```
For multi-step branches (e.g. "edit" prompts field-then-value), push answers in the EXACT order `question()` consumes them.

## Step 3 — assert the artifact, not stdout
Assert on real side effects downstream steps depend on: the rewritten manifest file, a thrown error, exit code. Never assert on prompt text.

## Pitfalls
- Don't `delete require.cache` blindly when the module also runs `loadConfig()` at import — guard re-imports if config caching bites.
- Clean up fixtures BEFORE restoring backups (read the persisted artifact first, then restore originals).
- `readline` is global; restore it between test files or isolate per-file.

Full worked example: `references/node-cli-testing.md` (the 7-test `test_approval_gate.js` from the autoclipping approval-gate work).
