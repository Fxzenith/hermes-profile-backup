# Composio `execute` — file uploads & output parsing

Working techniques for driving `composio execute <SLUG>` from a script/cron, discovered
while wiring Instagram auto-posting. Applies to any Composio tool, not just Instagram.

## Passing a local file to a tool: `--file` vs `-d`

`composio execute <SLUG> --file <path>` injects a local file path into the tool's
*single* `file_uploadable` input. It **fails** when the tool has **more than one**
`file_uploadable` field:

```
💥 ToolExecutionError • Tool "INSTAGRAM_POST_IG_USER_MEDIA" has multiple
file_uploadable inputs (image_file, video_file). Pass the target field explicitly
with -d instead of --file.
```

Fix: pass the path **inside `-d`** using the exact field key. The CLI-facing schema
(`composio execute <SLUG> --get-schema`) marks each uploadable input as
`{"file_uploadable": true, "format": "path", "type": "string"}`. So:

```json
{ "ig_user_id": "28532466729677348", "caption": "...", "image_file": "/abs/path/post.png" }
```

The CLI uploads the local path to a temporary public URL before calling the API —
**no self-hosted image host required.**

## Verifying a call without firing a side effect

`composio execute <SLUG> --dry-run -d '{...}'` validates args + connection and echoes
the resolved `arguments` back, without executing. Cheap pre-flight before wiring a cron.

## Parsing `composio execute` stdout as JSON

Output is usually a clean JSON document, **but** error/banner paths prepend prose that
can itself contain braces (e.g. the `💥 ToolExecutionError • msg with {braces}` banner),
and success output may have trailing text. `raw.rfind("{")` is WRONG — it slices from the
first brace in the banner.

Robust parse: try the whole string, then every `{`-suffix in order; return the first that
`json.loads` fully accepts:

```python
def parse_execute_json(raw: str):
    candidates = [raw] + [raw[i:] for i in range(len(raw)) if raw[i] == "{"]
    for cand in candidates:
        try:
            return json.loads(cand)
        except (json.JSONDecodeError, ValueError):
            continue
    return None
```

## Instagram content publishing (Graph-API-backed tools)

Resolved account: type MEDIA_CREATOR, business ID is a long numeric string
(ex. `28532466729677348`), returned by `INSTAGRAM_GET_USER_INFO` (`id`), not the username.

Flow for a single image post (all under the `instagram` toolkit):

1. `INSTAGRAM_GET_USER_INFO` → `id` (the `ig_user_id` for later calls; `"me"` not accepted here).
2. (optional) `INSTAGRAM_GET_IG_USER_CONTENT_PUBLISHING_LIMIT` — usage comes back as a list under `response.data.data`.
3. `INSTAGRAM_POST_IG_USER_MEDIA` with `image_file` + `caption` → returns `data.id` = container id.
4. `INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH` with `creation_id` = container id → media id.

**Publish-time pitfalls baked into the tools:**
- `image_url` often fails validation/fetch (query params, share/view pages). Use `image_file`
  (local upload) — the robust route.
- Publishing too soon → error code **9007**; rapid retries → code **9** ("too many actions").
  The PUBLISH tool has built-in readiness polling: set `max_wait_seconds` (60–300) and
  `poll_interval_seconds` (1–30). **Never set `max_wait_seconds: 0`** — that skips status
  checks and triggers 9007. For a plain image, default 60s is plenty.
- Select the right connected account with `--account <word_id>` (e.g. `--account instagram_magog-daroo`)
  so you don't hit an unrelated INITIALIZING/EXPIRED account for the same toolkit.

## Cron-scheduling gotcha

Hermes cron scheduler evaluates `schedule` in the **machine local timezone**. This VPS is
`Africa/Johannesburg` (UTC+2), so "09:00 UTC" is schedule `0 11 * * *`. Check with `date`
+ `/etc/timezone` before translating a UTC intended time into a cron expr. Desktop/CLI cron
jobs silently "save only" unless `deliver` is set to a gateway channel (`telegram:-100...`);
set `deliver` to get a notification when a post goes through.