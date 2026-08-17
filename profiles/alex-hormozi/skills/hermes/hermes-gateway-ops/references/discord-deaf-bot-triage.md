# Discord "bot connected but deaf" — deep-dive

Session-verified transcript of triaging a Hermes Discord bot (Atom101) that connected but never responded.

## Symptom

`grep -iE "discord" gateway.log` shows:

```
[Discord] Registered /skill command with 103 skill(s) via autocomplete
[Discord] Connected as Atom101#5846
✓ discord connected
```

...and then NOTHING else. Zero `inbound message: platform=discord` lines. Bot is online in Discord but every message goes unanswered.

## Root causes in order of likelihood

### 1. Mention-gating (Hermes adapter behavior — the usual culprit)

`plugins/platforms/discord/adapter.py` `_discord_message_admission()`:

- Non-DM guild messages are dropped unless the bot is explicitly mentioned, when `DISCORD_IGNORE_NO_MENTION` is truthy (DEFAULT: `"true"`).
- Exception: channels in the free-response allowlist (`gateway.discord.free_response_channels` / env `DISCORD_FREE_RESPONSE_CHANNELS`; `"*"` = all channels).
- Bot-authored messages, non-default message types (pins, system msgs) also dropped.
- DMs bypass the mention gate entirely (`dm_policy: open` → DMs admitted).
- Other gates that silently drop: `DISCORD_ALLOWED_USERS`, `DISCORD_ALLOWED_ROLES`, channel allowlists (`gateway.discord.allowed_channels`), bots policy (`DISCORD_ALLOW_BOTS`, default rejects bots).

Fix for the user: **DM the bot, or @mention it in a channel** (`@Atom101 hello`). Optionally set free-response channels so mentions aren't needed.

### 2. Bot not in the server (checked via REST, no portal needed)

```bash
TOKEN=$(hermes config get gateway.discord.token)
curl -s -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/users/@me/guilds
```

Returns JSON array of guilds the bot is in (name + id + permissions). Empty array → not invited anywhere. Invite URL:

```
https://discord.com/api/oauth2/authorize?client_id=<APPLICATION_ID>&permissions=2147485696&scope=bot
```

### 3. Privileged Gateway Intents disabled (portal-only, cannot verify via API)

The adapter requests (adapter.py ~line 1289):

```python
intents = Intents.default()
intents.message_content = True   # PRIVILEGED
intents.dm_messages = True
intents.guild_messages = True
intents.members = ...            # PRIVILEGED (Server Members)
intents.voice_states = True
```

If the portal hasn't granted them, Discord silently delivers no message events — bot still connects and shows online.

**June 10, 2026 change** (docs.discord.com/developers/gateway/getting-started-with-privileged-intent-review):
- Threshold is now **10,000 unique users** across all servers (was: 100 servers).
- Under 10k users: toggle on/off freely in Developer Portal → app → **Bot** → **Privileged Gateway Intents**.
- Over 10k: must apply for review; apps can keep using intents while in review; annual reapplication required.
- If the user reports "no toggle": double-check they're on the Bot page (left sidebar → Bot, scroll to bottom). The section exists for all apps under threshold; a screenshot settles it.

### 4. Misc

- `gateway.discord.dm_policy` / `group_policy`: `open` (default) vs `closed` — if closed, DM/group messages dropped.
- Adapter also runs a `reconcile` of slash commands at connect: `[Discord] Safely reconciled 64 slash command(s)` — normal.

## Log locations

- `$HERMES_HOME/logs/gateway.log` — main gateway log (inbound/outbound, connect/disconnect).
- Grep patterns: `discord`, `inbound message`, `Connected as`.
