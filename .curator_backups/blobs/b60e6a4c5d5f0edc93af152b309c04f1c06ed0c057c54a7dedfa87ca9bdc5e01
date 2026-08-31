# Self-healing cron pattern for Composio-driven automations

A battle-tested layered design that makes an unattended cron post recover from breakage
and keep running instead of dying at the first error. Built while making an Instagram
auto-poster resilient; the shape generalizes to ANY scheduled tool call (posting, email,
tweeting, webhook-fetch).

## Pipeline-specific preferences for this user's IG auto-poster

- **Black background ONLY.** Never use the light theme. In `cron_post.py`'s
  `build_post_config`, force `config["theme"] = "dark"` — do NOT read it from the template
  (`template.get("theme")` leaks "light" for 2 of the 4 built-in templates). A template
  declaring `"light"` must still render pure-black (`#000000`) posts. The dark theme's
  `bg` is `#000000`; verify at the pixel level if in doubt.
- **One image per run.** The pipeline emits exactly one `post.png` per trigger (config has
  a single post / single tweet); it posts as one single-image post, never a carousel.

## Why the agent prompt alone isn't enough

A prompt that says "if it fails, fix it" gives the LLM cron agent no structured state and
no primitives to act on. The durable-learnings live in the SCRIPT layer; the cron agent
gets a tight loop to drive. Three layers, each with a distinct job:

## Layer 1 — pre-flight health gate (`scripts/self_heal.py`)

Runs BEFORE the action and AFTER a failed run. Pure detection, no side effects. Emits a
structured JSON report + a tri-state exit code the driver can branch on:

| exit | meaning | driver action |
|---|---|---|
| `0` | healthy, safe to proceed | run the action |
| `2` | degraded — connection present but primary not ACTIVE | switch to a live alternate account if any, else skip + escalate |
| `3` | fatal — CLI broken / not logged in | attempt repair (reinstall binary), else escalate |

Checks to implement (Instagram/Composio specifics here, generalize the pattern):
- binary exists (`~/.composio/composio`), `whoami` returns a session
- `connections list` parses as JSON
- exactly which connected account `word_id` is `ACTIVE` vs `EXPIRED`/`INITIALIZING`
  (multiple accounts for one toolkit is common — stale ones go INITIALIZING then EXPIRED)

## Layer 2 — retry-with-backoff wrapper in the action script

The posting script itself must retry TRANSIENT failures and fast-fail PERMANENT ones.
Don't hand-roll cooldowns for API-inherent waits the tool already handles.

Transient (RETRY, backoff 8×attempt): rate-limit code **9**, publish-too-soon **9007**,
"too many actions", network blips.
Permanent (NO retry — wasted calls): `OAuthException`, "access token", "permission",
"reauthenticate", "invalid_scopes", code `3600`.

```python
def _retryable(parsed) -> bool:
    blob = json.dumps(parsed).lower()
    if "too many actions" in blob or "9007" in blob or "rate limit" in blob:
        return True
    return not any(s in blob for s in ("permission", "auth", "login",
                                       "reauthenticate", "invalid_scopes", "access token"))
```

Never re-implement a readiness wait the tool already does: the Instagram PUBLISH tool
polls with `max_wait_seconds`/`poll_interval_seconds` — leave them on, never `0`.

## Optional Layer 4 — notify the posted artifact (proof of life)

After a successful publish, send the actual produced artifact to the user's chat so a
headless cron visibly proves it ran. Bake it into the ACTION script (non-fatal), not the
agent prompt — the script always does it; don't rely on the LLM remembering. For Telegram:

- Bot token lives in `/root/.hermes/.env` as `TELEGRAM_BOT_TOKEN`; the target chat id is in
  `/root/.hermes/config.yaml` under `home_channel: telegram:<id>`. Read both at runtime.
- `POST https://api.telegram.org/bot<TOKEN>/sendPhoto` with `chat_id`, `caption`, and the
  local file as `photo`. Use the same tolerant JSON parse on the response.
- Fetch the IG permalink AFTER publishing via `INSTAGRAM_GET_IG_USER_MEDIA` and include it
  in the caption (data is under `data.data[0].permalink`; and may be `storedInFile` — see
  the instagram-posting reference).
- Wrap the notify in its own try/except and log WARN on failure — a dead Telegram must not
  fail the post itself.

## Layer 3 — cron agent loop (the "fix and continue" brain)

The cron prompt drives the run:
1. run `self_heal.py` → branch on exit code.
2. run the action script → on failure, read the log, DIAGNOSE, REPAIR (reinstall deps /
   rerun install-fonts / switch account / genuine rerun — the script re-picks a fresh
   template each time), then retry at least once.
3. VERIFY independently — don't trust the script's own success message. Fetch state
   (e.g. `INSTAGRAM_GET_IG_USER_MEDIA`) and confirm the new item + timestamp + caption
   actually landed.
4. ESCALATE to the user ONLY for permanent failures (auth expired → they must open a fresh
   `composio link <app> --no-wait` URL; CLI uninstallable; 3 consecutive full failures).
5. NEVER double-post — before a 2nd attempt, check whether the item already went live for
   today's template.

## Anti-patterns
- `rfind("{")` to parse `execute` output (banner braces) — walk `{`-suffixes instead.
- Manual `time.sleep` cooldowns duplicating the tool's own `max_wait_seconds` polling.
- Letting the LLM cron agent "improvise" recovery with no script primitives (no health
  report, no retry wrapper) — it has no structured signal to branch on.
- Treating every failure as permanent (spins on rate-limits) OR as transient
  (beats a dead horse on token expiry).