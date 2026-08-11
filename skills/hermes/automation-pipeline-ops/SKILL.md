---
name: automation-pipeline-ops
description: "Diagnose 'cron didn't fire'; rename live pipeline dirs."
---

# Automation Pipeline Ops

Class-level operations for the user's always-on automations (Instagram daily auto-poster via cron job `18d280b4af39`, and any future scheduled pipelines). Two recurring task types: **"did the job fire?"** diagnostics and **renaming/moving a live pipeline directory**.

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

## Pitfalls

- **Spaces in the folder name break shell usage**: every `cd`/path must be quoted (`cd "/root/Instagram daily auto-post"`), docstring examples need `\ ` escapes. If the user doesn't care about the exact label, recommend a hyphenated slug.
- A cron `workdir` must exist at tick time — verify right after `mv`, never "later".
- Historical artifacts (workspace/ post_meta.json, cron output logs) referencing the old path are records, not wiring — leave them.
- Renaming the cron's `name` does NOT relink anything; it's cosmetic. The relink is `workdir` + the prompt-embedded path.
- `/root/.hermes/cron/jobs.json` is the source of truth for schedule, prompt, workdir, deliver target. Direct edits are fine (scheduler re-reads it); re-validate JSON after editing.

## Support files

- `references/instagram-autoposter-ops.md` — actual pipeline facts (accounts, connection names, self-heal exit-code contract, 2026-08-09 diagnostic + rename session record).