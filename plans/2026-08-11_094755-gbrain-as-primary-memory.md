# GBrain-as-Primary-Memory Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make Hermes automatically use the existing gbrain second brain (PGLite + NVIDIA embeddings at `/root/gbrain`) for per-turn recall and durable storage, replacing reliance on the char-limited built-in MEMORY.md store.

**Architecture:** A user-installed Hermes **MemoryProvider plugin** named `gbrain` at `$HERMES_HOME/plugins/gbrain/` (i.e. `/root/.hermes/plugins/gbrain/`). The plugin shells out to the gbrain CLI (`gbrain query` / `search` / `salience` / `capture`), which is already proven to work headless on this box. Hermes's MemoryManager activates it via `memory.provider: gbrain`; per turn it calls `prefetch(user_message)` → hybrid semantic search → injects top hits as context, and mirrors built-in memory writes into gbrain via `capture`. The built-in MEMORY.md prompt block is then shrunk or disabled so gbrain becomes the default brain in practice.

**Tech Stack:** Hermes MemoryProvider ABC (`agent/memory_provider.py`), user-plugin loader (`plugins/memory/__init__.py`, `register(ctx)` pattern, `_hermes_user_memory.<name>` namespace), gbrain CLI v0.42.59.0 (`/root/.bun/bin/gbrain`, cwd `/root/gbrain`).

---

## Current Context (verified)

- MemoryProvider ABC requires: `name`, `is_available()`, `initialize()`, `get_tool_schemas()`; optional: `system_prompt_block()`, `prefetch()`, `queue_prefetch()`, `sync_turn()`, `handle_tool_call()`, `shutdown()`, `on_memory_write()` (mirrors built-in writes), `on_session_end()`, `get_config_schema()`, `save_config()`, `backup_paths()`.
- User plugins: `$HERMES_HOME/plugins/<name>/__init__.py` — either a `register(ctx)` fn calling `ctx.register_memory_provider(...)`, or a top-level `MemoryProvider` subclass. Discovered automatically (`hermes memory setup` lists them). Bundled providers take precedence on name collisions — `gbrain` does not collide.
- Only ONE external provider active at a time (`memory.provider`); built-in MEMORY.md/USER.md is always active alongside, but `memory.memory_enabled: false` skips the MEMORY.md prompt block (`agent/system_prompt.py:524`) — USER.md stays.
- gbrain CLI (verified): `gbrain query <q> [--limit N]` (hybrid vector+keyword, `--detail` medium default), `gbrain search <q> [--limit N]` (FTS), `gbrain salience [--days N] [--limit N]` (personal/emotional bursts — for "what's going on" queries), `gbrain capture [content] | --stdin | --file PATH [--quiet] [--json]` (writes; returns slug). Binary at `/root/.bun/bin/gbrain`; must run with `PATH` including `~/.bun/bin` and cwd `/root/gbrain` (per memory: not on PATH by default).
- `gbrain query`/`search` output shape (text vs JSON) not yet sampled — **Task 1 pins it down** before the parser is finalized. Upgrade available: 0.42.59.0 → 0.44.0.0 (optional, later).
- Current built-in usage: memory 3,048/4,000 chars (76%); user profile 175/3,000.

**Assumption:** gbrain stays the single source of long-term knowledge; Hermes becomes a client of it. We do NOT copy the gbrain DB into Hermes — the provider is a thin CLI bridge.

---

## Proposed Approach

1. Build `gbrain` MemoryProvider plugin (CLI bridge, ~250 lines).
2. `prefetch()` per turn: `gbrain query "<user msg>" --limit 5` → format top hits → inject as `GBRAIN RECALL` context block. Fallback to `search` on failure. `salience` for open-ended personal queries (v2 enhancement).
3. `system_prompt_block()`: standing instruction — check gbrain FIRST for anything factual about the user/projects; store durable facts with `gbrain capture`.
4. `on_memory_write()`: mirror built-in memory writes (`[hermes:memory]` / `[hermes:user]` prefixed) into gbrain via `capture --stdin --quiet`.
5. Expose an explicit `gbrain` tool (actions: `query`, `search`, `capture`, `salience`) so the model can dig on demand.
6. Activate: `memory.provider: gbrain`. Then shrink the default brain: `memory.memory_char_limit: 800` (keep a pointer note) — or test `memory.memory_enabled: false`; if it also kills the memory tool, keep enabled-tiny. **This is the "always use gbrain instead of the default brain" step.**
7. Guard rails: skip writes for subagent/cron contexts (`agent_context` kwarg), timeouts on all subprocess calls, `backup_paths()` → `~/.gbrain` so `hermes backup` covers it.

---

## Step-by-Step Plan

### Task 1: Pin down gbrain CLI output shapes (10 min, read-only)

**Objective:** Know exactly what `query`/`search`/`capture --json` print so the parser is real, not guessed.

**Steps:**
1. Run: `cd /root/gbrain && PATH="$HOME/.bun/bin:$PATH" gbrain query "hermes memory" --limit 3` — inspect stdout (text table or JSON?).
2. Run: same with `--json` if available (`gbrain search --json`); capture a sample of each shape into `/tmp/gbrain-samples.md`… (note: /tmp is ephemeral — save to `/root/.hermes/plans/gbrain-cli-samples.md` instead).
3. Run: `echo "test note" | gbrain capture --stdin --quiet` — confirm it prints a slug and exits 0.
4. Record: exact field names for hits (slug/title/excerpt/content/snippet) to use in `_format()`.

**Expected:** a documented sample of each command's output. If `query` lacks `--json`, parse the text table or fall back to `search --json`.

### Task 2: Scaffold the provider directory

**Files:**
- Create: `/root/.hermes/plugins/gbrain/__init__.py`
- Create: `/root/.hermes/plugins/gbrain/plugin.yaml`
- Create: `/root/.hermes/plugins/gbrain/README.md`

**Step 1:** Write `plugin.yaml`:

```yaml
name: gbrain
version: 0.1.0
description: "GBrain second brain — per-turn hybrid recall + capture via the gbrain CLI (PGLite + vector embeddings)."
```

**Step 2:** Write a stub `__init__.py` containing only `class GBrainProvider(MemoryProvider): ...` with `name` and `is_available()` (returns `Path(bin).exists() and Path(dir).is_dir()`), plus `def register(ctx): ctx.register_memory_provider(GBrainProvider())`.

**Step 3:** Verify discovery: `hermes memory status` and `hermes memory setup` (should now list `gbrain` as an available provider).

**Step 4:** Commit (provider dir is not a git repo — skip commit; keep files in place).

### Task 3: Implement the CLI bridge

**Files:**
- Modify: `/root/.hermes/plugins/gbrain/__init__.py`

**Step 1:** Add the subprocess helper (complete code):

```python
DEFAULT_BIN = str(Path.home() / ".bun" / "bin" / "gbrain")
DEFAULT_DIR = str(Path.home() / "gbrain")

def _run(self, args: list, stdin: str | None = None, timeout: float = 25.0) -> str | None:
    env = dict(os.environ)
    env["PATH"] = f"{Path(self._bin).parent}:" + env.get("PATH", "")
    try:
        p = subprocess.run([self._bin, *args], input=stdin,
                           capture_output=True, text=True, timeout=timeout,
                           env=env, cwd=self._dir)
    except Exception as e:
        logger.warning("gbrain %s error: %s", args[0], e); return None
    if p.returncode != 0:
        logger.warning("gbrain %s rc=%s: %s", args[0], p.returncode, p.stderr.strip()[:300])
        return None
    return p.stdout
```

**Step 2:** Constructor reads overrides from env (`GBRAIN_BIN`, `GBRAIN_DIR`) with the defaults above, plus `self._limit = 5`.

**Step 3:** `initialize(session_id, **kwargs)` — store `self._writable = kwargs.get("agent_context") in ("primary", "flush")`; warm call `self._run(["--version"])` (no failure if it returns None — availability already checked).

**Expected:** module imports cleanly (`python3 -c "import sys; sys.path.insert(0,'/root/.hermes/plugins/gbrain'); import __init__"` or via `hermes memory status`).

### Task 4: Implement recall (`prefetch` + `queue_prefetch` + `system_prompt_block`)

**Files:**
- Modify: `/root/.hermes/plugins/gbrain/__init__.py`

**Step 1:** `system_prompt_block()` returns the standing instruction (see Proposed Approach #3).

**Step 2:** `prefetch(query, *, session_id="")`:

```python
def prefetch(self, query: str, *, session_id: str = "") -> str:
    q = (query or "").strip()
    if len(q) < 3:
        return ""
    out = self._run(["query", q, "--limit", str(self._limit)])
    if out is None:
        out = self._run(["search", q, "--limit", str(self._limit)])
    return self._format(out, q)
```

**Step 3:** `_format(raw, q)` — parse per Task 1's recorded shape; produce:

```
GBRAIN RECALL (query: <q>):
- <slug>: <excerpt|snippet|content truncated to 600 chars>
...
```

Dedupe by slug, cap at `self._limit` hits, return `""` when no hits.

**Step 4:** `queue_prefetch` no-op for v1 (synchronous prefetch is fine — local SQLite is fast; add background threading only if turn latency suffers).

**Expected:** a stored gbrain fact surfaces as a `GBRAIN RECALL` block when the same topic is queried.

### Task 5: Implement writes (`on_memory_write` + `capture` tool)

**Files:**
- Modify: `/root/.hermes/plugins/gbrain/__init__.py`

**Step 1:** `on_memory_write(action, target, content, metadata=None)` — mirror built-in memory writes:

```python
def on_memory_write(self, action, target, content, metadata=None):
    if not getattr(self, "_writable", True) or action == "remove":
        return
    self._run(["capture", f"[hermes:{target}] {content}", "--quiet"], timeout=30)
```

**Step 2:** Add the `gbrain` tool schema:

```python
GBRAIN_TOOL = {
    "name": "gbrain",
    "description": ("Search or write the user's gbrain second brain (PGLite + vector "
                    "embeddings). actions: query <q> (hybrid semantic), search <q> "
                    "(keyword), salience (recent notable activity), capture <content> "
                    "(store a durable fact). Use this for ANY factual recall about the "
                    "user, their projects, or anything they may have captured."),
    "parameters": {"type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["query", "search", "salience", "capture"]},
            "query": {"type": "string"},
            "content": {"type": "string"},
            "limit": {"type": "integer", "default": 5},
            "days": {"type": "integer", "default": 7},
        },
        "required": ["action"]},
}
```

**Step 3:** `get_tool_schemas()` returns `[GBRAIN_TOOL]`; `handle_tool_call()` dispatches `query`/`search` → `self._run([action, query, "--limit", ...])`, `salience` → `self._run(["salience", "--days", ...])`, `capture` → `self._run(["capture", content, "--quiet"])` and returns `{"ok": true, "slug": ...}` as JSON; unknown action → `{"error": ...}`.

**Expected:** `memory add` writes land in gbrain; `gbrain capture` tool stores facts searchable by `gbrain query`.

### Task 6: Config schema + backup integration

**Files:**
- Modify: `/root/.hermes/plugins/gbrain/__init__.py`

**Step 1:** `get_config_schema()` returns fields: `gbrain_bin` (text, default `/root/.bun/bin/gbrain`), `gbrain_dir` (text, default `/root/gbrain`), `recall_limit` (integer, default 5). Implement `save_config(values, hermes_home)` writing a JSON at `/root/.hermes/plugins/gbrain/config.json` (read it in `__init__` if present; env overrides win).

**Step 2:** `backup_paths()` returns `[self._dir or "~/.gbrain"]` → the PGLite DB joins `hermes backup` archives.

**Expected:** `hermes memory setup` walks through the three fields; `hermes backup` includes `~/.gbrain`.

### Task 7: Activate the provider

**Steps:**
1. Run: `hermes memory setup` → select `gbrain` (or `hermes config set memory.provider gbrain`).
2. Verify: `hermes memory status` → gbrain active; `hermes config get memory.provider` → `gbrain`.
3. Verify discovery didn't break other providers: `hermes memory setup` still lists the bundled 8.

**Expected:** new sessions load GBrainProvider; `GBRAIN RECALL` blocks appear on relevant turns.

### Task 8: Demote the default brain (the "instead of" step)

**Steps:**
1. Option A (safe): `hermes config set memory.memory_char_limit 800` — keep a tiny always-on block (e.g. the gbrain pointer) so near-zero default-brain content is injected; everything real lives in gbrain.
2. Option B (aggressive): `hermes config set memory.memory_enabled false` — kills the MEMORY.md prompt block entirely (USER.md stays). **Verify** in a new session that the `memory` tool still exists (`hermes tools` / ask in-session); if the tool vanishes, revert to Option A (mirroring via `on_memory_write` only works while the built-in tool exists).
3. Move durable facts already in MEMORY.md into gbrain first (one `gbrain capture` per entry, or `gbrain import` the exported notes) so nothing is lost.
4. Optional cleanup: `hermes memory reset` only after migration is confirmed.

**Expected:** system prompt contains gbrain instructions + minimal-or-no MEMORY.md block; recall comes from gbrain per turn.

### Task 9: End-to-end validation

**Steps:**
1. Capture a test fact: `gbrain capture "test marker: user's favorite color is teal"`.
2. Start a fresh session and ask: "what's my favorite color?" → answer must cite the GBRAIN RECALL block.
3. In-session: ask the model to "remember X in gbrain" → provider `capture` fires; `gbrain search X` finds it afterward.
4. `hermes doctor` → no memory warnings.
5. Watch a few turns in `hermes logs` for `gbrain` warnings (subprocess errors would log there).

### Task 10 (optional): Housekeeping

- `gbrain self-upgrade` 0.42.59.0 → 0.44.0.0 (newer search modes); re-run Task 9 after.
- Add `salience` dispatch in `prefetch()` when the query is personal/open-ended ("what's going on", "what's new with me") — gbrain explicitly recommends it over semantic search for those.
- Consider `--detail low` on `query` to trim injected context size.

---

## Tests / Validation

- `hermes memory status` → `gbrain` active, built-in noted.
- Unit: `GBrainProvider().is_available()` True; `prefetch("favorite color")` returns a `GBRAIN RECALL` block containing the test capture.
- Unit: `handle_tool_call("gbrain", {"action": "capture", "content": "..."})` → `{"ok": true, "slug": ...}`.
- Integration: fresh-session factual question answered from gbrain (Task 9).
- Regression: `hermes doctor` clean; memory tool still functional if Option A chosen.

## Risks, Tradeoffs & Open Questions

- **Built-in cannot be fully removed:** MEMORY.md/USER.md always exist; "always gbrain" = gbrain recall per turn + tiny/no built-in block (Option A/B). Option B may disable the `memory` tool — verify before committing.
- **CLI bridge fragility:** gbrain CLI output format could change on upgrade → pin the parser to sampled fields; `--json` if available; keep `search` fallback. Upgrade 0.44.0.0 re-verifies.
- **Per-turn latency:** each `prefetch` spawns a subprocess (local PGLite — fast, but process spawn ~50-150ms). If turns feel slow, move to background `queue_prefetch` + cached results (ABC supports it).
- **Token cost:** recall block is relevance-based (only top-5 hits) vs the old always-on 4,000-char block — typically cheaper and far more useful.
- **One provider at a time:** activating gbrain precludes holographic/mem0/etc. Fine — gbrain IS the chosen backend.
- **gbrain `think` unavailable headless** (needs ANTHROPIC_API_KEY) — irrelevant; provider only uses `query/search/salience/capture`.
- **Open question:** does the user want the aggressive Option B (kill MEMORY.md injection, risk losing the memory tool) or safe Option A (tiny pointer block)? Default: **Option A** — zero risk, same effect in practice.
- **Open question:** should subagent context also read gbrain? Default no (recall only in primary agent turns; subagents inherit provider absence via `agent_context`).

## Files Likely to Change

- Create: `/root/.hermes/plugins/gbrain/__init__.py`, `plugin.yaml`, `README.md`, `config.json` (runtime)
- Modify: `/root/.hermes/config.yaml` — `memory.provider`, `memory.memory_char_limit` (via `hermes config set` only)
- Data: `~/.gbrain/brain.pglite` (gains `[hermes:*]` tagged captures)
- Reference: `/root/.hermes/plans/gbrain-cli-samples.md` (Task 1 output samples)
