#!/usr/bin/env bash
# tldraw_req.sh — authenticated request helper for the remote-bridge workflow.
# Usage: bash scripts/tldraw_req.sh <endpoint> <payload-file.json> [METHOD]
#   endpoint   e.g. /api/search or /api/doc/<DOCID>/exec
#   payload    a file containing raw JSON: {"code":"..."} (json) or JS source (text/plain)
#   METHOD     default POST
# Reads the bearer token from ~/.config/tldraw/server.json (re-read every call).
set -euo pipefail

BASE="${TLDRAW_BASE:-http://127.0.0.1:7236}"
ENDPOINT="${1:?usage: tldraw_req.sh <endpoint> <payload.json> [METHOD]}"
PAYLOAD_FILE="${2:?missing payload file}"
METHOD="${3:-POST}"

TOKEN="$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.config/tldraw/server.json')))['token'])")"

curl -s --max-time 60 -X "$METHOD" "$BASE$ENDPOINT" \
  -H 'content-type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  --data "@$PAYLOAD_FILE"
echo
