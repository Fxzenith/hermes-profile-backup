# Increasing Hermes Memory Capacity — Options & Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Expand the effective memory capacity of this Hermes instance beyond the current 76%-full 4,000-char built-in store, using the lowest-cost, most reliable options available on this VPS.

**Architecture:** Three stacked layers, cheapest first — (1) tune the built-in char-limited store, (2) offload bulk/procedural knowledge into skills/session history, (3) swap in a pluggable external memory provider (semantic/vector store) that removes the char ceiling entirely. Built-in MEMORY.md/USER.md stays active alongside any external provider.

**Tech Stack:** Hermes built-in memory (`memory.*` config), Hermes curator, skills, and the bundled memory-provider plugins (`holographic`, `mem0`, `hindsight`, `openviking`, `byterover`, `supermemory`, `honcho`, `retaindb`), plus the existing gbrain second brain.

---

## Current Context (verified)

- Built-in store: `MEMORY.md` + `USER.md` files, injected every turn.
- Config (`/root/.hermes/config.yaml`): `memory.memory_char_limit: 4000`, `memory.user_char_limit: 3000`, `memory_enabled: true`, `user_profile_enabled: true`. **No `memory.provider` key set** → built-in only.
- Current usage: memory 3,048/4,000 chars (**76%**, ~950 headroom); user profile 175/3,000 (5%).
- CLI: `hermes memory` manages external providers (`setup`, `status`, `off`, `reset`). Available bundled providers: `honcho, openviking, mem0, hindsight, holographic, retaindb, byterover`. **Only one external provider active at a time; built-in memory always active.**
- Tradeoff that governs everything: memory is injected into **every** turn → more memory = more tokens per turn = higher latency/cost. Keep the hot store small; push bulk to on-demand layers.

---

## Proposed Approach

| Layer | Option | Cost | Effort | Capacity gain |
|---|---|---|---|---|
| 1a | Raise `memory_char_limit` / `user_char_limit` | token cost per turn | 2 min | 2–3× linear |
| 1b | Enable `curator.consolidate` | aux-model calls (cheap) | 2 min | frees stale space, no growth |
| 2 | Move procedures → skills (`~/.hermes/skills/`) | none | ongoing | effectively unlimited, loaded on demand |
| 2b | Use `session_search` for recall of old conversations | none | habit | unlimited (SQLite FTS) |
| 3 | Enable local provider **`holographic`** (SQLite + FTS5 + trust scoring, no API key) | local disk | 10 min | semantic, no char limit |
| 3b | Cloud providers: `mem0` (needs key), `supermemory`/`honcho`/`retaindb` (API keys) | paid/free tiers | 15–30 min | unlimited, hosted |
| 4 | Keep using **gbrain** (`/root/gbrain`, NVIDIA 2048-dim embeddings) as the query-first long-term archive | NVIDIA key | already done | unbounded |

**Recommendation:** Layer 1a now (immediate headroom), Layer 1b + 2 continuously (free), Layer 3 `holographic` as the real "extension" (local, free, no external dependency, fits this VPS). Skip cloud providers unless semantic recall quality demands it.

---

## Step-by-Step Plan

### Task 1: Raise built-in memory limits (2 min, zero risk, reversible)

**Files:**
- Modify: `/root/.hermes/config.yaml` (via CLI only — never hand-edit)

**Steps:**
1. Run: `hermes config set memory.memory_char_limit 8000`
2. Run: `hermes config set memory.user_char_limit 6000`
3. Verify: `hermes config get memory` shows the new values.
4. Note: new limits take effect next session (memory is injected at session start).

**Expected:** ~2× headroom (≈7,000 chars free on memory, ≈5,800 on user profile).

**Caveat:** each turn now injects up to 14,000 chars of memory context. On `deepseek-v4-flash-free` this is acceptable; if cost ever matters, drop back to 6000/4000.

### Task 2: Enable curator consolidation (frees space without growth)

**Steps:**
1. Run: `hermes config set curator.consolidate true`
2. Verify: `hermes config get curator.consolidate` → `true`.
3. Optional: `hermes curator run` (manual pass) to consolidate stale memory entries now.

**Expected:** old overlapping entries merged into compact ones; effective capacity freed.

### Task 3: Offload procedures to skills (continuous, free)

**Steps:**
1. When a multi-step workflow is completed, save it with `skill_manage(action='create')` (e.g. the autoclipper pipeline, backup runbook).
2. Keep only durable user preferences / environment facts in memory; everything procedural goes to skills (loaded only when relevant — no per-turn token cost).

**Expected:** memory growth slows to near-zero for recurring work.

### Task 4: Enable the holographic local memory provider (the main "extension")

**Files:**
- Modify: `/root/.hermes/config.yaml` (via `hermes memory setup` interactive picker)

**Steps:**
1. Run: `hermes memory setup` → select `holographic` (local SQLite fact store + FTS5 search + trust scoring; no API key, no network).
2. Verify: `hermes memory status` shows `holographic` active.
3. Confirm built-in memory still injected alongside (by design).

**Expected:** semantic long-term recall without the 4,000-char ceiling; facts retrieved by relevance, not crammed into the prompt.

**Fallback if `holographic` misbehaves:** `hermes memory off` restores built-in-only instantly.

### Task 5 (optional): Cloud providers, only if semantic quality disappoints

- `mem0` — LLM fact extraction + dedup; needs API key (`hermes memory setup` → mem0 → configure key).
- `supermemory` / `honcho` / `retaindb` — hosted semantic memory; each needs its API key + account.
- Cost/benefit: hosted = unlimited + smarter extraction, but adds per-request cost and a network dependency on a box where web auth is already flaky. Prefer local.

### Task 6 (optional): Formalize gbrain as the archive

- gbrain (`gbrain search`, NVIDIA 2048-dim embeddings) is already wired and working headless. Use it for anything archival (video summaries, notes, long-term topics); memory stays a pointer: "query gbrain for X".

---

## Tests / Validation

- `hermes memory status` → expected provider + limits shown.
- After Task 1: start a new session, confirm injection size grew (`hermes prompt-size` or watch system prompt memory block).
- After Task 4: ask a factual question about a detail only in old sessions → holographic should retrieve it via FTS5/semantic match.
- `hermes doctor` → no memory-related warnings.

## Risks, Tradeoffs & Open Questions

- **Token cost:** bigger char limits inflate every prompt. Mitigate: keep limits modest (8000/6000), rely on holographic for depth.
- **One provider at a time:** external providers are mutually exclusive; built-in always on.
- **holographic is new (0.1.0):** bundled and local, but young — keep a `hermes memory off` escape hatch.
- **Cloud keys on this box:** web auth/network already flaky → prefer local/self-hosted options.
- **Open question:** does the user want semantic recall (holographic) or just more headroom (limits)? Default plan does both, cheapest first.

## Files Likely to Change

- `/root/.hermes/config.yaml` — `memory.*`, `curator.consolidate` (via `hermes config set` only)
- `/root/.hermes/skills/` — new skills as procedures are offloaded
- `~/.hermes/` holographic store (SQLite) once provider enabled
