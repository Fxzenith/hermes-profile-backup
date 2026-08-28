# Composio Instagram Tool Pitfalls — Error Transcripts

Captured 2026-08-28 while auditing @ze.nith001.

## 1. `INSTAGRAM_GET_IG_MEDIA` default fields → 400

Default schema `fields` includes `total_views_count, view_count, reposts_count, saved_count, shares_count ...` which are NOT supported on Media node via Instagram Login toolkit.

**Request (default):**
```
INSTAGRAM_GET_IG_MEDIA --account instagram_magog-daroo -d '{"ig_media_id":"18224025895327139"}'
# internally sends fields=id,caption,...,total_views_count
```

**Error:**
```
400 {"message":"Instagram API Error: Tried accessing nonexisting field (total_views_count). This field is not supported on the Media node. Supported fields are: id, caption, comments_count, is_comment_enabled, like_count, media_type, media_url, media_product_type, owner, permalink, shortcode, thumbnail_url, timestamp, username, children, comments.","status_code":400}
```

**Fix:** Always override with explicit allowlist:
```
-d '{"ig_media_id":"<id>","fields":"id,caption,like_count,comments_count,media_type,media_product_type,permalink,timestamp,thumbnail_url,username,shortcode"}'
```

## 2. `INSTAGRAM_GET_USER_INSIGHTS` string timestamps → validation error

```
INSTAGRAM_GET_USER_INSIGHTS -d '{"since":"2026-08-14","until":"2026-08-28","metric":["reach"]}'
→ {"successful":false,"error":"Instance type \"string\" is invalid. Expected \"integer\"."}
```

**Fix:** Pass Unix seconds:
```python
from datetime import datetime
since=int(datetime(2026,8,14).timestamp())  # 1786658400
until=int(datetime(2026,8,28).timestamp())  # 1787868000
```

Only `reach` reliably returns values; other metrics (`views`, `likes`) are silently omitted when no data, with a `composio_execution_message` explaining missing metrics — not an error.

## 3. `storedInFile` large payload

```
{"successful":true,"storedInFile":true,"tokenCount":22125,"outputFilePath":"/tmp/composio/adhoc_ad4c42e78294/INSTAGRAM_GET_IG_USER_MEDIA_OUTPUT_dc6fddf3.json"}
```

Read `outputFilePath`; `data.data` is double-nested (`data: {data: [...]}`) plus `paging`.

## 4. `GET_IG_USER_MEDIA` listing null counts

Listing returns `like_count: null, comments_count: null` for every item — counts only appear after per-media hydrate via `GET_IG_MEDIA`.

## 5. Self vs organic comments

Every post auto-adds one self-comment (`from.id=="17841416058149055"` / `username=="ze.nith001"`). Organic signal is a different `from.username` (e.g., `mindset__community`, `mindfulness._.communityy`, `mindset_journeyy`). Check `from.username` before counting engagement. Example with both:

```json
{"from":{"username":"mindset__community"},"text":"Send me this post"},
{"from":{"username":"ze.nith001"},"text":"That's the one 🎯 ..."}
```

## 6. Placeholder `.env` tokens

`/root/projects/Instagram daily auto-post/.env` contains `INSTAGRAM_ACCESS_TOKEN=your_instagram_business_account_id_here` etc. Direct `curl https://graph.facebook.com/v21.0/<id>/insights?access_token=<that>` → `OAuthException 190 Invalid OAuth access token`. Use Composio account instead.
