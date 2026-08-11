# Hacker News top-stories recipe via Composio (verified live Aug 2026)

Goal: list the top/trending HN stories using the Composio CLI, without any OAuth account.

## Tools

| Slug | Input | Output |
|---|---|---|
| `HACKERNEWS_GET_TOP_STORIES` | `{"print":"pretty"}` | `data.count` (500) + `data.story_ids[]` (rank-ordered list) |
| `HACKERNEWS_GET_ITEM` | `{"id": <int>}` | full item: `title`, `url`, `score`, `descendants`, `by`, `time`, `type` |

Both need no auth. `HACKERNEWS_GET_STORY` and `HACKERNEWS_SEARCH_STORIES` do NOT exist — probing them fails, don't retry.

## Discovery path (important)

`composio search "hacker news"` / `"hackernews top stories"` / `"get top headlines stories from hacker news website"`
all return ONLY the generic `composio_search` toolkit use-cases (`COMPOSIO_SEARCH_NEWS`, `COMPOSIO_SEARCH_FETCH_URL_CONTENT`, `COMPOSIO_SEARCH_TRENDS`, `COMPOSIO_SEARCH_WEB`) — never the `HACKERNEWS_*` tools. Semantic search does not cover this app.

The way in is slug probing:

```bash
composio execute HACKERNEWS_GET_TOP_STORIES --dry-run -d '{}'
# {"successful": true, "dryRun": true, "slug": "HACKERNEWS_GET_TOP_STORIES", "schemaPath": "/root/.composio/tool_definitions/HACKERNEWS_GET_TOP_STORIES.json", ...}
```

A successful dry-run validates the connection AND caches the schema into `~/.composio/tool_definitions/<SLUG>.json` (list that dir to enumerate discovered tools).

`composio link hackernews --no-wait --no-browser` exits 0 with NO output at all and creates no `hackernews` connection (`composio connections list` stays github/instagram/gmail). It's a silent no-op — HN works without linking anything, via a server-side `consumer-*` userId.

## Loop: top IDs → details

Pull the ID list, then one GET_ITEM per ID. In practice (~0.4s sleep between calls): 15 items ≈ 100s wall time. Keep loops to a subset (top 10–15), not all 500.

```python
import json, subprocess, time

top_ids = json.loads(subprocess.run(
    ["/root/.composio/composio", "execute", "HACKERNEWS_GET_TOP_STORIES", "-d", '{"print":"pretty"}'],
    capture_output=True, text=True, timeout=60).stdout.split('{', 1)[1].rsplit('}', 1)[0].join(['{','}']))  # or: parse from first '{'
```

Simpler robust parse (banner prose can precede the JSON):

```python
out = subprocess.run([...]).stdout
d = json.loads(out[out.find('{'):])
stories = d['data']['story_ids']  # 500 rank-ordered IDs
```

Then per ID:

```python
for sid in stories[:10]:
    r = subprocess.run(["/root/.composio/composio", "execute", "HACKERNEWS_GET_ITEM", "-d", json.dumps({"id": sid})],
                       capture_output=True, text=True, timeout=60)
    item = json.loads(r.stdout[r.stdout.find('{'):])['data']
    print(item['score'], item['title'], item['url'], item['by'], item['descendants'])
    time.sleep(0.4)
```

## Output notes

- Score/points live in `score`; comment count in `descendants`. `url` is the external link; for self-posts use `https://news.ycombinator.com/item?id=<id>`.
- `story_ids` is the live front-page ranking at fetch time — a fast-moving new story can sit top-5 with few points; don't assume points == rank.
- The `execute` stdout in this session was clean JSON (no banner), but the first-`{` walk is the safe habit.