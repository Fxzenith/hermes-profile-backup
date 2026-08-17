# twitter-cli cookie debugging — ct0 corruption vs geo-block (session record)

Real debugging path from a headless-server Agent-Reach setup. This is the reference for
distinguishing "cookie corrupted" from "IP blocked" when X reads fail.

## Symptom sequence observed

1. `twitter status` → `authenticated: true` (auth token valid, user returned). 
   → This ONLY proves the auth token works. It does NOT prove read endpoints work.
2. `twitter search "query"` → **HTTP 404** with an empty message.
   - First pass misread this as an auth/geo problem and went down a proxy rabbit hole (wasted effort in later sessions — see the correction below).
3. `twitter feed -n 3` → **HTTP 403, error code 353**:
   `{"errors":[{"code":353,"message":"This request requires a matching csrf cookie and header."}]}`
   - This is the smoking gun for a **`ct0` mismatch**, not a geo block. X matches the
     `ct0` cookie value against the `X-Csrf-Token:` header AND against the server-side
     session that `auth_token` is bound to.
4. Root cause found: the pasted `ct0` (160 chars) had been **corrupted in transit** — a
   single character flipped (`721c3d8` → `721c3c8`, position 16) plus an initial truncation.
   Fixing it made the 403 disappear.
5. After fixing `ct0`: `feed`, `show`, `likes`, `user-posts` all worked and returned real
   tweets, but `search` STILL 404'd with `Failed to init ClientTransaction: 'NoneType'`
   present on every run. See `twitter-search-clienttransaction.md` for the real cause — this
   is the known twitter-cli tool bug, not account-trust (see the section below).

## Diagnostic table

| `status` | timeline/reads | `search` | Cause | Fix |
|---|---|---|---|---|
| ok | ok | **404 empty / REST bare 200 (0 bytes), + `Failed to init ClientTransaction` warning** | **twitter-cli ClientTransaction bug** — missing `x-client-transaction-id` header that SearchTimeline requires | none client-side; needs a twitter-cli maintainer patch. Proxy/older-account/queryId do NOT help (see `twitter-search-clienttransaction.md`) |
| ok | ok | **404 empty / REST bare 200 (0 bytes), NO ClientTransaction warning** | X **account-trust gate** on search (less common) | use a higher-activity X account, or warm the account up in a real browser; a proxy does NOT help |
| ok | **403 code 353** | — | `ct0` corrupted / stale / mismatch | byte-verify `ct0` against original paste, fix, retest |
| fail | — | — | auth_token invalid/expired | re-export fresh cookies |

`twitter status` works even when reads are broken — never use it as the only health check.

## The account-trust correction, superseded (session record, 2026-08)

An earlier revision concluded the residual `search` 404 was an X **account-trust gate**
(not IP, not tooling) and recommended warming up the account or using an older one. That
attribution was **also wrong** — superseded by a deeper investigation. The real root cause
is a **known, open tool bug** in twitter-cli v0.8.5; see `twitter-search-clienttransaction.md`.

Important: the "decisive discriminator" once recorded here is **not** a reliable
account-trust test and should not be repeated as one. The REST search probe returns a bare
`200` with `size_download=0` for a different, more common reason: **X requires the
`x-client-transaction-id` header on the search surface, and the twitter-cli tool fails to
emit it.** A 0-byte REST body / GraphQL 404 on search therefore means "the search surface
rejected the request" — which is consistent with BOTH account-trust AND the missing
client-transaction header. Treat it as a signal to check the tool, not as proof of account
gating. Account trust *can* separately gate search for very-new/quiet accounts, but it is
NOT the first-line explanation when the `Failed to init ClientTransaction` warning is
present.

Diagnostic order for feed/show/likes/user-posts OK + search 404:
1. Check for `WARNING twitter_cli.client: Failed to init ClientTransaction: 'NoneType'...`
   → present = the known ClientTransaction bug; search is a lost cause until maintainer fix.
2. Otherwise, and only as residual hypothesis, consider account-trust (assess `createdAt`,
   tweet/follower counts from `twitter status`).

## How twitter-cli sends auth (why a single bad char breaks reads)

twitter-cli sends the **same `ct0` string** as both the `Cookie:` header value and the
`X-Csrf-Token:` header (source: `twitter_cli/client.py` build_headers). A self-mismatch is
impossible; the failure is X rejecting the `ct0` as not matching the session the
`auth_token` belongs to.

## The byte-verify fix (do this BEFORE blaming the IP)

Mid-length tokens are fragile. After storing any pasted credential, diff the stored value
against the user's original **character by character**, not by grep-eyeball:

```bash
STORED=$(python3 -c "import re,pathlib;s=pathlib.Path.home().joinpath('.agent-reach','config.yaml').read_text();print(re.search(r'twitter_ct0:\s*[\"']?([^\"'\n]+)',s).group(1))")
printf 'stored: %s\n' "${STORED:0:40}"
printf 'yours : %s\n' "<first-40-characters-of-the-original-paste>"
# then a char-level diff loop over the full length:
Y="<full-original-paste>"
for i in $(seq 0 $((${#STORED}-1))); do
  [ "${STORED:$i:1}" = "${Y:$i:1}" ] || echo "DIFF@$i stored=${STORED:$i:1} yours=${Y:$i:1}"
done
```

Rewrite stored config + shell env with the exact corrected value, re-test.

## Notes
- Cookie-Editor "Export → Header String" is the clean path. Pluck only `auth_token` + `ct0`
  (X needs exactly these two); ignore the ads/analytics/reseller cookies in the dump.
- Cookie-based X automation from a datacenter IP is a **ban risk** — recommend the user use
  a secondary account, and set things up so a burner can be swapped in without redoing config.
- If distance from conversion is not the issue: X rotates `ct0` frequently; a stale exported
  `ct0` is fixed by a fresh export from a live logged-in tab.