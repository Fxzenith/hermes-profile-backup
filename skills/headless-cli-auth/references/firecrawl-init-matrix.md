# firecrawl init flag matrix

## Command
```
npx -y firecrawl-cli@latest init --all --browser
```

## Flags
| Flag | Effect |
|------|--------|
| `--all` | Install skills to all detected agents (codex, gemini-cli, opencode, hermes-agent) |
| `--browser` | Browser OAuth (recommended for agents) — hangs headless |
| `--skip-auth` | Skip authentication — install only |
| `--skip-install` | Skip global CLI install |
| `--skip-skills` | Skip skills installation |
| `-y, --yes` | Non-interactive |
| `-k, --api-key <key>` | Auth with key, skip browser |
| `-a, --agent <name>` | Install to specific agent only |
| `-g, --global` | Global (default) |

## Idempotence
- If already authenticated, `init --all --browser` prints `✓ Already authenticated` and proceeds to reinstall CLI + 28 skills. Safe to re-run.
- If not authenticated, same command opens browser, prints `https://firecrawl.dev/cli-auth?code_challenge=...` and spins `Waiting for browser authentication...` until timeout.

## Headless pattern
```bash
# Phase 1 — install, skip blocking auth
npx -y firecrawl-cli@latest init --all --browser --skip-auth

# Phase 2 — auth headless
firecrawl login --api-key $FIRECRAWL_API_KEY
firecrawl --status  # Credits: 1000/1000 proves valid

# Phase 3 — re-run full init now that auth exists (becomes no-op on auth step)
npx -y firecrawl-cli@latest init --all --browser  # → Already authenticated

# Alternative single-shot:
npx -y firecrawl-cli@latest init --all --browser -k $FIRECRAWL_API_KEY
```

## Skills installed (28)
Core (12) + Workflows (16) → symlinked `~/.hermes/skills/firecrawl*` → `~/.agents/skills/firecrawl*`
- firecrawl, firecrawl-scrape, firecrawl-search, firecrawl-map, firecrawl-crawl, firecrawl-parse, firecrawl-agent, firecrawl-interact, firecrawl-monitor, firecrawl-research-index, firecrawl-developer-index, firecrawl-knowledge-* etc.

## Verify
```bash
firecrawl --version  # 1.23.3
firecrawl --status   # Authenticated, concurrency, credits
firecrawl view-config
```
