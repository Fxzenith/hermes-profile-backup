#!/usr/bin/env bash
# Hermes profile backup: snapshot -> commit -> push.
# Emits a result line on EVERY run (cron delivers stdout to Telegram).
set -uo pipefail

SRC="$HOME/.hermes"
DST="${BACKUP_DEST:-$HOME/hermes-profile-backup}"
LOG="${BACKUP_LOG:-$HOME/.hermes/logs/backup_profile.log}"
REMOTE="${BACKUP_REMOTE:-https://github.com/Fxzenith/hermes-profile-backup.git}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$DST" "$(dirname "$LOG")"
log() { echo "[$NOW] $*" >> "$LOG"; }
# Always exit 0 so the result line is delivered as a normal Telegram message (not a silent error).
fail() { echo "❌ Hermes profile backup FAILED ($NOW): $*"; log "FAILED: $*"; exit 0; }

# 0. Self-heal: ensure the destination is a git repo (clone from remote if missing).
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
  log "no changes, skipping"
  exit 0
fi

git commit -q -m "backup: $NOW" || fail "git commit failed"
git push -q origin HEAD || fail "git push failed"

N=$(git diff --name-only HEAD~1 HEAD 2>/dev/null | wc -l | tr -d ' ')
echo "✅ Hermes profile backup OK ($NOW): committed + pushed $N file(s) -> ${REMOTE##*/}"
log "committed and pushed $N file(s)"
