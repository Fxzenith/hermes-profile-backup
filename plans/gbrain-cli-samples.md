# GBrain CLI Output Samples (pinned for gbrain-provider parser)

Captured against gbrain 0.42.59.0 (PGLite, cwd `/root/gbrain`, bin `/root/.bun/bin/gbrain`).

## gbrain query <q> --limit N --detail <low|medium|high>
Text output (no --json). Example for query `hermes memory extension`:
```
[1.2298] inbox/2026-08-11-b932c245 -- # Test note for Hermes memory extension: favorite color is teal

Test note for Hermes memory extensi
```
- Format per hit: `[score] <slug> -- <title>` then a blank line and a text excerpt.
- First stdout line is `UPGRADE_AVAILABLE ...` on stderr? No — it appears on stderr mixed into 2>&1 here. In subprocess with `capture_output=True` it lands in `stderr`; `stdout` is clean hits only. Verify: the code uses text mode; we'll strip any `UPGRADE_AVAILABLE` lines defensively.
- No `--json` flag on `query` (not in --help). Use text parsing.

## gbrain search <q> --limit N --detail <low|medium|high>
Same text shape `[score] slug -- title`. ALSO supports `--json` (confirmed). JSON shape tbd — text form is sufficient for v1.

## gbrain salience --days N --limit N
Table text:
```
#   score   emo   takes   slug — title
--------------------------------------
1   0.517   0.00  0       yt_callaway_personal_brand_formula — Video: The Personal Brand Formula (Callaway)
2   0.198   0.00  0       inbox/2026-08-07-a250b135 — Skill verification test note
```
- Lines start with `N   <float>`. Skip header rows (`#`, `---`, and the column-header line). Slug field is unquoted; title after ` — `.

## gbrain capture --stdin --quiet [--json]
- Without --json: stdout `captured:\n  slug:          inbox/2026-08-11-b932c245\n  status:        created_or_updated\n  content_hash:  ...`
- With --json: `{"slug":"inbox/...","status":"created_or_updated","chunks":1,"content_hash":"..."}`. Parse `--json`, field `slug`.

## Parser strategy (finalized)
- query/search: regex `^[[\d+\.\]]+\]\s+(.+)\s*--\s*(.+)$` capture slug + title; excerpt follows in trailing lines (optional context). Dedupe by slug.
- capture: use `--json`, parse first JSON line, read `slug`.
- All commands: subprocess env PATH includes `~/.bun/bin`; cwd `/root/gbrain`. 25s timeout default.
