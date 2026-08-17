---
name: gbrain-nvidia-embeddings
description: Wire up second-brain embeddings via NVIDIA nemotron.
version: 0.1.0
author: Hermes
platforms: [linux, macos]
metadata:
  hermes:
    tags: [GBrain, Embeddings, NVIDIA, SecondBrain]
---

# GBrain + NVIDIA Nemotron Embeddings

Configures the gbrain second brain (garrytan/gbrain) to embed via the NVIDIA
API Catalog (`nvidia/llama-nemotron-embed-vl-1b-v2`, 2048 dims): install/repair
the CLI, persist the key, backfill chunks, and — the core value — debug
"Bad Request" failures from asymmetric embedding providers by inspecting the
actual wire body. Covers setup + embed only; not extract/consolidate pipelines
or Postgres brains.

## When to Use

- "Configure the second brain / knowledge base with NVIDIA nemotron"
- "gbrain embed fails with Bad Request" (or any OpenAI-compatible embed 400)
- Setting up gbrain from a fresh clone (bun install/link)
- A repo won't compile after a botched automated find-replace (corruption triage)

## Prerequisites

- bun: `curl -fsSL https://bun.sh/install | bash`, then
  `export PATH="$HOME/.bun/bin:$PATH"`
- gbrain clone + deps: `cd <repo> && bun install && bun link` (global
  `gbrain` CLI; verify with `gbrain --version`)
- `NVIDIA_API_KEY` (`nvapi-...`, free tier at https://build.nvidia.com/)
- `~/.gbrain/config.json` already targets `nvidia:llama-nemotron-embed-vl-1b-v2`
  (dims 2048) — check with `gbrain config get embedding_model`

## How to Run

Invoke through the `terminal` tool: export PATH + NVIDIA_API_KEY, run
`gbrain embed --stale`, verify with `gbrain search` and `gbrain doctor`.

## Quick Reference

- `gbrain doctor` — health report; must run without compile errors
- `gbrain embed --stale` — backfill embeddings for unembedded chunks
- `gbrain search "<query>"` — vector search; a `[0.78]`-style similarity score
  proves embeddings are live (plain keyword search has no score)
- `gbrain sources list` — registered sources
- Key storage: gbrain reads auth strictly from env vars (`recipe.auth_env`) —
  persist via `export NVIDIA_API_KEY=...` in the shell profile
- Wire debug: temporarily patch the recipe's compat fetch shim with
  `console.error` logging of the request body + response, run embed, read
  stderr, remove the logging

## Procedure

1. **Assess**: `gbrain doctor`, `gbrain sources list`, `gbrain search "test"`.
2. **Repair if the CLI won't compile**: `git status`, then `git diff` each
   modified file. Separate intentional local work (e.g. an added provider
   recipe) from corruption (identifiers replaced by random phrases — a
   signature of a botched find-replace). Revert ONLY the corruption:
   `git checkout -- <corrupted files>`. Keep intentional files.
3. **Prove the key before touching the app**: test payload shapes against the
   raw API (see `scripts/nvidia-embed-test.sh`). A 401 = key problem; a 400
   with an otherwise-good key = payload shape problem. Asymmetric models
   400 with `"'input_type' parameter is required for asymmetric models"`.
4. **Persist the key**: `echo 'export NVIDIA_API_KEY="nvapi-..."' >> ~/.bashrc`
   (then export it in the current session too).
5. **Backfill**: `gbrain embed --stale`. On "Bad Request", go to
   "Debugging a 400" below — the wire body MUST carry `input_type` (`passage`
   for indexing, `query` for search).
6. **Verify**: `gbrain search "<query>"` returns a similarity score, and
   `gbrain doctor` reports `embed_staleness: No stale chunks` and
   `embedding_width_consistency` OK (2048d matches).
7. **Regression-check the touched code**:
   `bun test test/ai/embedQuery.test.ts test/embed-input-type-wire.serial.test.ts`
   (25 tests must stay green; wire-format suites cover ZE/Voyage/OpenAI paths).

### Debugging a 400 from the embed provider

Instrument the recipe's compat fetch shim (e.g. `nvidiaCompatFetch` in
`src/core/ai/gateway.ts`): log `typeof init.body`, the body string, the
threaded `input_type` store value, and the response status/text to stderr,
run embed, inspect, then remove the logging. Compare the wire body against
your curl of the raw API — the diff is the bug.

## Pitfalls

- NVIDIA nemotron is an ASYMMETRIC model: `input_type` is required on every
  call. The dims resolver must ALWAYS emit it —
  `input_type: inputType === 'query' ? 'query' : 'passage'`. The
  Voyage-style opt-in shape (`...(inputType ? {...} : {})`) silently omits it
  and 400s.
- `embed()` passes `inputType: undefined` for indexing paths, and undefined
  means document side by contract — a truthy-only emit drops the field
  exactly on the path that matters.
- The `__embedInputTypeStore` AsyncLocalStorage only accepted `'query' |
  'document'`; NVIDIA's wire value `'passage'` was rejected, so the shim
  never re-injected it. Widen the union + the check.
- `dimsProviderOptions` receives the BARE model name (`llama-nemotron-...`),
  so `modelId.startsWith('nvidia/')` never fires. Match on
  `recipeId === 'nvidia'` as well.
- The ai-sdk's openai-compatible adapter validates `providerOptions` against
  a fixed schema and DROPS unknown fields (like `input_type`) before building
  the wire body — the compat fetch shim must re-inject it from the store.
- `bun test`/typecheck emit pre-existing noise (TS5097 `.ts`-import errors,
  zod `Intl.Segmenter`, `MapIterator` downlevel) — bun runs fine; don't chase it.
- Test the key with curl FIRST: an embed 400 while the curl works means the
  app's wire shape is wrong, not the key.

## Verification

`gbrain search "test"` returns a result with a similarity score in brackets
(e.g. `[0.7854]`) AND `gbrain embed --stale` reports `Embedded N chunks`.
