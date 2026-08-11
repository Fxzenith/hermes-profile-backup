#!/usr/bin/env bash
# Monthly full Hermes backup -> GitHub Release (keeps the 2 most recent). Silent on success.
set -euo pipefail
DATE=$(date +%Y%m%d)
ZIP="/tmp/hermes-full-$DATE.zip"
LOG="${BACKUP_LOG:-$HOME/.hermes/logs/backup_profile.log}"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" >> "$LOG"; }

hermes backup -o "$ZIP"
gh release create "full-$DATE" "$ZIP" --repo Fxzenith/hermes-profile-backup --title "Full backup $DATE" >/dev/null
rm -f "$ZIP"

# Keep only the 2 most recent full-* releases
gh release list --repo Fxzenith/hermes-profile-backup --json tagName --jq '.[].tagName' \
  | grep '^full-' | sort -r | tail -n +3 \
  | while read -r tag; do gh release delete "$tag" --repo Fxzenith/hermes-profile-backup --yes >/dev/null; log "deleted old release $tag"; done

log "full backup release full-$DATE created"
