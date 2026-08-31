# Composio Morning Briefing Migration (google-workspace → Composio)

Session: 2026-08-31 — Morning briefing cron `3c98da2d9134` (`0 7 * * *`, `deliver: origin`, `skills: [google-workspace]`) stuck `blocked_config` for 4 days.

## Symptom
- `cronjob list` → `last_status: blocked_config`, `last_run_at: 2026-08-31T07:00:06+02:00`
- `~/.hermes/cron/output/3c98da2d9134/*.md` → `Status: BLOCKED (configuration)` / `Reason: attached skill 'google-workspace' is not ready: missing credential file google_token.json, credential file google_client_secret.json`
- User reports: "haven't got Cron from it in telegram" — no message despite daily schedule.

## Root causes (two independent)
1. **Skill gate blocks execution**: `google-workspace` requires `~/.hermes/google_token.json` + `google_client_secret.json`. Preflight (`cron.preflight: true`) prevents the agent from running; output repeats daily without re-alerting.
2. **Silent deliver**: `jobs.json` had `deliver: "origin"` with `origin: null` — even a successful run would deliver nowhere. User expected Telegram DM `telegram:6898985502`.

## Verification commands
```bash
~/.composio/composio --version  # expect 0.3.x binary, not pip 0.7.21
~/.composio/composio whoami  # {"email":"phemelop25@gmail.com", ...}
~/.composio/composio connections list  # gmail: ACTIVE (gmail_sioux-azox), googlecalendar: missing
~/.composio/composio connections list --toolkit gmail
~/.composio/composio connections list --toolkit googlecalendar  # {} in this session
# Dry-run validates schema only — can succeed without a real connection:
~/.composio/composio execute GOOGLECALENDAR_EVENTS_LIST --dry-run -d '{"calendarId":"primary","timeMin":"2026-08-31T00:00:00Z","timeMax":"2026-08-31T23:59:59Z","singleEvents":true}'
~/.composio/composio execute GMAIL_FETCH_EMAILS --dry-run -d '{"max_results":5,"query":"is:unread"}'
# Real execute — gmail works, calendar fails without link:
~/.composio/composio execute GMAIL_FETCH_EMAILS -d '{"max_results":2,"query":"is:unread"}'  # storedInFile=true
~/.composio/composio execute GOOGLECALENDAR_EVENTS_LIST -d '{"calendarId":"primary","timeMin":"2026-08-31T00:00:00Z","timeMax":"2026-08-31T23:59:59Z","singleEvents":true,"maxResults":5}'
# → {"successful": false, "error": "No active connection found for toolkit \"googlecalendar\"..."}
```

## Fix recipe
```bash
# 1. Create calendar link (headless-safe):
~/.composio/composio link googlecalendar --no-wait
# → {"redirect_url":"https://connect.composio.dev/link/lk_RSArKGbvTHDK","connected_account_id":"ca_JRFscrQ3CKRw"}
# User opens redirect_url → authorizes → verify:
~/.composio/composio connections list --toolkit googlecalendar  # expect status ACTIVE

# 2. Migrate cron off google-workspace (clears blocked_config):
hermes cron edit 3c98da2d9134 --remove-skills google-workspace
# OR full update via cronjob tool: patch jobs.json skills=[], update prompt to:
# "Use composio execute GMAIL_FETCH_EMAILS (max_results 10, query is:unread/newer_than:1d) and
#  GOOGLECALENDAR_EVENTS_LIST (calendarId primary, timeMin/timeMax today, singleEvents true).
#  Keep brief short/scannable per daily-brief.md logic. Deliver via telegram:6898985502"

# 3. Fix deliver:
hermes cron edit 3c98da2d9134 --deliver telegram:6898985502

# 4. Test:
hermes cron run 3c98da2d9134   # forces one fire on next tick
# Check ~/.hermes/cron/output/3c98da2d9134/<timestamp>.md and Telegram DM
```

## Job record after fix (intended)
- `skills: []` (no preflight blocker)
- `deliver: telegram:6898985502`
- `prompt` explicitly mentions Composio tool slugs so the agent knows to use terminal's `composio execute`.

## Pitfalls captured
- Gmail ACTIVE ≠ Calendar connected. Always check both toolkits separately.
- `--dry-run` success ≠ real connection. Always do a real `execute` smoke test before declaring "Composio works."
- `composio link <app>` without `--no-wait` hangs on headless VPS. Use `--no-wait` + send `redirect_url` to user.
- `deliver: origin` is only meaningful when `origin` was captured at creation (e.g., telegram DM). For persistent briefs, use explicit `telegram:<id>`.
