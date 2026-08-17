---
name: jfx-journal
description: Use the JFX Journal API to answer questions about the user's private trading journal, trades, notes, analytics, and bridge state.
---

# JFX Journal

The API key is NOT stored here (never put it in source control or in this file).
It lives in `~/jfx/key` (actually `/root/.jfx/key`) with 600 perms.
Load it into the shell before any call:

    export JFX_KEY=$(cat /root/.jfx/key)

Base URL: https://lwlikhjgwazyrahucatl.supabase.co/functions/v1/jfx-api

Every request must send `X-API-Key: $JFX_KEY` (use the env var, never inline the raw key).

## Common requests

- Latest trade:    `GET /v1/trades?limit=1`
- Recent trades:   `GET /v1/trades?limit=20`
- Trade summary:   `GET /v1/analytics/summary`
- Monthly summary: `GET /v1/analytics/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`
- Notes:           `GET /v1/notes?limit=20`
- Bridge health:   `GET /v1/bridge/status`

## Usage pattern (bash)

    export JFX_KEY=$(cat /root/.jfx/key)
    curl -s -H "X-API-Key: $JFX_KEY" \
      "https://lwlikhjgwazyrahucatl.supabase.co/functions/v1/jfx-api/v1/trades?limit=1"

Only call endpoints covered by the key's scopes. Explain API errors plainly; never invent journal data.
If a request fails, print the HTTP status and body so the error is visible — do not fabricate results.
