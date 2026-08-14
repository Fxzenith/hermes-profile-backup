#!/usr/bin/env bash
# Daily Instagram auto-post pipeline launcher (called by cron, no_agent).
#
# Chains the already-self-healing scripts end to end:
#   1. self_heal.py    -- verify Composio + IG connection healthy
#   2. composio_post.py -- generate quote image + publish via Composio
#   3. comment_loop.py  -- seed + reply to comments (state-tracked)
#   4. post_story.py    -- publish a story from the newest post image
#
# Emits a result line on EVERY run (cron delivers stdout to Telegram).
# Exit 0 normally so the result message is delivered as a normal post.
set -uo pipefail

REPO="/root/projects/Instagram daily auto-post"
LOG="$REPO/logs/cron.log"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

mkdir -p "$(dirname "$LOG")"
log() { echo "[$NOW] $*" >> "$LOG"; }

if [ ! -d "$REPO" ]; then
  echo "❌ IG pipeline FAILED ($NOW): project dir missing: $REPO"
  log "FAILED: repo missing"
  exit 0
fi
cd "$REPO" || { echo "❌ IG pipeline FAILED ($NOW): cannot cd $REPO"; exit 0; }

# 1. pre-flight
python3 scripts/self_heal.py > "$LOG.heal" 2>&1
if ! python3 - <<'PY'
import sys, json
try:
    r = json.load(open("logs/cron.log.heal"))
except Exception:
    sys.exit(1)
if not r.get("healthy"):
    sys.exit(2)
PY
then
  echo "❌ IG pipeline BLOCKED ($NOW): self-heal reports unhealthy connection. Check Composio auth."
  log "FAILED: self-heal unhealthy"
  cat "$LOG.heal" >> "$LOG"
  exit 0
fi

# 2. generate + post
if ! python3 scripts/composio_post.py >> "$LOG" 2>&1; then
  echo "❌ IG pipeline FAILED ($NOW): composio_post.py exited non-zero. See $REPO/logs/cron.log"
  log "FAILED: composio_post"
  exit 0
fi

# 3. comment engagement
python3 scripts/comment_loop.py >> "$LOG" 2>&1 && creplies="ok" || creplies="failed(non-fatal)"

# 4. story
python3 scripts/post_story.py >> "$LOG" 2>&1 && story="ok" || story="failed(non-fatal)"

echo "✅ IG daily pipeline OK ($NOW): posted to @ze.nith001 | comments=$creplies story=$story"
log "pipeline complete: comments=$creplies story=$story"
