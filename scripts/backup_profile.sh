#!/usr/bin/env bash
# Hermes profile backup: snapshot -> commit -> push. Silent on success (logs to file).
set -euo pipefail
SRC="$HOME/.hermes"
DST="${BACKUP_DEST:-$HOME/hermes-profile-backup}"
LOG="${BACKUP_LOG:-$HOME/.hermes/logs/backup_profile.log}"
mkdir -p "$DST" "$(dirname "$LOG")"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

# 1. Consistent snapshot of the live SQLite session store (WAL-safe online backup API)
sqlite3 "$SRC/state.db" ".backup '$DST/state.db'"

# 2. Mirror everything else, excluding regenerable data + repo metadata
#    (.git/, README.md, MANIFEST.md, .gitignore live in DST only — exclude so --delete can't nuke them)
rsync -a --delete \
  --exclude='cache/' --exclude='logs/' --exclude='lsp/' --exclude='bin/' \
  --exclude='image_cache/' --exclude='audio_cache/' --exclude='runtime/' \
  --exclude='sandboxes/' --exclude='desktop/' \
  --exclude='state.db*' --exclude='*.lock' --exclude='*.pid' \
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
  exit 0                                    # empty stdout = cron stays silent
fi
git commit -q -m "backup: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push -q origin HEAD
log "committed and pushed"
