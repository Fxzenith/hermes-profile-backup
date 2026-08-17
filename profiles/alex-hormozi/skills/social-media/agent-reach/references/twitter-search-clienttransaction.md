# twitter-cli search 404 — the ClientTransaction / x-client-transaction-id bug (session record)

Definitive root-cause investigation (2026-08) for the classic symptom:
`feed`/`show`/`likes`/`user-posts` all work, but `twitter search` returns **HTTP 404** (empty
message) on every request. **This is a known, open tool bug — NOT a geo/IP block and NOT an
account-trust gate.** A previous revision blamed account-trust; the deeper investigation
disproved that too.

## Mechanistic root cause

1. X redesigned its homepage. twitter-cli's `x_client_transaction/utils.py`
   `get_ondemand_file_url()` runs `ON_DEMAND_FILE_REGEX.search(str(response)).group(1)`; the
   new homepage no longer matches the regex, so `.search()` returns `None` and `.group(1)`
   raises **`'NoneType' object has no attribute 'group'`**.
2. This error is **caught** by twitter-cli's `_ensure_client_transaction()` (`client.py`
   ~1092) and only logged as a warning: `Failed to init ClientTransaction: 'NoneType'...`.
   So `self._client_transaction` stays `None`.
3. `_build_headers()` (~1127) only adds the **`X-Client-Transaction-Id`** header
   `if self._client_transaction and url`. With init failed, that header is never emitted.
4. **X's SearchTimeline (search) endpoint hard-requires a valid `x-client-transaction-id`
   header**; without it, X returns 404. HomeTimeline (feed), UserTweets (user-posts), TweetDetail
   (show), Likes currently tolerate the missing header, which is why reads work but search doesn't.

## Proof gathered

- **Identical 404 across 4 residential proxies** (US `31.56.127.193`, GB `31.59.20.176` &
  `45.38.107.97`, JP `142.111.67.146`) — so not egress-IP bound.
- **Fresh community SearchTimeline queryId** `Yw6L66Pw54NHKuq4Dp7b4Q` (from
  `fa0311/twitter-openapi` `placeholder.json`) patched into `FALLBACK_QUERY_IDS` → still 404
  (stale queryId was a red herring; the header is the real driver). Reverted the patch.
- **Raw curl_cffi request** with correct Chrome TLS fingerprint, fresh queryId, proper session
  cookies, WITHOUT the client-transaction header → 404. With python `urllib` → 404 (different
  TLS fingerprint, also no header). The common denominator is the missing header.
- **GitHub issues #73 and #78** in `public-clis/twitter-cli` — same exact symptom, same root
  cause analysis by reporters; both **OPEN with zero comments** (no fix yet). Also #69 (the
  warning itself) and #72 ("Twitter account got flagged as bot" — a separate concern).

## What does and does NOT fix it

| Attempt | Result |
|---|---|
| Residential proxy (multiple IPs) | ❌ 404 persists |
| Swap to fresh community queryId | ❌ 404 persists |
| Different account / account-trust explanation | ❌ not the cause here (the tool emits no header) |
| Patching `get_ondemand_file_url` to be non-fatal | ⚠️ not actually validated this session (did not complete a working ClientTransaction); requires the authenticated homepage + ondemand bundle anyway |
| Maintainer patch to twitter-cli | ✅ the only real fix (none shipped as of v0.8.5) |

The header can only be generated if ClientTransaction initializes, which needs BOTH the
`meta[name='twitter-site-verification']` key and ondemand-bundle indices parsed from a
**logged-in** x.com homepage (`get_key` + `get_indices` in
`x_client_transaction/transaction.py`). A headless server can't obtain that without a real
browser session, so this is not solvable by configuration.

## Diagnostic discriminator

When `feed`/`show`/`likes`/`user-posts` work but `search` 404s:
1. Look for `WARNING twitter_cli.client: Failed to init ClientTransaction: 'NoneType'...`
   on the **same run**. Present → the ClientTransaction bug; search is blocked until a
   maintainer fix. Stop there — do not chase proxies or blame the account.
2. Only if that warning is ABSENT (tool apparently healthy) consider account-trust gating as a
   residual hypothesis (assess `twitter status` `createdAt`, tweet/follower counts).

## Relevant code locations (twitter-cli v0.8.5)

- `twitter_cli/client.py`: `_ensure_client_transaction` (~1052), `_build_headers` (~1127, the
  `if self._client_transaction and url:` gate), `_load_ct_cache` (~1008) — the cache path that
  *would* init ClientTransaction without the failing fetch, but still needs authenticated
  home_html + ondemand_text.
- `x_client_transaction/utils.py`: `get_ondemand_file_url` (regex→`.group(1)` crash point).
- `x_client_transaction/transaction.py`: `get_key` (needs `meta[name=twitter-site-verification]`)
  and `get_indices` (needs ondemand bundle).
- `twitter_cli/graphql.py`: `SearchTimeline` fallback queryId + `_scan_bundles`/`_fetch_from_github`
  (the "live queryId" retry — also fails because the homepage fetched is the logged-out shell with
  no ondemand bundle).