---
name: automation-pipeline-ops
description: "Repair broken cron jobs and deliver result messages."
version: 0.2.0
author: Hermes
metadata:
  hermes:
    tags: [Cron, Automation, Diagnostics, Backup]
---

# Automation Pipeline Ops

Class-level operations for the user's always-on automations (Instagram daily auto-poster via cron job `18d280b4af39`, the `hermes-profile-backup-daily` job, and any future scheduled pipelines). Three recurring task types: **"did the job fire?"** diagnostics, **renaming/moving a live pipeline directory**, and **fixing a failed cron so its result message actually delivers**.

## 1. Diagnose "the job didn't trigger"

The recurring complaint: *"last [artifact] is 1 day old, I think the cron didn't trigger."* ~90% of the time it's a timing/expectation mismatch, not a broken job. Order of operations:

1. `cronjob list` → read `last_run_at`, `last_status`, `next_run_at` for the job id.
2. Get the REAL server clock: `date '+%F %T %Z (%z)'` — compare against last/next run in the same TZ.
3. If `last_status == "ok"` and `next_run_at` is still in the future → the job is healthy; today's run simply hasn't fired yet. An artifact stamped "1 day old" exactly matches a daily job that ran yesterday: the post the user sees **is** the successful run.
4. Verify real-world side effects (the post/artifact itself) rather than trusting the script's report or the user's inference.
5. Separate **trigger failure** from **engagement/reach failure**: "post live but 1 like / no views" is an engagement problem — do NOT rewrite pipeline code to "fix" it. Say so explicitly.
6. Escalate to true fault-finding only when status changed or the job is actually overdue: read `~/.hermes/cron/output/<job_id>/<timestamp>.md` (what the scheduled agent actually did) and re-check `last_delivery_error`.

Key trap: the job's prompt contains a literal "Work from <absolute path>" line. When the directory is renamed/moved, that prompt text must change too — the `workdir` field alone is not enough (see checklist below).

## 2. Rename / move a live pipeline directory

Symptom: user says "change the name from X to Y" pointing at a cron `workdir`. First check the job `name` field — it may already say what they want; often they mean the **folder**, not the job name. Full safe rename:

1. **Find every reference first**: `grep -rl '<old-path>' <dir> ~/.hermes --include='*.py' --include='*.sh' --include='*.md' --include='*.json'` (skip `cron/output` history, `__pycache__`, curator backups — historical). Check scripts, `.env`, configs.
2. `mv /old/name "/root/New Name"`. Spaces are legal but painful — see pitfalls.
3. Patch scripts: runtime constants (e.g. `WORKDIR = Path("/root/...")`) AND docstring/usage lines showing `cd<dir> && python3 ...`.
4. Patch `/root/.hermes/cron/jobs.json`: BOTH the `"workdir"` value AND the `Work from <old-path>` substring inside the JSON-escaped `"prompt"` blob (uses literal `\n` escapes — patch the plain-text token only). Validate: `python3 -c "import json; json.load(open('/root/.hermes/cron/jobs.json'))"`.
5. **Prove it from the new path before declaring done**: run the pipeline's health/self-heal script with CWD at the new directory; confirm exit 0 / healthy output.
6. Update memory entries referencing the old path.

## 3. Fix a failed cron and make it report results

Symptom: user reports "the cron failed" (you see `Script exited with code N` + stderr) OR "I didn't get the cron's result message." The job fired but either errored or went silent. Procedure:

1. **Read the job's real state** — `read_file` `/root/.hermes/cron/jobs.json`, find the job by `id`. Capture `last_status`, `last_error`, `last_run_at`, `last_delivery_error`, `deliver`, `workdir`, `no_agent`, `script`.
2. **Read the script** — `read_file` `~/.hermes/scripts/<script>` (and the `workdir` copy if present). Reproduce the error locally via the `terminal` tool with the same CWD the cron uses (respect `workdir`; quote paths with spaces).
3. **Fix the root cause**, not the symptom:
   - `fatal: not a git repository (or any of the parent directories): .git` → the destination lost its `.git`. Re-clone the remote into the `workdir`/`DST` (the backup script self-heals via `git clone` if `.git` missing — ensure that branch exists).
   - `target missing: /old/path/...` → the project moved; update the cron `workdir` (and any path embedded in the `prompt` blob) to the new absolute path. See section 2.
   - `HTTP 429: Rate limit exceeded: free-models-per-day` on an `openrouter/free` LLM → the agent-driven job exhausted free quota. Convert it to `no_agent` + a script chain (see the IG daily pipeline pattern: replace the LLM prompt with `ig_daily_pipeline.sh`).
4. **Harden the script so results ALWAYS deliver.** For `no_agent` jobs, the cron delivers the script's **stdout** to `deliver`. Contract:
   - Emit a result line on EVERY exit path (success AND handled failure): `✅ ... OK` / `❌ ... FAILED`.
   - Exit `0` even on handled failure, so the result is delivered as a normal Telegram message instead of being dropped or shown only as a silent error. (An unhandled crash still exits non-zero — that's fine, it surfaces the error.)
   - Keep a self-heal branch (e.g. `if [ ! -d "$DST/.git" ]; then git clone ...; fi`) so a transient missing-repo failure heals itself next tick.
5. **Verify the fix locally** via `terminal`: run the script with the cron's CWD; confirm it prints the success line and exits 0, and that the side effect landed (e.g. `git log -1` shows a new commit, or the file is uploaded).
6. **Force a real post-fix run to actually deliver the message** — `cronjob action="run"` with the `job_id`. This is the ONLY way to confirm `deliver` works end-to-end (a script that "works locally" still won't send a Telegram message until the cron fires it).
7. **Confirm delivery** — `/root/.hermes/cron/executions.db` is SQLite; query the latest row for the `job_id`: `status == 'completed'` and `error IS NULL`. Then re-read `jobs.json`: `last_status == 'ok'` and `last_delivery_error == null`. The result line is now in the user's Telegram (`deliver` target).

Key insight — "no result message" usually means the job hadn't *succeeded* since the fix: the failing run was the last one before repair, and the next scheduled run hadn't fired yet. Triggering a manual run (step 6) is what actually sends the message.

## Pitfalls

- **Spaces in the folder name break shell usage**: every `cd`/path must be quoted (`cd "/root/Instagram daily auto-post"`), docstring examples need `\ ` escapes. If the user doesn't care about the exact label, recommend a hyphenated slug.
- A cron `workdir` must exist at tick time — verify right after `mv`, never "later".
- Historical artifacts (workspace/ post_meta.json, cron output logs) referencing the old path are records, not wiring — leave them.
- Renaming the cron's `name` does NOT relink anything; it's cosmetic. The relink is `workdir` + the prompt-embedded path.
- `/root/.hermes/cron/jobs.json` is the source of truth for schedule, prompt, workdir, deliver target. Direct edits are fine (scheduler re-reads it); re-validate JSON after editing.
- A `no_agent` cron delivers **stdout** to `deliver`. If the script emits nothing (or only writes to a log file), the user gets no message — always `echo`/`print` the result line to stdout.
- `deliver: telegram:6898985502` is the user's DM; `deliver: local` means no message is sent (watchdog jobs use this). Check `deliver` before assuming a message should arrive.
- `jobs.json` `last_run_at`/`last_status` only update after a REAL cron run — a manual `terminal` test of the script does NOT update them; use step 6/7 to confirm.
- GitHub warns when a committed file exceeds 50 MB (LFS warning). The backup's `state.db` can hit ~52 MB; it still works but consider excluding regenerable `state.db` from the mirror if you want a clean repo.

## Support files

- `references/instagram-autoposter-ops.md` — actual pipeline facts (accounts, connection names, self-heal exit-code contract, 2026-08-09 diagnostic + rename session record).
