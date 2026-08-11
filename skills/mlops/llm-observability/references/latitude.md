# Latitude telemetry — SDK v4 specifics + gbrain integration map

Session-verified 2026-07-31 against `@latitude-data/telemetry@4.0.0` (npm latest).

## SDK (`@latitude-data/telemetry`)

- Install: `bun add @latitude-data/telemetry` (npm: `@latitude-data/telemetry`).
- Primary API: `new Latitude({ apiKey, project, instrumentations: [...], serviceName })`
  → `await latitude.ready` → `latitude.getTracer(scope)` →
  `latitude.flush()` / `latitude.shutdown()`.
- **Instrumentations are opt-in SUBPATH factories**, e.g.
  `createOpenAIInstrumentation(OpenAI)` from
  `@latitude-data/telemetry/instrumentations/openai`. Available subpaths:
  `openai`, `openai-agents`, `anthropic`, `bedrock`, `cohere`, `langchain`,
  `llamaindex`, `togetherai`, `vertexai`, `aiplatform`. The older
  `instrumentations: { openai: OpenAI }` map shape is stale.
- **Vercel AI SDK v6**: no auto-instrumentation subpath. Use
  `experimental_telemetry: { isEnabled: true, tracer: latitude.getTracer("vercelai"), functionId }`
  on each `generateText` / `generateObject` / `embed` call. `getTracer()`
  returns a tracer from the provider Latitude is actually exporting from.
- **Context**: `capture(name, fn, { userId, sessionId, tags, metadata, project })`
  attaches context to auto-instrumented spans (no span of its own); also
  `capture.start(name, opts)` / `capture.end(scope, error?)` lifecycle mode
  for shapes that don't fit callback wrapping. One capture at the
  request/job/turn boundary.
- **Memory spans** (long-term-memory apps): `createMemoryTelemetry({ latitude, storeId, captureContent })`,
  exported from the index. Ops: `memory.search({ query, execute, recordsFromResult })`,
  `memory.upsert({ recordId, records: [{ content }], execute })`, `memory.update`.
  storeId = the memory store (a write visible to a read ⇒ same store);
  recordId path-like (`pages/<slug>`).
- Smart filtering: only `gen_ai.*`, `llm.*`, `openinference.*`, `ai.*` spans
  are exported. Built-in redaction (`disableRedact` / `redact` options).

## Endpoints / auth

- REST base `https://api.latitude.so/v1`. `GET /v1/projects` with
  `Authorization: Bearer <key>` → `{ items: [{ id, slug, name, organizationId, firstTraceAt }] }`.
  **API keys may be bare UUIDs** — don't reject a pasted UUID, test it.
- Traces check: `GET /v1/traces?projectId=<id>`.
- MCP: `https://api.latitude.so/v1/mcp` (StreamableHTTP, SSE responses).
  Accepts the same bearer key in `initialize` — no separate OAuth key needed
  when using a static header.
- `docs.latitude.so` is scraper-gated (401 without token) → `npm pack`
  the SDK tarball for usage truth instead.

## Hermes MCP wiring (remote bearer server)

```bash
hermes config set mcp_servers.latitude.url "https://api.latitude.so/v1/mcp"
hermes config set mcp_servers.latitude.headers.Authorization "Bearer <key>"
hermes config set mcp_servers.latitude.timeout 180
```

Nested dotted keys work in `hermes config set`. Takes effect on Hermes
restart (no hot-reload). Key ends up in config.yaml — revocable via
Settings → Keys.

## gbrain integration map (audit findings)

- Stack: TypeScript + Bun, `ai@^6.0.168` (Vercel AI SDK v6), providers via
  `@ai-sdk/*`; **no prior telemetry** (clean slate — SDK owns the OTel setup).
- LLM chokepoint `src/core/ai/gateway.ts`: `chat()` generateText :2845,
  `expand()` generateObject :2263, `generateOcrText()` generateText :2317,
  `embed`/`embedMany` :1655. A central "SDK CALL layer" (abortSignal defaulting,
  `withDefaultTimeout`, ~:62) is the ideal single injection point.
- Lifecycle: `src/cli.ts` (short-lived per-command → flush in
  `cli-force-exit.ts` `flushThenExit`), `src/mcp/server.ts` (long-lived →
  init at start).
- Ops dispatch: `src/core/operations.ts` — one `capture()` boundary covers
  both CLI and MCP; metadata: `remote` flag, brain slug.
- Memory read: `searchKeyword` / `searchVector` in `pglite-engine.ts`
  (:1543/:1867) and `postgres-engine.ts` (:1557/:1830); write: page upsert
  path. storeId = brain slug; recordId `pages/<slug>`.
- Env: `LATITUDE_API_KEY` + `LATITUDE_PROJECT_SLUG=capital-empire-s-project`
  in `/root/gbrain/.env`.
- Verification without a chat-provider key: `gbrain embed --stale` (NVIDIA
  embeddings already working) emits embed LLM spans + memory update spans;
  `gbrain search "…"` emits a `search_memory` span; confirm via
  `GET /v1/traces?projectId=wjkwqta3avnn60tlhqp7n9kh`.
