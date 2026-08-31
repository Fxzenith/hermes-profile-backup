# Composio cross-account connected-account invisibility

## Symptom
User pastes a `ca_*` connected-account ID (or `ak_*` key) they created in the
Composio dashboard while logged in with a DIFFERENT Google account than the one
the CLI session is authenticated as. Every attempt to use it fails:

```
composio execute GOOGLESHEETS_CREATE_GOOGLE_SHEET1 --account ca_TJMyucDjeReh --dry-run -d '{...}'
💥 services/ConnectedAccountResolutionError • No connected account matched "ca_TJMyucDjeReh" for toolkit "googlesheets". No active connected accounts were found for that toolkit.
```

`composio connections list --toolkit googlesheets` shows only the accounts of the
CURRENT CLI identity — the pasted `ca_*` never appears.

## Why
The CLI session is bound to ONE Composio identity/org. Its key lives in
`~/.composio/user_data.json` (`"api_key": "uak_..."`). `--account` only resolves
connected accounts within that identity. A `ca_*` from another identity is simply
not in scope — it's not "broken", it's invisible.

`ca_*` = connected-account ID (wrong type to log in with).
`ak_*` = also NOT a `uak_` User API Key; passing it to `composio login --user-api-key`
returns `HTTP 401 Unauthorized`.

## Fix (to use the other account's connection)
1. Log into https://dashboard.composio.dev with the OTHER Google account.
2. Settings → API Keys → copy the key starting with `uak_`.
3. `composio login --user-api-key uak_xxxxx`
4. Now `composio connections list` shows that account's connections and
   `--account ca_...` resolves.

## Faster path (no key hunting)
If the sheet can live under the CLI's CURRENT account, just re-OAuth that account:
`composio link <app> --no-wait` → send the `redirect_url` → user approves →
poll `composio connections list --toolkit <app>` until `ACTIVE`.

## Expired connections
All `EXPIRED` connections are unusable (tool calls return
`ToolRouterV2_NoActiveConnection`). They cannot be silently refreshed — issue a
fresh `composio link` OAuth. A brand-new connection sometimes sits in
`INITIALIZING` for 1–3 min before flipping to `ACTIVE`; if it stays
`INITIALIZING` >~3 min, regenerate the link and re-authorize.
