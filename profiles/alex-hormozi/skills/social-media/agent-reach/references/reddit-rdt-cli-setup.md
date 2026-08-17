# Reddit via rdt-cli — cookie credential setup (server, no browser)

Headless-server Reddit access for Agent Reach uses `rdt-cli` as the backend. There is **no
anonymous path** (Reddit's `.json` endpoints are anti-bot blocked, official API needs manual
approval). You need a logged-in `reddit_session` cookie the user exports from their browser —
same Cookie-Editor flow, but the config shape is completely different from Twitter's (below).

## Install (Agent Reach documented / pinned source)

```bash
pipx install 'git+https://github.com/public-clis/rdt-cli.git@5e4fb3720d5c174e976cd425ccc3b879d52cac66'
# -> installs `rdt` v0.4.2 globally (PyPI's 0.4.1 is behind; pin this git sha)
```

Note: pipx may install under `/root/.local/bin/rdt` and it is NOT in a venv that the
`~/.agent-reach-venv` agent runs from — reference it by absolute path in scripts.

## Write the credential (do this so reads actually work)

`rdt` reads its auth from `~/.config/rdt-cli/credential.json`. This file must EXIST at
`~/.config/rdt-cli/`; it is not auto-created. Shape:

```bash
mkdir -p /root/.config/rdt-cli
cat > /root/.config/rdt-cli/credential.json <<EOF
{"cookies":{"reddit_session":"<REDDIT_SESSION_COOKIE_VALUE>"},"source":"manual","username":"","modhash":null,"saved_at":$(date +%s),"last_verified_at":null}
EOF
```

The user pastes a cookie JSON dump; pluck the JWT value of the cookie named **`reddit_session`**
only (ignore `token_v2`, `reddit_session`+`csrf_token`, `loid`, etc.). It is a long base64url
JWT (~700+ chars). Use `python3` (NOT `/root/.local/bin/python3`, which doesn't exist) to
validate the JSON and report the value length after writing.

## Verify — two commands, and a subtle ID gotcha

```bash
rdt status    # -> authenticated: true, capabilities: read+write, username shown
rdt search "openai" -n 3   # -> real t3 results; proves reads work end-to-end
```

**ID gotcha that causes a false "not_found":** `rdt read` takes the **short post ID**
(`1v49v7c`), NOT the `t3_`-prefixed fullname. Passing `t3_1v49v7c` returns
`ok: false / code: not_found` even when auth and search are perfect.
```bash
rdt read 1v49v7c -n 30   # reads a post + comments; short ID only
```

## Delegation pitfall

If you hand the Reddit setup to a subagent, do NOT trust its "completed" summary alone.
In practice a subagent installed rdt-cli (pinned git install worked) but stopped before
(a) writing `credential.json` and (b) running a real read. Verify yourself, from scratch:
`which rdt`, credential file exists, `rdt status`, `rdt search`. Treat subagent installs as
done and credentials/verification as un-done until you confirm both.

## Geo note

Contrary to the blanket "Reddit needs a proxy" assumption: from the VPS in this session
(SAST-region datacenter IP `102.208.217.192`) Reddit read **worked without a proxy**,
while X search was geo-blocked on the same IP. Test Reddit directly before configuring a
proxy; do not preemptively buy one.