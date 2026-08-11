# OpenCode Zen / Go — provider specifics

Session-derived notes (verified 2026-07 against `hermes_cli/providers.py` and
`hermes_cli/models.py` in the Hermes source tree).

## Identity & aliases

| Alias you type | Canonical provider id | Notes |
|---|---|---|
| `opencode-zen` | `opencode` | models.dev id; `HERMES_OVERLAYS["opencode"]` |
| `zen` | `opencode` | |
| `opencode-go` | `opencode-go` | Open-models subscription ($10/mo) |
| `go`, `opencode-go-sub` | `opencode-go` | |

`hermes auth add opencode-zen` stores the key under `OPENCODE_ZEN_API_KEY`.
`hermes auth add opencode-go` → `OPENCODE_GO_API_KEY`.

Both are **flat-namespace resellers**, NOT routing aggregators: every model they
list is first-party, served under their own subscription. The picker dedup must
NOT strip their models just because a user custom proxy serves a same-named
model (`is_routing_aggregator()` returns False for them).

## Base URLs (the /v1 question)

OpenCode's OpenAI-compatible endpoints live under `/v1`; the Anthropic SDK appends
its own `/v1/messages`, so anthropic_messages needs the `/v1` suffix STRIPPED.

| API mode | Base URL (Zen) | Base URL (Go) |
|---|---|---|
| chat_completions / codex_responses | `https://opencode.ai/zen/v1` | `https://opencode.ai/go/v1` |
| anthropic_messages | `https://opencode.ai/zen` | `https://opencode.ai/go` |

- Env override: `OPENCODE_ZEN_BASE_URL` / `OPENCODE_GO_BASE_URL`. Custom overrides
  are left alone by normalization unless they already carry `/v1`.
- `hermes_cli/models.py::normalize_opencode_base_url()` heals persisted URLs:
  a URL stripped for anthropic mode gets `/v1` re-appended when you switch back to
  chat_completions (otherwise you'd POST to the marketing site → 404).
- `hermes_cli/models.py::opencode_model_api_mode()` decides per-model: models
  matching `claude-*` on Zen route through the Anthropic-style endpoint; Qwen
  models on Zen moved to `/v1/messages`; most others are chat_completions.

## Per-model ID normalization

`hermes_cli/model_normalize.py` strips vendor prefixes for these providers
(e.g. `nvidia/nemotron-3-ultra-550b-a55b` → `nemotron-3-ultra-550b-a55b`)
because their `/v1/models` returns bare IDs, not `vendor/model` routing slugs.
`claude-*` on Zen keeps its name for the Anthropic route.

## Verification

```bash
hermes auth status opencode-zen        # expect: logged in
hermes auth list opencode-zen          # shows OPENCODE_ZEN_API_KEY api_key env:...
hermes chat -q "Hello" --provider opencode-zen
```

Note: `hermes chat --provider opencode-zen` prints a model-normalization warning
when your default model carries a vendor prefix — that's expected, not an error.
