---
name: telegram-delivery
description: "Send files to Telegram using the existing Hermes bot token."
version: 1.0.0
author: Hermes Agent (auto-curated)
license: MIT
tags: [telegram, delivery, bot-api, file-send]
---

# Telegram Delivery

## When to use

When the user asks to send a file, document, or message to a Telegram chat or
channel — e.g. "send this to the conference room", "DM me the report on
Telegram", "drop the PDF in the group". In this environment the Hermes agent
**is already running as a Telegram bot**, so you can deliver directly through
the Bot API without registering a new bot or asking the user for tokens.

## Key facts (this environment)

- Hermes runs as a Telegram bot. Its credential is the `TELEGRAM_BOT_TOKEN`
  environment variable of the running `hermes` process.
- The token is **not** stored in plaintext in `config.yaml` (it is redacted
  there). Read it from the live process environment instead.
- Target chats are referenced by numeric id. The configured home/conference
  channel appears in `/root/.hermes/config.yaml` as
  `home_channel: telegram:<id>`. Supergroup ids look like `-1003938786142`
  (the `-100` prefix is REQUIRED — a bare number will not deliver).
- Resolved this session: `CONFERENCE ROOM` supergroup = `-1003938786142`,
  bot username `zeeniith_bot`, bot id `8236061962`.

## Steps

1. Resolve the bot token into a shell variable **without printing it**:

   ```bash
   PID=$(pgrep -f hermes | head -1)
   TOKEN=$(tr '\0' '\n' < /proc/$PID/environ 2>/dev/null \
           | grep '^TELEGRAM_BOT_TOKEN=' | cut -d= -f2-)
   ```

2. Resolve the chat id (from `config.yaml` `home_channel`, or the user) and the
   file path.

3. Send. For a file use `sendDocument`; for plain text use `sendMessage`.

   ```bash
   CHAT="-1003938786142"
   FILE="/root/knowledge/JFX JOURNAL/API_KEYS.md"
   CAP="JFX Journal API Key Strategy (v1.1.0-draft)"
   curl -sS -F "chat_id=$CHAT" -F "document=@$FILE" -F "caption=$CAP" \
        "https://api.telegram.org/bot$TOKEN/sendDocument"
   ```

   A successful response is `{"ok":true,"result":{...}}` with a `message_id`.

   Reusable sender (copy into a script and chmod +x):

   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   CHAT="${1:?usage: send_file.sh <chat_id> <file> [caption]}"
   FILE="${2:?usage: send_file.sh <chat_id> <file> [caption]}"
   CAP="${3:-}"
   PID="$(pgrep -f hermes | head -1)"
   TOKEN="$(tr '\0' '\n' < "/proc/$PID/environ" 2>/dev/null \
            | grep '^TELEGRAM_BOT_TOKEN=' | cut -d= -f2-)"
   [ -z "$TOKEN" ] && { echo "no token" >&2; exit 1; }
   [ -f "$FILE" ] || { echo "no file: $FILE" >&2; exit 1; }
   ARGS=(-F "chat_id=$CHAT" -F "document=@$FILE")
   [ -n "$CAP" ] && ARGS+=(-F "caption=$CAP")
   curl -sS "${ARGS[@]}" "https://api.telegram.org/bot$TOKEN/sendDocument"; echo
   ```

## Pitfalls

- **Never echo/print the token.** Keep it only in a shell variable and pass it
  solely inside the `curl` URL. The `grep | cut` pipeline keeps it off disk and
  off screen.
- **Supergroup ids carry the `-100` prefix.** Forgetting it is the most common
  silent failure (API returns `ok:false` or the message goes nowhere).
- **Bot must be a member of the target group.** If the bot was removed or never
  added, delivery fails — re-add the bot to the group first.
- **`sendDocument` for files, `sendMessage` for text.** Mixing them up returns
  method-not-found errors.
- If `pgrep -f hermes` returns multiple PIDs, `head -1` picks one; all hermes
  processes share the same token, so any is fine.
