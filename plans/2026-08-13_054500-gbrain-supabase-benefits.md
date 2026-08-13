# gbrain + Supabase: Benefits and Migration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Connect the Hermes gbrain second brain to a Supabase Postgres instance, replacing its current local PGLite storage, and enumerate exactly what that unlocks.

**Architecture:** gbrain currently runs in `Mode: local` on **PGLite** (`~/.gbrain/brain.pglite`, embedded single-machine Postgres, schema v122). Supabase provides a **managed Postgres + pgvector + RLS + PostgREST + multi-process workers** backend. The switch is a one-command re-init (`gbrain init --supabase` or `gbrain init --url <conn_string>`) followed by a data migration.

**Tech Stack:** gbrain (bun CLI v0.42.59.0), Supabase (Postgres 15, pgvector, RLS, PostgREST), Transaction pooler (port 6543).

---

## Current State (verified 2026-08-13)

- gbrain `Mode: local`, v0.42.59.0, schema v122 (latest).
- Storage: PGLite at `~/.gbrain/brain.pglite` (embedded, single-writer, single-machine).
- Only 5 pages, embedded 14%, sync never run, no workers.
- Doctor confirms the switch command: `gbrain init --supabase` or `gbrain init --url <connection_string>`.
- Upgrade available: 0.42.59.0 → 0.45.9.0 (`gbrain self-upgrade`).

---

## Benefits of Connecting to Supabase

### 1. Scale past the single-machine ceiling
- **The official trigger:** gbrain's own AGENTS.md says *"For 1000+ files or multi-machine sync, init suggests Postgres + pgvector via Supabase."* — you are at the exact moment where this is recommended.
- PGLite is embedded and single-writer: one process, one box. Supabase gives you a real network Postgres that many processes and machines can query concurrently.
- Schema/vector size stops being a local-disk/CPU concern.

### 2. True multi-machine / multi-agent access
- Every Hermes box (this VPS, your Windows Desktop, any future agent host / cron runner / minion) can address the **same brain** by URL — no copying `brain.pglite` around, no divergence between machines.
- This is the biggest concrete unlock: your brain stops being trapped on this one VPS and becomes reachable from anywhere with the connection string.

### 3. Reliable, auto-retried sync (the "sync did nothing" fix solved)
- gbrain tunes for **Supabase Transaction pooler (port 6543)**. On PGLite there's no pooler, no durable queue, no worker surface.
- With Supabase you get the live-sync path: `gbrain sync --repo <path> && gbrain embed --stale`, cron-able every 15 min or `--watch` (60s) — the index stays current automatically instead of drifting (PGLite currently shows 14% embedded, never synced).

### 4. Managed backups, uptime, and DR
- Supabase = cloud Postgres with automated backups, point-in-time recovery, and high availability — vs. PGLite where the brain dies with the VPS disk (your `/tmp`-ephemeral risk and VPS blow-away risk are real).
- Your daily Hermes profile backup already covers `~/.hermes`, but it does **not** back up `~/.gbrain/brain.pglite` reliably — moving the brain to Supabase removes that single point of loss.

### 5. Row-Level Security (RLS) — controlled sharing
- Supabase exposes tables via PostgREST; RLS gates who can read what. gbrain's service-role connection holds `BYPASSRLS`, so the brain itself stays unconstrained while external apps (Baku, Hermes, cron workers, a future web admin) are strictly scoped.
- PGLite has **no PostgREST exposure and RLS is skipped** (`rls: Skipped (PGLite...)` in doctor) — meaning today you genuinely cannot share the brain on the network securely.

### 6. pgvector similarity search, native + optimized
- PGLite bundles one pgvector version; Supabase runs a managed pgvector with production tuning (2000-dim+ support, HNSW/IVFFlat indexes, GPU-less vector ops). Better retrieval latency at scale.
- Doctor will be able to run `pgvector`, `queue_health`, `oversized_pages`, and worker checks that it currently *skips* on PGLite → health visibility you don't have today.

### 7. Multi-process worker fan-out
- PGLite is single-writer, autopilot fan-out = 1. Supabase surfaces a real `queue_health` + multi-process worker pool, so autopilot / ingestion can parallelize (cron jobs + the worker pool can run concurrently without lock contention).

---

## The Honest Tradeoffs / Costs (read before committing)

- **A key moves off the box.** The brain's contents (your captured knowledge, notes, video summaries) will live in a third party's cloud. Confirm you're comfortable trusting Supabase with that data; the RLS guide is explicit that *everything in `public` is exposed via PostgREST if RLS is off* — gbrain auto-enables it (v0.26.7+), but you should review.
- **IPv4/IPv6 gotcha (the #1 silent failure):** Supabase's **direct** host is **IPv6-only**; on an IPv4-only host, reads work but sync silently skips most pages. Fix: use the **Transaction pooler** host (port 6543, IPv4-compatible) or enable Supabase's IPv4 add-on. Verify after syncing that `gbrain stats` page count matches the repo file count.
- **Multi-machine power = multi-machine attack surface.** More places can read the brain; RLS and the service-role key must be treated as secrets.
- **Cost:** Supabase free tier is generous (500MB DB, 1GB vector storage) but heavy vector workloads can push to paid tiers. For 5 pages you're nowhere near limits.
- **Not a drop-in:** switching storage is one command, but you must re-run `embed` for all content in the new backend (fresh vector index).

---

## Step-by-Step Migration Plan

### Task 1: Create the Supabase project + get connection details
**Files:** none (external).
**Steps:**
1. Create a Supabase project (supabase.com → New Project).
2. Under Database → Connection string / pooler, capture:
   - **Transaction pooler** string `postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres` (IPv4-safe, preferred)
   - **Direct** string `postgresql://postgres.<ref>:<pw>@db.<ref>.supabase.co:5432/postgres` (IPv6-only; only use if host has IPv6).
3. Enable the **Vector** extension in the Supabase dashboard.
**Verify:** You can `psql` or curl-ping the pooler from this VPS (confirm IPv4 reachability before proceeding).

### Task 2: Back up the current PGLite brain
**Files:** backup copy of `~/.gbrain/brain.pglite`.
**Step 1:** `cp -r ~/.gbrain/brain.pglite ~/.gbrain/brain.pglite.bak.pre-supabase` (there is already a `.bak`; make a clean pre-migration snapshot).
**Verify:** `ls -la ~/.gbrain/brain.pglite.bak.pre-supabase` exists and is non-empty.

### Task 3: Re-init gbrain to Supabase
**Files:** `~/.gbrain/config.json` (rewritten by the CLI, not by hand).
**Step 1:** Run, using the Transaction pooler URL:
```bash
export PATH="$HOME/.bun/bin:$PATH"; cd /root/gbrain
gbrain init --supabase --url "postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:6543/postgres"
```
**Verify:** `gbrain doctor` → `pgvector: [OK]`, `schema_version: <latest>`, no more `oversized_pages`/`queue_health` "Skipped (No database connection)".

### Task 4: Migrate content + rebuild embeddings
**Files:** none (data operation in the new DB).
**Step 1:** Re-embed all content against the new backend:
```bash
gbrain embed && gbrain synccheck
```
If the brain repo lives at a path, chain it (from live-sync guide):
```bash
gbrain sync --repo /data/brain && gbrain embed --stale
```
**Verify (critical — catches the IPv6 sync trap):** `gbrain stats` page count **must equal** the syncable file count in the repo. If it's far lower, the connection fell back to the IPv6 direct host — switch to the pooler or add IPv4.

### Task 5: Verify search end-to-end + Hermes integration
**Files:** `~/.hermes/plugins/gbrain/` (Hermes memory-provider plugin — confirm it still resolves).
**Step 1:** Sanity-retrieve: `gbrain search "<a term you captured>"` → returns results.
**Step 2:** Confirm the Hermes memory provider still works (it shells to `gbrain`; verify a `gbrain query` returns the same shape as before — the plugin reads the CLI, not the storage backend, so this should be transparent).
**Verify:** `gbrain search` returns rows from the Supabase-backed brain, and Hermes memory/retrieval behaves identically.

### Task 6: Set up live sync (optional but recommended)
**Files:** Hermes cron job (or system cron).
**Step 1:** Add a cron job running `gbrain sync --repo <brain-path> && gbrain embed --stale` every 15 minutes (or `--watch` for 60s polling) so the index auto-updates.
**Verify:** After pushing a change to the brain repo, `gbrain search` finds it within the sync window without manual `sync`.

### Task 7: (Optional) Upgrade gbrain 0.42.59.0 → 0.45.9.0
**Files:** gbrain binary + migrations.
**Step 1:** `gbrain self-upgrade` — do this **after** the Supabase switch so schema migrations run against the new backend; follow any `[AGENT]` post-upgrade prompts (search-mode cost matrix) per AGENTS.md.
**Caution (memory rule):** earlier note said don't auto-run the upgrade because it may change CLI output. Do it as an explicit, user-approved step, and re-run Task 5 verification after.

---

## Files That Change
- `~/.gbrain/config.json` — storage backend re-pointed to Supabase (CLI-managed).
- `~/.gbrain/brain.pglite` — becomes a stale local copy (keep the `.bak`); brain-of-record moves to Supabase.
- Hermes `~/.hermes/plugins/gbrain/` — no code change expected (it shells to the gbrain CLI), verify only.
- New cron job (Task 6) for live sync.

## Risks, Tradeoffs & Open Questions
- **Data leaves the box** → Supabase cloud. Confirm comfort + review RLS (auto-on since v0.26.7).
- **IPv6 direct-host sync trap** → use Transaction pooler (port 6543) or IPv4 add-on; verify page counts.
- **Re-embed cost** → all vectors rebuilt in the new backend (small today: 5 pages).
- **Cost tier** → free tier ample for current scale.
- **Open: which Supabase region?** Matters for latency to this VPS and for IPv4 availability — pick the region closest to the box, and confirm IPv4/pooler before wiring anything sensitive.
- **Open: do you actually need multi-machine access?** If the brain will only ever live on this one VPS, the sync/backup/scale benefits still justify Supabase, but the multi-machine angle is the one to weigh hardest.

---

## Quick Decision Summary

| Concern | PGLite (today) | Supabase |
|---|---|---|
| Scale | 1 machine, single-writer | Multi-machine, multi-process |
| Access from other boxes | ❌ boxed to VPS | ✅ anywhere |
| Backups / DR | ❌ none reliable | ✅ managed + PITR |
| Network sharing | ❌ no PostgREST/RLS | ✅ RLS-scoped |
| Live sync / queue | ❌ none (14% embedded) | ✅ pooler + cron-able |
| Vector ops | bundled pgvector | managed, tuned |

**Recommendation:** For your current scale (5 pages) Supabase is not *required*, but it is the documented step-up for exactly the reasons you care about — **durability (the brain currently survives only as long as this VPS), live sync, and future multi-machine access.** Proceed if you want the brain to survive a box failure; skip if content must never leave this machine.