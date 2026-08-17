# NVIDIA asymmetric embeddings — full debug chain (gbrain gateway)

Session: configuring gbrain `nvidia:llama-nemotron-embed-vl-1b-v2` (2048 dims). `gbrain embed --stale` failed with `[embed(nvidia:llama-nemotron-embed-vl-1b-v2)] Bad Request` for every page, while a raw curl with the same key worked. This is the complete diagnosis → fix story.

## Key facts
- Endpoint: `POST https://integrate.api.nvidia.com/v1/embeddings` (OpenAI-compatible shape, but asymmetric).
- Model: `nvidia/llama-nemotron-embed-vl-1b-v2` — default 2048 dims, Matryoshka range [128..2048].
- Key: `nvapi-...` from https://build.nvidia.com/ (free tier). Env var `NVIDIA_API_KEY`, declared in recipe `src/core/ai/recipes/nvidia.ts` (`auth_env.required`).
- API REQUIRES `input_type` on every call (asymmetric model): `'query'` for queries, `'passage'` for documents. Missing it → HTTP 400 `"'input_type' parameter is required for asymmetric models"`.
- Accepts `"input"` as either a plain string or an array of strings (both fine when `input_type` present).

## Curl probe matrix (fastest way to isolate provider vs client)
```bash
K="nvapi-..."; M="nvidia/llama-nemotron-embed-vl-1b-v2"
# OK:     {"model":M,"input":["test"],"input_type":"query"}
# OK:     {"model":M,"input":"test","input_type":"passage"}
# OK:     {"model":M,"input":["test"],"input_type":"passage"}
# 400:    {"model":M,"input":["test"]}   → "'input_type' parameter is required for asymmetric models"
```
Conclusion: provider is healthy and key valid; the client was sending a body without `input_type`.

## How the wire body flows (and where it breaks)
1. `embed(texts, opts)` → `dimsProviderOptions(recipe.implementation, modelId, dims, opts?.inputType, recipe.id)`.
2. `opts.inputType` **defaults to undefined** for document-side indexing (docstring: "treated as 'document' by the dim resolver — the correct default for indexing paths"). So an asymmetric-required branch must ALWAYS emit, mapped to provider vocabulary.
3. The AI SDK `createOpenAICompatible().textEmbeddingModel()` **validates `providerOptions.openaiCompatible` against a fixed schema (`dimensions`, `user`) and silently DROPS every other field** before building the wire body. So `input_type` can't ride providerOptions — it must travel via a module-level `AsyncLocalStorage` store (`__embedInputTypeStore`) populated by `embedSubBatch` when the dims branch emitted a value, then be re-injected by the recipe's compat fetch shim.
4. `embedSubBatch` only runs the store when `threadedInputType === 'query' | 'document'` — NVIDIA's `'passage'` was rejected, store stayed empty, shim passed the body through untouched.

## The three bugs in the custom NVIDIA recipe (all fixed)
| # | Bug | Symptom | Fix |
|---|---|---|---|
| 1 | `dimsProviderOptions` matched `modelId.startsWith('nvidia/')`, but gateway passes the BARE modelId (`llama-nemotron-embed-vl-1b-v2`); prefix is added only at wire time (`effectiveModelId = 'nvidia/' + modelId`) | branch never fired → no `input_type` in providerOptions | also match `recipeId === 'nvidia'` (5th param) and bare `llama-nemotron-embed` prefix |
| 2 | Store typed `AsyncLocalStorage<'query' \| 'document'>`; NVIDIA emits `'passage'` | `=== 'query' \|\| === 'document'` check failed → store empty → shim no-op | widen to `'query' \| 'document' \| 'passage'` and extend the check |
| 3 | Branch emitted input_type only `...(inputType ? {...} : {})` | undefined inputType (document side) → no field → 400 | always emit: `input_type: inputType === 'query' ? 'query' : 'passage'` |

Reference pattern in the same file: ZeroEntropy `zembed-1` is the upstream model that is ALSO required-asymmetric — it emits `input_type: inputType ?? 'document'` unconditionally. Voyage is opt-in asymmetric (emits only when threaded) — do not copy Voyage's pattern for NVIDIA/ZE-style providers.

## Debug technique (use first next time)
- Instrument the compat shim with `console.error` at the very TOP — before its passthrough guards (`typeof input !== 'string' && !(input instanceof URL) → passthrough`, `threadedInputType === undefined → passthrough`). The ai-sdk calls fetch with a string URL + string JSON body, so a top-of-function log shows the exact wire body in one `gbrain embed` run:
  `[nvidia-shim] ENTER input: string https://integrate.api.nvidia.com/v1/embeddings | init.body: string {"model":...,"input":["# Test Brain"],"encoding_format":"float","dimensions":2048}`
  Missing `input_type` in that dump = dims/store chain broken (providerOptions never threaded). If NO shim log appears at all = the fetch wrapper isn't wired (`compat.fetch ??` precedence in `instantiateEmbedding`, or recipe's `resolveOpenAICompatConfig`).
- After fixing, confirm both directions: `input_type: "passage"` on the document/index side and `input_type: "query"` on `embedQuery`/search side. Search returns a similarity score (e.g. `[0.7854]`) once vectors are live.

## Verification commands
- `bun test test/ai/embedQuery.test.ts test/embed-input-type-wire.serial.test.ts test/gateway-embed-model-override.test.ts` → 25 pass (wire-format suites: ZE required-asymmetric, Voyage opt-in preserved, OpenAI symmetric untouched).
- `gbrain embed --stale` → "Embedded N chunks across N pages", no Bad Request.
- `gbrain doctor` → `embed_staleness: No stale chunks`, `embedding_width_consistency` OK.
- Ignore standalone `tsc` noise: TS5097 (`.ts` import extensions — repo uses bun's tsconfig with `allowImportingTsExtensions`) and zod v3/v4 locale/Intl.Segmenter errors are pre-existing; bun runtime is authoritative.
