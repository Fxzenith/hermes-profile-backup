---
name: hermes-profile-backup
description: "Use when backing up or restoring the Hermes profile."
---

# Hermes Profile Backup & Restore

Class-level workflow for making the Hermes profile (`~/.hermes`) survive a full machine reset / reinstall, and for restoring it. Triggers: "create a backup of my profile/repo", "if everything resets we can continue", "migrate Hermes to a new machine", "restore after a wipe".

## Choose the mechanism

- **Primary: versioned git repo** mirroring `~/.hermes` content — diffable, auto-pushable (cron), byte-for-byte restore. Best when the user says "repo". The `hermes backup` zip and `hermes profile export` docs pages may be unreachable from this box (web auth failure) — verify commands locally with `hermes <cmd> --help`.
- **Secondary: `hermes backup`** (official full zip; `--quick` = critical state only) — monthly point-in-time artifact via `gh release`.
- **Tertiary: `hermes profile export|import|install`** — official profile archive; `install <git-url>` ships a profile distribution.

## Core steps (implemented & verified 2026-08-11)

1. **Git identity + private repo**: set `user.name`/`user.email` (repo holds `.env`/`auth.json` secrets — MUST be private), run `gh auth setup-git` so cron pushes work, then `gh repo create <name> --private --confirm`.
2. **Backup script** (`~/.hermes/scripts/backup_profile.sh`): `sqlite3 .backup` of `state.db` (WAL-safe), rsync mirror with excludes, commit + push only when something changed.
3. **First snapshot + `.gitignore` + `MANIFEST.md`** (inventory of external dirs: gbrain, pipelines, venvs, agentmail creds) → push.
4. **Restore drill via `HERMES_HOME` staging** — prove recovery WITHOUT touching the live profile (see reference).
5. **Daily cron** (`no_agent` script job) + optional **monthly full zip → gh release** (keep the 2 most recent releases).
6. **README restore runbook** in the repo so a stranger can rebuild the box.

## Pitfalls (all hit in the field)

- **`rsync --delete` destroys the repo it backs into**: mirroring `~/.hermes` INTO the git working tree makes `.git/`, `.gitignore`, `README.md`, `MANIFEST.md` look extraneous. They survive ONLY if explicitly excluded in the rsync (excludes protect against deletion too).
- **`state.db` is live WAL-mode SQLite**: never rsync it raw. `sqlite3 "$SRC/state.db" ".backup '$DST/state.db'"` is the online-safe consistent snapshot; exclude `state.db*` from rsync.
- **SQLite sidecars**: `*.db-shm` / `*.db-wal` (kanban.db, projects.db…) churn constantly — exclude + gitignore them or they pollute the repo.
- **cronjob tool rejects absolute script paths** — must be a bare filename relative to `~/.hermes/scripts/`.
- **Cron `deliver` defaults to `local`** on desktop/CLI sessions (no live channel) — the job runs, but failure alerts vanish. Read `~/.hermes/channel_directory.json` for gateway channel ids and set `deliver='telegram:<chat_id>'` explicitly.
- **no_agent cron: deliver a result line on EVERY run** (user preference). The user wants cron output posted to Telegram on every run, not only on failure. Pattern: always print one summary line — `✅ OK (<ts>): <what>` or `❌ FAILED (<ts>): <reason>` — and ALWAYS `exit 0` (so it posts as a normal message, not a crash trace). Log details to a file; print only the summary. A bare non-zero exit also alerts, but mid-script hard failures emit confusing stack traces; a deliberate result line + `exit 0` gives a clean message every time.
- **Git identity + credential helper**: no `user.name`/`user.email` → commits fail; `gh auth setup-git` wires the helper so unattended cron pushes work.
- **DST must actually be a git repo (repo-drift failure)**: if `DST` (default `~/hermes-profile-backup`) is only a plain rsync mirror with **no `.git`**, the script dies at `git add` with `fatal: not a git repository` (exit 128) and the cron reports FAILED. This happens when the real repo was created at a different path (e.g. `/root/projects/hermes-profile-backup`) while a separate non-git mirror sits at the canonical path. Verify the repo lives at the script's default DST: `git -C "$DST" rev-parse --is-inside-work-tree`. Fix: clone the canonical repo into `DST` (`git clone <remote> "$DST"`) and remove orphaned copies; or self-heal in-script (see reference) by cloning when `.git` is missing.
- **Size budget**: `state.db` is now ~51 MB — already over GitHub's **50 MB soft limit** (it still pushes, but emits a `GH001 Large files` warning every run). The hard cap is 100 MB. Add Git LFS for `state.db` (or prune old sessions) before it approaches 100 MB, or future pushes will be rejected.
- **Secrets**: `.env` + `auth.json` live in the repo — keep it private; consider `age`-encrypting as hardening.

## Support files

- `references/backup-recipe.md` — exact verified commands, the current self-healing `backup_profile.sh` (clone-on-missing-`.git`, always-emit-result + `exit 0`), `monthly_full_backup.sh`, cron params, restore runbook, staged-drill + ad-hoc verification patterns, and a 2026-08-13 incident writeup (repo-drift → exit 128 fix).
