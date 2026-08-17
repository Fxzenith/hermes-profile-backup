# MWIToken Conflict: Multiple Hermes Gateways Sharing Bot Tokens

## Symptom

Two Hermes gateway processes (different profiles) try to use the **same** Telegram/Discord bot token. Telegram rejects the duplicate `getUpdates` request, so the second gateway never connects — and because Telegram's polling is exclusive, the messages that arrive are routed to whichever gateway holds the token first. Result: user messages silently dropped or answered by the wrong agent.

## Evidence from this session (2026-08-17)

**Two gateways active on the same box:**

| PID | Profile | Telegram token | Discord token | Status |
|-----|---------|----------------|---------------|--------|
| 1899306 | `default` | `8600384515:***` (Alex Hormozi bot) | `MTQ3NjAx...` | ✓ Connected, answering Telegram |
| 2308552 | `alex-hormozi` | `8236061962:***` (Hermes Agent 101 bot) | `MTQ3NjAx...` (SAME) | ✗ Fails: "token already in use (PID 1899306)" |

**Log excerpt** (`/root/.hermes/logs/gateway-restart.log`):

```
2026-08-17 10:03:28,639 INFO gateway.run: Starting Hermes Gateway...
2026-08-17 10:03:28,699 ERROR gateway.platforms.base: [Discord] Discord bot token already in use (PID 1899306). Stop the other gateway first.
2026-08-17 10:03:28,756 ERROR gateway.platforms.base: [Telegram] Telegram bot token already in use (PID 1899306). Stop the other gateway first.
2026-08-17 10:03:28,767 WARNING gateway.run: Gateway started with no connected platforms — 2 platform(s) queued for retry
2026-08-17 10:03:58,850 ERROR gateway.platforms.base: [Discord] Discord bot token already in use (PID 1899306). Stop the other gateway first.
2026-08-17 10:03:58,901 ERROR gateway.platforms.base: [Telegram] Telegram bot token already in use (PID 1899306). Stop the other gateway first.
```

**Root cause:** The `alex-hormozi` profile's `gateway run` was started while the `default` profile's systemd service (`hermes-gateway.service`, PID 1899306) was already polling the same tokens. Both profiles had `DISCORD_BOT_TOKEN` set to the identical value in their `.env` files. Telegram's polling is exclusive — only one process can hold the offset at a time.

## How to diagnose

1. `hermes gateway status` — shows all running gateways and their PIDs.
2. `ps -eo pid,cmd | grep -i hermes` — find every `gateway run` / `gateway restart` process.
3. Compare tokens across profiles:
   - `grep TELEGRAM_BOT_TOKEN <profile>/.env`
   - `grep DISCORD_BOT_TOKEN <profile>/.env`
4. Verify which bot each token belongs to (read-only, no auth needed):
   - `curl -s "https://api.telegram.org/bot<TOKEN>/getMe"` → returns bot `id`, `first_name`, `username`
   - `curl -s "https://discord.com/api/v10/users/@me"` with `Authorization: Bot <TOKEN>` → returns bot identity
5. Check the gateway log for the collision signature: `"bot token already in use (PID <N>). Stop the other gateway first."`

## How to fix

1. **Decide which profile owns each bot.** If the user says "use bot X" (`8600384515:***`), that bot belongs to the profile that has it configured — in this case the `default` profile, not `alex-hormozi`.
2. **Stop the competing gateway.** If the `alex-hormozi` profile was started manually (`hermes -p alex-hormozi gateway restart`) and is not needed, kill it:
   - `kill 2308552` (or `pkill -f "hermes_cli.main -p alex-hormozi"`)
   - Do NOT use `systemctl --user restart hermes-gateway` from a session that is itself a child of the gateway (see the restart guard in the main SKILL.md).
3. **If both profiles are genuinely needed, give each its own bot tokens** — do not share tokens across profiles. Register a second bot via @BotFather and set `TELEGRAM_BOT_TOKEN` / `DISCORD_BOT_TOKEN` uniquely in each profile's `.env`.
4. Verify the surviving gateway is connected: `grep -iE "Connected to Telegram|✓ telegram connected" <profile>/logs/gateway.log | tail`.

## Pitfalls

- **Telegram polling is exclusive.** Two gateways with the same token never both work — one silently starves the other.
- **Discord tokens are also exclusive.** A duplicate Discord token produces the same "already in use" error.
- **A `gateway restart` that fails to connect keeps retrying forever** (reconnect watcher, exponential backoff 60s → 120s → 240s…). It logs noise but never recovers on its own — you must kill it or fix the token.
- **`hermes gateway status` lists PIDs for all profiles**, not just the current one. Always check `ps` too — the status output can mask a zombie restart process.
- **Don't assume the current session's profile is the one answering Telegram.** Messages may be handled by a different profile's gateway. Match the bot token the user references to the profile that owns it.