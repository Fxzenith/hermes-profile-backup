---
name: llm-observability
description: Add tracing/observability to existing LLM apps.
version: 0.1.0
author: Hermes
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [LLM, Observability, Tracing, Telemetry, Latitude, OpenTelemetry]
---

# LLM App Observability (tracing/telemetry integration)

Class-level workflow for instrumenting an existing LLM application with a
tracing/observability vendor (Latitude, Langfuse, LangSmith, OpenTelemetry…).
Proven on gbrain (TypeScript + Bun + Vercel AI SDK v6) with Latitude; the
concrete session detail lives in `references/latitude.md`.

## When to Use

- "Add tracing / telemetry / observability to this app"
- Wiring any tracing vendor into an existing codebase
- A pasted credential that doesn't look like a key, or vendor docs that 403

## Workflow

1. **Audit before planning.** Find: LLM call sites (grep `generateText` /
   `streamText` / `chat` / `embed`), the AI SDK version, existing telemetry
   (grep `OTEL_`, Sentry, Langfuse in package.json + src), entry points and
   process lifecycle (short-lived CLI vs long-lived server → where flush
   belongs), and any central SDK-call defaulting layer (e.g. an abortSignal
   wrapper) — that wrapper is the ideal telemetry injection point.
2. **Verify credentials early with a cheap authenticated read.** A bare UUID
   pasted into chat may be the API key. `curl` the vendor's list endpoint
   (e.g. `GET /v1/projects`) with it before planning around it. 200 → key;
   401 → ask.
3. **Get version-matched API truth.** Vendor docs are frequently gated or
   JS-rendered. `npm pack <sdk-package>` into /tmp, extract, and read the
   tarball's README + `dist/*.d.ts` exports. The README is authoritative for
   THAT version — installed-skill snippets and blog posts lag releases (e.g.
   Latitude v4 moved to opt-in subpath instrumentation factories; the v3 map
   shape is stale).
4. **Resolve material gaps one at a time** (account? project? existing
   telemetry to preserve?), then present a plan and WAIT for explicit
   approval before touching code.
5. **Implement.**
   - Init once at startup, before the first LLM call; env-gated no-op so a
     missing key never breaks the app.
   - Inject at the SDK-call chokepoint (one wrapper change covers
     chat/expand/ocr/embed).
   - One `capture()` boundary per request/job/turn — never per internal step.
   - Memory/retrieval apps: trace the read (search) and write (upsert) paths
     — that is the product's core value.
   - Flush on teardown for short-lived processes (CLI exit hooks), shutdown
     for servers.
   - Secrets only in `.env` (gitignored); never re-echo a pasted key in
     chat; never commit it.
6. **Verify with real traces, not compile.** Run a real LLM-touching command
   (embed/search/extract), then confirm spans landed via the vendor API
   (`GET /v1/traces?projectId=…`) or MCP tools.

## Pitfalls

- **Skill snippets go stale.** Confirm API shape against the npm-pack'd
  README for the exact version in package.json — never trust a skill's
  snippet over the shipped package.
- **Short-lived CLI processes drop spans** unless flushed before exit — hook
  the app's existing teardown path (`flushThenExit`-style hooks).
- **`await sdk.ready` before the first LLM call** or spans silently never
  export.
- **Vercel AI SDK v6**: no auto-instrumentation exists — use
  `experimental_telemetry: { isEnabled: true, tracer: vendor.getTracer(...),
  functionId }` on each call.
- **Unknown `providerOptions` fields get stripped** by the AI SDK before the
  wire — shims must re-inject what the wire requires (same bug class as
  embedding `input_type`).
- Don't encode environment-state failures ("vendor is broken"): a missing
  key is a config gap — fix it in `.env`.

## Support files

- `references/latitude.md` — Latitude SDK v4 shapes, endpoints, Hermes MCP
  wiring, and the gbrain integration map (call sites, lifecycle hooks).
