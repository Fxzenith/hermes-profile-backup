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

## backup_profile.sh (daily — verified)

Excludes: regenerable dirs, SQLite sidecars, AND repo metadata (`.git/`, `.gitignore`, `README.md`, `MANIFEST.md`) — the metadata excludes are what keep `rsync --delete` from destroying the repo it backs into.

```bash
#!/usr/bin/env bash
set -euo pipefail
SRC="$HOME/.hermes"
DST="${BACKUP_DEST:-$HOME/hermes-profile-backup}"
LOG="${BACKUP_LOG:-$HOME/.hermes/logs/backup_profile.log}"
mkdir -p "$DST" "$(dirname "$LOG")"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

# 1. Consistent snapshot of the live SQLite session store (WAL-safe online backup API)
sqlite3 "$SRC/state.db" ".backup '$DST/state.db'"

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
  "$SRC/" "$DST/"

# 3. Commit + push only when something changed
cd "$DST"
git add -A
if git diff --cached --quiet; then
  log "no changes, skipping"
  exit 0                                    # empty stdout = no_agent cron stays silent
fi
git commit -q -m "backup: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push -q origin HEAD
log "committed and pushed"
```

Run manually: `BACKUP_DEST=... ~/.hermes/scripts/backup_profile.sh`. Result size: ~226 MB (state.db 41 MB + skills 51 MB + checkpoints 43 MB + rest).

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
