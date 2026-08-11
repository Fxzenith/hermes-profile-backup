---
name: gbrain
description: Use when configuring, fixing, or querying gbrain.
---

# gbrain (second brain)

Personal knowledge base ("second brain") CLI, repo at `/root/gbrain` (bun-linked global CLI, `gbrain` on PATH via `/root/.bun/bin`), brain DB at `~/.gbrain/brain.pglite` (PGLite, zero-config; Postgres+pgvector for 1000+ files/multi-machine). Model: brain = which DB, source = which repo inside the DB; every query routes on both axes.

## ⚡ Day-to-day workflows (user's brain — run these FIRST)

**Setup every session**: the binary is NOT on PATH by default. Before any gbrain command:
```bash
export PATH="$HOME/.bun/bin:$PATH"; cd /root/gbrain
```

**ADD notes ("add this to the second brain", "save this")** — use `capture`, it lands searchable immediately:
```bash
# from a heredoc / pasted text (preferred — keeps formatting)
gbrain capture --stdin <<'EOF'
# Title

Content with ## sections, tags, source URLs...
EOF

# one-liner
gbrain capture "the thought to remember"
# from a file
gbrain capture --file ./note.md
```
Verify: `gbrain search "<keyword>"` returns the new slug with a score. Good notes have a clear `# Title`, source URL if external, tags line, and structured sections — this feeds the graph extractor.

**QUERY ("what do I have on X", "find the note about Y", user's knowledge questions)**:
```bash
gbrain search "<term>"          # raw ranked pages: [score] slug -- title. Score present = vector search live.
gbrain get <slug>               # full note content (e.g. inbox/2026-08-07-1e17dc07)
```
**Known limitation**: `gbrain think "question"` (synthesized prose answer) silently returns "no LLM available — set ANTHROPIC_API_KEY" on this machine. Do NOT rely on it. Use `gbrain search` + read the top page yourself and summarize; that works headless with zero extra keys.

**Routing rule**: when the user asks a knowledge question and this skill is loaded, gbrain is the FIRST source — check it before web search. Web search is often broken on this box (Firecrawl auth failures). If gbrain search returns nothing relevant, then say so and offer web search.

## Verify / baseline
- `gbrain doctor` — health report. Healthy: "Overall health score: N/100. All checks OK". Key lines: `embed_staleness: No stale chunks`, `embedding_width_consistency: Schema width (Nd) matches gateway embedding_dimensions`, `schema_version` current.
- `gbrain search "term"` — returns `[score] title`; a similarity score (e.g. `[0.7854]`) means vector search is live. Bare keyword hits without score = embeddings broken/degraded.
- `gbrain sources list` — registered sources (dirs of markdown ingested into the brain).
- Useful ops: `gbrain sources add <dir>`, `gbrain sync`, `gbrain extract`, `gbrain embed --stale`, `gbrain config show|get|set`, `gbrain onboard --check` (schema-pack upgrade preview).

## API keys (embedding/LLM providers)
- Keys are read from **env vars** — each recipe declares them in `auth_env.required` in `src/core/ai/recipes/<provider>.ts` (e.g. NVIDIA recipe requires `NVIDIA_API_KEY`). There is no `config set api_key`; persist via `export VAR=...` in `~/.bashrc`.
- Configure model: `gbrain config set embedding_model <provider>:<model>` + `gbrain config set embedding_dimensions <N>` (must match recipe `default_dims` / schema width).
- This machine: `nvidia:llama-nemotron-embed-vl-1b-v2`, 2048 dims, NVIDIA_API_KEY in ~/.bashrc.

## Embedding provider wiring — pitfalls (NVIDIA / asymmetric models)
The AI SDK `openai-compatible` adapter **strips unknown providerOptions fields** (only `dimensions`/`user` survive to the wire), so asymmetric `input_type` must ride a module-level AsyncLocalStorage store (`__embedInputTypeStore`) + a per-recipe compat fetch shim that re-injects it into the JSON body.
1. **Bare modelId**: the gateway passes the BARE model name to `dimsProviderOptions` (provider prefix is prepended only at wire time). Matching on `modelId.startsWith('nvidia/')` never fires — match on `recipeId === 'nvidia'` (5th arg) instead.
2. **Wire vocabulary**: upstream store accepts only `'query' | 'document'`; NVIDIA's API uses `'query' | 'passage'`. If the dims branch emits `'passage'`, the store check silently drops it and the shim never injects `input_type` → 400.
3. **Required field**: NVIDIA NeMo Retriever models are asymmetric and **400 without `input_type`** (`"'input_type' parameter is required for asymmetric models"`). `embed()` defaults `inputType` to undefined = document-side indexing, so the branch must ALWAYS emit (`inputType === 'query' ? 'query' : 'passage'`), not `...(inputType ? {...} : {})`. (Voyage is opt-in asymmetric; ZE zembed-1 is required like NVIDIA.)
4. **Wire debugging**: `console.error` at the very TOP of the compat shim (before the passthrough guards) to dump `typeof input`, `init.body` — the ai-sdk passes string URL + JSON string body, so you can see exactly what's missing. Probe the provider directly with curl first (see `references/nvidia-asymmetric-embeddings.md` for the matrix).

## Repo corruption triage (working-tree hygiene)
This repo previously contained widespread corruption from a botched automated find-replace (identifiers replaced with hallucinated phrases like `pforeign exchange`, `countStalePagesCurrency marketstraction` — broke `gbrain doctor`/build entirely). Pattern that works:
1. `git status` → `git diff` each modified file; classify: intentional work vs corruption.
2. Corruption usually repeats one pattern — grep for it: `grep -rn "pforeign exchange" src/`.
3. **Selective revert**: `git checkout -- <files>` for corrupted files only; KEEP intentional uncommitted work (e.g. a custom recipe + its gateway/dims edits that match the configured model). Don't blanket `checkout -- .`.
4. Re-verify: `gbrain doctor` must build and run.

## Verification
- `bun test test/ai/embedQuery.test.ts test/embed-input-type-wire.serial.test.ts test/gateway-embed-model-override.test.ts` — the wire-format suites; 25 pass expected.
- End-to-end: `gbrain embed --stale` → "Embedded N chunks" with no Bad Request; then `gbrain search` returns a score.
- Note: standalone `tsc` lint on this repo spews pre-existing noise (`.ts` import extensions, zod v3/v4 Intl.Segmenter) — bun's runtime tsconfig is authoritative; don't chase those errors.

## References
- `references/nvidia-asymmetric-embeddings.md` — full NVIDIA debug chain: curl probe matrix, before/after wire bodies, exact fixes, key facts.
