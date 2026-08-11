# Posting to Instagram via `composio execute` (single-image)

Verified working end-to-end against a real Instagram Creator account. Covers the
Content-Publishing API flow through Composio, the file-upload pitfall, error-code
handling, and connection health checks.

## Accounts & connections

- `composio connections list` returns JSON: `{ "<toolkit>": [{status, word_id, permission_group}, ...] }`
- `composio connections list --toolkit instagram` narrows to one app.
- An ACTIVE connection is what you anchor `--account <word_id>` to. Stale
  `INITIALIZING` entries from repeated connect-link flows eventually flip to
  `EXPIRED` — ignore all but ACTIVE.
- `composio execute INSTAGRAM_GET_USER_INFO --account <wd> -d '{}'` resolves the
  publishable account: returns `id` (the numeric IG_BUSINESS_ACCOUNT_ID), plus
  username, account_type, followers. Use the returned `id` as `ig_user_id` for
  all subsequent calls (or `"me"`).

## The single-image post flow (two calls)

```bash
# 1. Create a media container (uploads + captions; NOT yet live)
composio execute INSTAGRAM_POST_IG_USER_MEDIA \
  --account <word_id> \
  -d '{"ig_user_id":"<IG_BUSINESS_ACCOUNT_ID>","caption":"...","image_file":"/absolute/path/post.png"}'
# -> response.data.id is the container id

# 2. Publish it (goes live)
composio execute INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH \
  --account <word_id> \
  -d '{"ig_user_id":"<ID>","creation_id":"<container_id>","max_wait_seconds":120,"poll_interval_seconds":5}'
```

Verify independently afterward:
`composio execute INSTAGRAM_GET_IG_USER_MEDIA --account <wd> -d '{"ig_user_id":"<ID>"}'`
and check the newest item's `id` + `permalink` + timestamp. Never trust only the
publish call's success flag.

## Pitfalls

### Multiple file-uploadable inputs break `--file`
`INSTAGRAM_POST_IG_USER_MEDIA` has TWO file_uploadable fields (`image_file` AND
`video_file`). `composio execute --file <path>` then errors:

> Tool "... has multiple file_uploadable inputs (image_file, video_file). Pass the target field explicitly with -d instead of --file."

Fix: put the path directly in `-d` as the named field, e.g.
`-d '{"image_file":"/abs/path.png", ...}'`. Check which fields are `file_uploadable`
with `composio execute <TOOL> --get-schema` (fields show `"file_uploadable": true, "format": "path"`).

### Large payloads come back as `storedInFile`, not inline
`INSTAGRAM_GET_IG_USER_MEDIA` returns a small envelope with
`"storedInFile": true` and an `"outputFilePath"` (e.g.
`/tmp/composio/adhoc_<id>/INSTAGRAM_GET_IG_USER_MEDIA_OUTPUT_<id>.json`); the real
`data.data[]` list lives in that file. When parsing execute output, if the response
has `storedInFile`, read `outputFilePath`. Data layout: `data.data[0].permalink/id/timestamp`.
The file path is under `/tmp` — parse it in the same invocation.

### Output parsing: tolerate a text banner
The CLI can prepend a banner or stack trace (which itself contains `{` braces)
before the JSON result. Do NOT `rfind("{")` (wrong brace). Instead try the raw
string, then walk every `{`-suffix and `json.loads` each until one forms complete
valid JSON.

### Error-code semantics (Instagram Graph API)
- **9007** — publish attempted before the container finished processing → transient, RETRY (wait).
- **code 9** — "too many actions" / rate limit → transient, RETRY with backoff.
- **Auth/permission strings** (`OAuthException`, `The access token has expired, reauthenticate`, `invalid_scopes`, `permission denied`) → PERMANENT, fast-fail; retrying wastes time.
- The PUBLISH tool's `max_wait_seconds` (default 60) + `poll_interval_seconds` already poll for FINISHED — never set `max_wait_seconds: 0` for images unless you know the container is ready. This is how you "wait for cooldown" without hand-rolling it.

### image_url vs image_file
`image_url` needs a clean, Meta-fetchable URL (query-param-riddles/`?` URLs fail validation). `image_file` avoids hosting entirely — Composio uploads the local file to a temporary public URL that Instagram fetches. Prefer `image_file` for on-disk assets.

### Publishable-account requirement
The IG user must be a Business/Creator account (MEDIA_CREATOR / BUSINESS); the 
Content-Publishing API does not work on personal accounts.

## Connection health check pattern (pre-flight)

```python
# subprocess: composio connections list --toolkit instagram
# parse JSON; primary word_id ACTIVE -> healthy; else try other ACTIVE; else re-auth
```
Exit-code convention used in a self-healing cron: 0 = healthy, 2 = present-but-warn
(post via alternate or skip), 3 = composio CLI broken (reinstall from https://composio.dev/install).
Re-auth is human-gated: `composio link instagram --no-wait` prints a
`connect.composio.dev/link/...` URL the user must open; the CLI can't re-auth itself.