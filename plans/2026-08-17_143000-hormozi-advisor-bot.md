# Hormozi Advisor Bot — Implementation Plan

> **For Hermes:** Implement task-by-task. This is a self-contained RAG CLI; no subagent required unless the user later wants a chat UI.

**Goal:** Build a command-line "Alex Hormozi advisor" bot that answers questions, drafts copy, and brainstorms — strictly grounded in the 50 Hormozi expert notes already stored in GBrain (`experts/alex-hormozi/`).

**Architecture:** A thin Python CLI (`hormozi_bot.py`) that (1) retrieves the most relevant Hormozi notes via `gbrain query` + `gbrain get`, then (2) sends the question + retrieved notes to an OpenAI-compatible LLM to synthesize an answer/draft. If no LLM key is configured, it degrades gracefully to a **retrieval-only mode** that prints the raw matching notes so the tool is useful without any API spend. A strict system prompt enforces "answer only from the notes provided" and labels inference vs. direct knowledge (matching the Expert Advisory Council rule).

**Tech Stack:** Python 3 (stdlib `subprocess`, `argparse`, `json`, `os`) + `requests` for the LLM call. Reuses the existing `gbrain` CLI (already embedded with NVIDIA embeddings). No new DB, no server. LLM = OpenCode Zen `https://opencode.ai/zen/v1`, model `hy3-free` (free, OpenAI-compatible), key read from `OPENCODE_ZEN_API_KEY`.

---

## Current context / assumptions

- GBrain is installed; `export PATH="$HOME/.bun/bin:$PATH"` then `gbrain` works.
- 50 Hormozi notes exist under prefix `experts/alex-hormozi/` (verified: `gbrain list --slug-prefix experts/alex-hormozi` → 50).
- `gbrain query "<q>"` performs hybrid search and returns ranked `[score] slug -- title` lines; `gbrain get <slug>` returns the full note (YAML frontmatter + body).
- **LLM endpoint confirmed working (2026-08-17):** OpenCode Zen at `https://opencode.ai/zen/v1`, model `hy3-free` (free, `cost:0`), OpenAI-compatible chat completions. Key is provided via `OPENCODE_ZEN_API_KEY` — verified with a live test call returning valid JSON. The bot reads this from the environment (no key hardcoded in source).
- The user prefers simple, low-cost tools — a single CLI script with no daemon is the right scope. (Optional Hermes-skill wrapper included as a final task for chat invocation.)

## Open questions / decisions

1. **LLM provider + key** — RESOLVED: OpenCode Zen `https://opencode.ai/zen/v1`, model `hy3-free` (free). Key via `OPENCODE_ZEN_API_KEY` env var (verified live). No user-supplied key needed.
2. **Default model** — RESOLVED: `hy3-free` (free, OpenAI-compatible) — matches the user's low-token-cost preference.
3. **Invocation style** — CLI now; optionally expose as a Hermes slash skill so the user can type `/hormozi <question>` in chat (Task 6).

---

## Proposed approach

- **Retrieval layer** (`retrieve(query, k=6)`): run `gbrain query "<query>" --limit 12`, keep only slugs starting with `experts/alex-hormozi/`, take top `k`, then `gbrain get` each to fetch full text. Assemble a single context block.
- **LLM layer** (`synthesize(mode, user_input, context)`): POST to `${LLM_BASE_URL}/chat/completions` with a mode-specific system prompt. Modes:
  - `ask` — answer the question using ONLY the notes; if the notes don't cover it, say so and do not invent.
  - `draft` — produce copy (email/ad/offer/script) applying the cited Hormozi frameworks.
  - `brainstorm` — generate ideation variants grounded in the notes.
- **Grounding guardrail** (in the system prompt, enforced in code by refusing to send the call if context is empty for `ask`): the LLM must cite note slugs and may mark `[inference]` when extending beyond the notes.
- **No-key fallback:** if no key, print the retrieved notes' principle + explanation verbatim so the user still gets the raw Hormozi material.

---

## Step-by-step plan

### Task 1: Create project scaffold
**Objective:** Set up the directory and dependency file.

**Files:**
- Create: `/root/hormozi_bot/requirements.txt`
- Create: `/root/hormozi_bot/.env.example`

**Step 1:** Create the folder and `requirements.txt`:
```
requests>=2.31.0
```
**Step 2:** Create `.env.example`:
```
# Copy to .env and fill in. Retrieval-only mode works with all blanks.
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4o-mini
HORMOZI_PREFIX=experts/alex-hormozi/
TOP_K=6
```
**Step 3:** Create empty `.env` (gitignored conceptually) — `touch /root/hormozi_bot/.env`.
**Step 4:** Verify layout: `ls -la /root/hormozi_bot/` shows both files.

---

### Task 2: Retrieval module with a unit test (TDD)
**Objective:** Implement `retrieve()` that calls gbrain and returns full note texts scoped to the Hormozi prefix.

**Files:**
- Create: `/root/hormozi_bot/retrieval.py`
- Create: `/root/hormozi_bot/test_retrieval.py`

**Step 1 — write failing test** (`test_retrieval.py`):
```python
import retrieval

def test_filter_scopes_to_hormozi(monkeypatch):
    # fake gbrain query output
    fake_query = "1.0 experts/alex-hormozi/aaa-method -- AAA method\n0.4 books/unrelated -- x"
    fake_get = "---\ntype: concept\n---\nexpert: Alex Hormozi\nprinciple: AAA\nconfidence: high\nexplanation: |\n  Acknowledge associate ask.\n"
    def fake_run(cmd, **kw):
        class R: stdout = fake_query if "query" in cmd else fake_get; returncode = 0
        return R()
    monkeypatch.setattr(retrieval.subprocess, "run", fake_run)
    notes = retrieval.retrieve("objection", k=6)
    assert len(notes) == 1
    assert notes[0]["slug"] == "experts/alex-hormozi/aaa-method"
    assert "Acknowledge" in notes[0]["text"]
```
**Step 2 — run test, expect FAIL** (`cd /root/hormozi_bot && python3 -m pytest test_retrieval.py -q` → ImportError / not defined).
**Step 3 — implement** (`retrieval.py`):
```python
import subprocess, os, re

def _gbrain(args):
    env = dict(os.environ); env["PATH"] = os.path.expanduser("~/.bun/bin") + ":" + env.get("PATH","")
    r = subprocess.run(["gbrain"] + args, capture_output=True, text=True, env=env)
    return r.stdout

def retrieve(query, k=6, prefix="experts/alex-hormozi/"):
    out = _gbrain(["query", query, "--limit", "12"])
    slugs = re.findall(r"experts/alex-hormozi/[A-Za-z0-9\-]+", out)
    seen, notes = set(), []
    for s in slugs:
        if s in seen: continue
        seen.add(s)
        text = _gbrain(["get", s])
        notes.append({"slug": s, "text": text})
        if len(notes) >= k: break
    return notes
```
**Step 4 — run test, expect PASS.**
**Step 5 — commit:** `git -C /root/hormozi_bot init -q && git -C /root/hormozi_bot add -A && git -C /root/hormozi_bot commit -m "feat: retrieval module with scope filter + test"`

---

### Task 3: LLM synthesis module (TDD)
**Objective:** Implement `synthesize()` posting to an OpenAI-compatible endpoint, with graceful no-key fallback.

**Files:**
- Create: `/root/hormozi_bot/llm.py`
- Create: `/root/hormozi_bot/test_llm.py`

**Step 1 — failing test** (`test_llm.py`):
```python
import llm, retrieval

def test_no_key_returns_raw_context(monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "load_config", lambda: {"LLM_API_KEY": ""})
    notes = [{"slug":"experts/alex-hormozi/x","text":"principle: X\nconfidence: high\nexplanation: |\n  Do X."}]
    out = llm.synthesize("ask","how?", notes)
    assert "Do X." in out and "experts/alex-hormozi/x" in out
```
**Step 2 — run, expect FAIL.**
**Step 3 — implement** (`llm.py`):
```python
import os, requests, json

SYSTEMS = {
 "ask": "You are Alex Hormozi's advisory voice. Answer using ONLY the provided notes. "
        "Cite note slugs. If notes don't cover it, say so and do NOT invent. "
        "Mark any extension beyond the notes with [inference].",
 "draft": "Using ONLY the provided Hormozi notes, draft the requested asset. Cite the frameworks used.",
 "brainstorm": "Using ONLY the provided Hormozi notes, generate ideation variants grounded in his frameworks. Cite slugs.",
}

def load_config():
    cfg = dict(LLM_BASE_URL=os.getenv("LLM_BASE_URL","https://api.openai.com/v1"),
               LLM_API_KEY=os.getenv("LLM_API_KEY",""),
               LLM_MODEL=os.getenv("LLM_MODEL","gpt-4o-mini"),
               TOP_K="6")
    p = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(p):
        for line in open(p):
            line=line.strip()
            if line and not line.startswith("#") and "=" in line:
                k,v=line.split("=",1); cfg[k.strip()]=v.strip()
    return cfg

def synthesize(mode, user_input, notes, cfg=None):
    cfg = cfg or load_config()
    ctx = "\n\n---\n\n".join(f"[{n['slug']}]\n{n['text']}" for n in notes)
    if not cfg.get("LLM_API_KEY"):
        return ("[Retrieval-only mode — no LLM key set. Raw notes retrieved:]\n\n" + ctx)
    sys = SYSTEMS.get(mode, SYSTEMS["ask"])
    payload = {"model": cfg["LLM_MODEL"],
               "messages":[{"role":"system","content":sys},
                           {"role":"user","content":f"NOTES:\n{ctx}\n\nREQUEST: {user_input}"}],
               "temperature":0.4}
    r = requests.post(cfg["LLM_BASE_URL"].rstrip("/")+"/chat/completions",
                     headers={"Authorization":f"Bearer {cfg['LLM_API_KEY']}"},
                     json=payload, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]
```
**Step 4 — run, expect PASS.**
**Step 5 — commit.**

---

### Task 4: CLI entrypoint (`hormozi_bot.py`)
**Objective:** Wire `ask` / `draft` / `brainstorm` subcommands.

**Files:**
- Create: `/root/hormozi_bot/hormozi_bot.py`

**Step 1 — implement:**
```python
import argparse, sys
import retrieval, llm

def main():
    ap = argparse.ArgumentParser(description="Alex Hormozi advisor bot (RAG over GBrain notes)")
    sub = ap.add_subparsers(dest="mode", required=True)
    for m in ("ask","draft","brainstorm"):
        p = sub.add_parser(m); p.add_argument("prompt", nargs="+")
    args = ap.parse_args()
    q = " ".join(args.prompt)
    notes = retrieval.retrieve(q, k=int(llm.load_config().get("TOP_K","6")))
    if not notes:
        print("[No relevant Hormozi notes found for that query.]"); return
    out = llm.synthesize(args.mode, q, notes)
    print(out)

if __name__ == "__main__":
    main()
```
**Step 2 — smoke test retrieval-only** (no key needed):
`cd /root/hormozi_bot && python3 hormozi_bot.py ask "how do I handle price objections?"`
Expected: prints `[Retrieval-only mode ...]` followed by the matching `dont-negotiate-price` / `details-are-death-traps` notes.
**Step 3 — commit.**

---

### Task 5: Verification with a real LLM key (blocked until key supplied)
**Objective:** Confirm synthesized answers cite notes and stay grounded.

**Step 1:** Put key in `/root/hormozi_bot/.env` (`LLM_API_KEY=...`, `LLM_MODEL=...`).
**Step 2:** `python3 hormozi_bot.py ask "what's the CLOSER framework?"` → answer cites `experts/alex-hormozi/closer-framework`.
**Step 3:** `python3 hormozi_bot.py draft "a 3-email sequence selling a $2k coaching offer"` → draft references `three-pillar-pitch` / `pain-cycle`.
**Step 4:** `python3 hormozi_bot.py brainstorm "lead magnet ideas for a fitness coach"` → variants cite `lead-magnet-three-types`.

---

### Task 6 (optional): Hermes skill wrapper for chat invocation
**Objective:** Let the user run it from Hermes chat as `/hormozi`.

**Files:**
- Create: `~/.hermes/skills/hormozi-advisor/SKILL.md`

**Step 1:** Write SKILL.md describing: run `python3 /root/hormozi_bot/hormozi_bot.py <mode> "<query>"`, modes ask/draft/brainstorm, retrieval-only if no key.
**Step 2:** Verify `/hormozi ask "..."` invokes the script and returns output.

---

## Tests / validation summary
- `test_retrieval.py` — scope filter + full-text fetch (Task 2).
- `test_llm.py` — no-key fallback returns raw context (Task 3).
- Manual smoke (Task 4) + keyed runs (Task 5).

## Risks, tradeoffs, open questions
- **No LLM key today** → bot is fully functional in retrieval-only mode now; synthesized answers require the user to add a key (Task 5). This is the only external dependency.
- **`gbrain query` ranking quality** depends on existing NVIDIA embeddings; if a query returns off-topic notes, bump `TOP_K` or refine the question. Retrieval stays scoped to the Hormozi prefix so it can't pull unrelated brain content.
- **Grounding drift:** the LLM could still extend beyond notes. The system prompt + `[inference]` tagging + "say so if not covered" instruction mitigate this; the user (per Advisory Council rule) should treat bot output as *application/inference*, not Alex's literal words.
- **Cost:** pin a cheap model (`gpt-4o-mini` / 8B-class) — typical ask ≈ 2-4k tokens. Matches the user's low-token-cost preference.

## How this plan is an improvement over a naive version
- **Scope-locked retrieval** (only `experts/alex-hormozi/`) instead of dumping the whole brain.
- **Graceful no-key mode** so the tool is usable today with zero API spend.
- **Three explicit modes** (ask / draft / brainstorm) rather than one vague "chat".
- **Grounding guardrails** (cite slugs, mark `[inference]`, refuse to invent) — directly enforces the user's standing rule that the advisory council must distinguish direct knowledge from inference.
- **TDD + small commits** so each layer is verifiable independently.
