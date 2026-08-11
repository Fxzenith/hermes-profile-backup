# Webshare free proxies via their API key

When the user hands you a **Webshare API key** (`Authorization: Token <key>`) instead of
copy-pasting proxy endpoints, you can fetch and test all their free proxies yourself — no
manual dashboard copy needed.

## List proxies (correct call — the list endpoint REQUIRES `?mode=direct`)

```bash
curl -s -H "Authorization: Token $KEY" \
  "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page_size=20"
```
- Omitting `mode=direct` returns `{"mode":[{"message":"This field is required."}]}`.
- Each row carries `proxy_address`, `port`, `username`, `password`, `country_code`,
  `city_name`, `asn_name`, `valid`. The free tier typically supplies 10 mixed-geo proxies
  (US/GB/ES/PL/JP). `proxy/<id>/` and `proxy/detail/` single-record endpoints 404; use the list.

## Test each proxy's egress IP + a probe

```bash
IP=$(curl -s --max-time 20 -x "$PROXY" https://api.ipify.org)   # confirms the proxy egress
```

## Picking a proxy for X/Twitter

Prefer **US or UK** proxies for X (least likely to geo-trigger). But note the critical lesson
from the session record: for X *search*, egress IP often does NOT matter. The classic
"feed/reads work, search 404s" failure is the **twitter-cli ClientTransaction tool bug** (missing
`x-client-transaction-id` header), not geo and not account-trust — so EVERY proxy returns the
identical 404/empty-200. Rule of thumb: if a proxy gives a byte-identical response to the
no-proxy attempt, a proxy is not the lever (check the `Failed to init ClientTransaction`
warning — see `twitter-search-clienttransaction.md`). Free-tier Webshare proxies are also
shared/heavily-used and may already be flagged; cheap to test, not to rely on.

## Wiring it into Agent Reach

Store the chosen endpoint once (hidden, via stdin) so the agent can export it as
HTTP(S)_PROXY for upstream tools:
```bash
printf 'http://USER:PASS@host:port' | agent-reach configure proxy --stdin
```
`configure proxy` stores under the `proxy` key in `~/.agent-reach/config.yaml`; nothing reads
it automatically — the agent must `export HTTP_PROXY/HTTPS_PROXY` before invoking twitter-cli
or rdt-cli.