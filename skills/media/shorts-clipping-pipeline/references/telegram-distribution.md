# Telegram Distribution for Clips

## Overview
The YT Clipper pipeline produces final videos in `/root/autoclipping/Outputs/` (per-platform variants: `_shorts.mp4`, `_tiktok.mp4`, `_reels.mp4`). This reference covers how to programmatically send those outputs to a Telegram channel using the Bot API.

**Fastest path in an interactive Hermes session: native `MEDIA:` delivery.** To send clips straight into the current Telegram DM, just put `MEDIA:/absolute/path/to/clip.mp4` lines in the final response — Hermes delivers them as native video messages (no curl, no token, no chat ID needed). Use the Bot API flow below only for scheduled/headless/cron delivery or sending to a channel the session isn't attached to. Verified: two ~5–12MB clips delivered this way; videos under 50MB send fine.

## Bot Configuration

The Telegram Bot Token is stored in **Hermes' .env** (`/root/.hermes/.env`) and the target chat ID is configured in **Hermes' config.yaml** (`/root/.hermes/config.yaml`):

```yaml
# config.yaml
home_channel: telegram:-1003938786142
```

```bash
# .env (line 480)
TELEGRAM_BOT_TOKEN=8236061962:AAHD...
```

The bot is `@zeeniith_bot` (id 8236061962).

## Sending Videos (curl)

```bash
TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" /root/.hermes/.env | cut -d= -f2-)
CHAT_ID="-1003938786142"

cd /root/autoclipping/Outputs
for f in *.mp4; do
  curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendVideo" \
    -F "chat_id=$CHAT_ID" \
    -F "video=@$f" \
    -F "caption=$f"
done
```

### Notes:
- The token in `.env` has masked characters (`***`) when viewed via `grep` without proper extraction. Always use `cut -d= -f2-` to get the full token.
- Max file size for `sendVideo` via Bot API is 50 MB. The clips in this pipeline are ~3-5 MB each, well within limits.
- Videos send successfully with `ok: true` response.
- Use `-F` for multipart/form-data (required for file upload).

## Verifying Bot Token

```bash
TOKEN=$(grep "^TELEGRAM_BOT_TOKEN=" /root/.hermes/.env | cut -d= -f2-)
curl -s "https://api.telegram.org/bot$TOKEN/getMe" | jq .
```

Expected response:
```json
{
  "ok": true,
  "result": {
    "id": 8236061962,
    "first_name": "Hermes Agent 101",
    "username": "zeeniith_bot"
  }
}
```

## Pitfalls

1. **Masked token in .env** — The `.env` file shows `TELEGRAM_BOT_TOKEN=8236061962:***` with asterisks. Direct copy-paste fails. Must extract with `cut -d= -f2-` or similar to get the real token.

2. **Chat ID format** — Use the full numeric ID including the `-100` prefix for channels/groups (e.g., `-1003938786142`). User IDs are positive numbers.

3. **Bot must be admin in channel** — The bot needs permission to post in the target channel. Invite `@zeeniith_bot` as an admin.

4. **50 MB limit** — If clips exceed this, use a file hosting service and send a link instead, or compress further.

## Integration with Pipeline

The pipeline's `export.js` (step 6) produces the final outputs. A natural extension would be a post-export hook that automatically sends to Telegram. Example pattern in Node:

```javascript
// After export.js completes
const { execSync } = require('child_process');
const fs = require('fs');

const TOKEN = process.env.TELEGRAM_BOT_TOKEN || 
  fs.readFileSync('/root/.hermes/.env', 'utf8')
    .match(/^TELEGRAM_BOT_TOKEN=(.+)$/m)?.[1]?.trim();
const CHAT_ID = '-1003938786142';

fs.readdirSync('Outputs')
  .filter(f => f.endsWith('.mp4'))
  .forEach(f => {
    execSync(`curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendVideo" \
      -F "chat_id=${CHAT_ID}" -F "video=@Outputs/${f}" -F "caption=${f}"`);
  });
```