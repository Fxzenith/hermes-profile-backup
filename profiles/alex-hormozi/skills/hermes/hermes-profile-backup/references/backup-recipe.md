# Backup Recipe — verified 2026-08-11 on this VPS

Full working setup for the git-repo profile backup. All commands below ran successfully; the 44-check ad-hoc verification passed.

## Repo + identity

```bash
gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"'   # noreply email (avoids exposing personal email)
git config --global user.name "Fxzenith"
git config --global user.email "<noreply address>"
gh auth setup-git                                                 # wires git credential helper so cron pushes work
gh repo create hermes-profile-backup --private --description "..." --confirm
mkdir -p ~/hermes-profile-backup && cd ~/hermes-profile-backup
git init -b main && git remote add origin https://github.com/Fxzenith/hermes-profile-backup.git
git commit --allow-empty -m "chore: init backup repo"
```

## backup_profile.sh (daily — verified, self-healing)

Excludes: regenerable dirs, SQLite sidecars, AND repo metadata (`.git/`, `.gitignore`, `README.md`, `MANIFEST.md`) — the metadata excludes are what keep `rsync --delete` from destroying the repo it backs into.

Emits a result line on EVERY run and always `exit 0` so the cron delivers it to Telegram (user wants results every run, not only on failure). Mid-step failures print `❌ FAILED` + reason instead of crashing so the message stays clean.

```bash
#!/usr/bin/env bash
# Hermes profile backup: snapshot -> commit -> push. Emits a result line on EVERY run.
set -uo pipefail
SRC="$HOME/.hermes"
DST="${BACKUP_DEST:-$HOME/hermes-profile-backup}"
LOG="${BACKUP_LOG:-$HOME/.hermes/logs/backup_profile.log}"
REMOTE="${BACKUP_REMOTE:-https://github.com/Fxzenith/hermes-profile-backup.git}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
mkdir -p "$DST" "$(dirname "$LOG")"
log() { echo "[$NOW] $*" >> "$LOG"; }
fail() { echo "❌ Hermes profile backup FAILED ($NOW): $*"; log "FAILED: $*"; exit 0; }

# 0. Self-heal: ensure DST is a git repo (clone from remote if .git missing).
if [ ! -d "$DST/.git" ]; then
  tmp="${DST}.clone.$$"
  if git clone -q "$REMOTE" "$tmp" 2>"$LOG.cloneerr"; then
    rm -rf "$DST"; mv "$tmp" "$DST"; log "DST reinitialized from $REMOTE"
  else
    fail "DST $DST is not a git repo and clone of $REMOTE failed: $(tail -1 "$LOG.cloneerr" 2>/dev/null)"
  fi
fi
cd "$DST" || fail "cannot cd into $DST"

# 1. Consistent snapshot of the live SQLite session store (WAL-safe online backup API)
sqlite3 "$SRC/state.db" ".backup '$DST/state.db'" || fail "sqlite3 state.db snapshot failed"

# 2. Mirror everything else, excluding regenerable data + repo metadata
rsync -a --delete \
  --exclude='cache/' --exclude='logs/' --exclude='lsp/' --exclude='bin/' \
  --exclude='image_cache/' --exclude='audio_cache/' --exclude='runtime/' \
  --exclude='sandboxes/' --exclude='desktop/' \
  --exclude='state.db*' --exclude='*.db-shm' --exclude='*.db-wal' --exclude='*.lock' --exclude='*.pid' \
  --exclude='models_dev_cache.json' --exclude='ollama_cloud_models_cache.json' \
  --exclude='provider_models_cache.json' --exclude='.update_check' \
  --exclude='.mcp-discovery.lock' --exclude='processes.json' \
  --exclude='.git/' --exclude='.gitignore' --exclude='README.md' --exclude='MANIFEST.md' \
  "$SRC/" "$DST/" || fail "rsync mirror failed"

# 3. Commit + push only when something changed
git add -A
if git diff --cached --quiet; then
  echo "✅ Hermes profile backup OK ($NOW): no changes since last backup."
  log "no changes, skipping"; exit 0
fi
git commit -q -m "backup: $NOW" || fail "git commit failed"
git push -q origin HEAD || fail "git push failed"
N=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | wc -l | tr -d ' ')
echo "✅ Hermes profile backup OK ($NOW): committed + pushed $N file(s) -> ${REMOTE##*/}"
log "committed and pushed $N file(s)"
```

Run manually: `BACKUP_DEST=... ~/.hermes/scripts/backup_profile.sh`. Result size: ~909 MB working tree (state.db 51 MB + skills/checkpoints + rest).

### Incident 2026-08-13 — cron FAILED: "fatal: not a git repository (or any of the parent directories): .git"

Symptom: daily `hermes-profile-backup-daily` cron exited 128, stderr `fatal: not a git repository`.

Cause (repo-drift): the script default `DST=~/hermes-profile-backup` was a **plain rsync mirror with no `.git`**. The actual git repo (`.git`, history, GitHub remote) had been created at a different path — `/root/projects/hermes-profile-backup` — while a separate non-git mirror sat at the canonical path the script targets. An Aug 13 run rsynced fresh data into the non-git copy; the subsequent `git add` then crashed. Two duplicate copies existed plus a stale `.bak`.

Fix applied:
1. Moved the broken non-git mirror aside, then `git clone <remote> /root/hermes-profile-backup` into the canonical path (pulled history + remote + `.git`).
2. Removed the orphaned `/root/projects/hermes-profile-backup` and the `.bak` so there is a single source of truth.
3. Rewrote the script with the self-heal guard above and the always-emit-result `exit 0` behavior.
4. Verified: first run committed 4804 files + pushed; subsequent runs idempotent; cron still resolves `backup_profile.sh` from `~/.hermes/scripts/`.

Lesson: when a `DST` git failure appears, first confirm which directory the script actually uses (`BACKUP_DEST` default) is the real repo, and check for stray duplicate clones at other paths before assuming the script is wrong.

## monthly_full_backup.sh (gh release with retention)

```bash
#!/usr/bin/env bash
set -euo pipefail
DATE=$(date +%Y%m%d)
ZIP="/tmp/hermes-full-$DATE.zip"
LOG="${BACKUP_LOG:-$HOME/.hermes/logs/backup_profile.log}"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }
hermes backup -o "$ZIP"
gh release create "full-$DATE" "$ZIP" --repo Fxzenith/hermes-profile-backup --title "Full backup $DATE" >/dev/null
rm -f "$ZIP"
# keep only the 2 most recent full-* releases
gh release list --repo Fxzenith/hermes-profile-backup --json tagName --jq '.[].tagName' \
  | grep '^full-' | sort -r | tail -n +3 \
  | while read -r tag; do gh release delete "$tag" --repo Fxzenith/hermes-profile-backup --yes >/dev/null; log "deleted old release $tag"; done
log "full backup release full-$DATE created"
```

`hermes backup` full run: 828 files, 185.5 MB → 64 MB zip in ~13 s. Release URL: github.com/<owner>/<repo>/releases/tag/full-YYYYMMDD.

## Cron jobs (cronjob tool)

- Daily: `schedule='0 20 * * *'`, `no_agent=true`, `script='backup_profile.sh'` (bare filename — absolute paths rejected), `deliver='telegram:6898985502'`.
- Monthly: `schedule='0 4 1 * *'`, `no_agent=true`, `script='monthly_full_backup.sh'`, same deliver.
- `deliver` defaulted to `local` on the desktop session — had to read `~/.hermes/channel_directory.json` (`platforms.telegram[].id`) and set the DM id explicitly.
- Test-fire with `cronjob action='run'`; confirm via `~/.hermes/logs/backup_profile.log` + `git -C ~/hermes-profile-backup log --oneline -1`.

## Restore runbook (repo README)

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
git clone https://github.com/<owner>/<repo>.git ~/hermes-profile-backup
hermes gateway stop
rm -f ~/hermes-profile-backup/.gitignore ~/hermes-profile-backup/README.md ~/hermes-profile-backup/MANIFEST.md
rsync -a ~/hermes-profile-backup/ ~/.hermes/
hermes chat -q "list my cron jobs and memories"   # verify
```

## Staged restore drill (never touches live profile)

```bash
git clone <repo> /tmp/restore-test
mkdir -p /tmp/test-home && rsync -a /tmp/restore-test/ /tmp/test-home/
rm -f /tmp/test-home/.gitignore /tmp/test-home/README.md /tmp/test-home/MANIFEST.md
HERMES_HOME=/tmp/test-home hermes chat -q "list your memories and cron jobs"
rm -rf /tmp/restore-test /tmp/test-home
```

Verified result: restored profile booted with all 7 memory entries + all 4 cron jobs intact (REELS 18:00 reel, 11:00 IG post, comment sweep, ssh reaper).

## Ad-hoc verification pattern

Test the real scripts without touching the live repo: `mktemp -d /tmp/hermes-verify-XXXXXX` + trap cleanup; local bare remote (`git init --bare remote.git` + clone) so `git push` works; assert with explicit PASS/FAIL echo lines. Covered: syntax, sqlite `PRAGMA integrity_check`, restored payload presence, excluded dirs, sidecar absence, repo-metadata survival under `--delete`, idempotent second run, `git check-ignore` (18/18 junk ignored, secrets NOT ignored), release-retention pipeline. 44/44 passed.

Gotchas hit while writing the verification: empty-bare-repo clone defaults to `master` (branch-agnostic `git push origin HEAD` is fine — assert "some branch", not `main`); `sort -r | tail -n +3` lists deletion candidates newest-first (assert the SET, not the order).
