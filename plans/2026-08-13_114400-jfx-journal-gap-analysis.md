# JFX Journal — Gap Analysis & User-Workflow Improvement Plan

> **Status:** Plan only — no code changed.
> **Sources:** `DOCUMENTATION.md` (1.0.0-beta.1), `DEEP_DIVE.md`, `API_KEYS.md` (draft).

**Goal:** Identify what's missing for users across the whole app and produce a prioritized, actionable list of improvements — each with *what*, *why*, and *effort/impact rating* — that makes the journal more useful and more user-friendly.

**Architecture:** The app is a Supabase-backed React 19 / Vite / TypeScript SPA with analytics, a notebook, AI chat (19 slash commands), an MT5 desktop bridge, and a backtest lab. Everything here is a product/workflow gap analysis and proposed feature set — no execution.

---

## Current Context

### What exists today (strengths)
- Comprehensive analytics: win rate, profit factor, equity, drawdown, symbol/session/psychology breakdowns, comparison, reports, cash tracking.
- Rich notebook with labels, lists, tables, images, trash, Gemini-assisted notes.
- 19 AI slash commands (macro calendar, news, quotes, DCF, filings, earnings, analyst ratings, exchange status).
- MT5 desktop bridge with sync keys, heartbeat, live positions.
- Backtest lab, multi-chart TradingView layouts, playbook/rules.
- Tiered plans (Free/Pro/Premium), offline queue, CSV/PDF exports.

### Known friction / missing pieces (summary preview)
1. No guided onboarding for *what to log* or *how to read* analytics.
2. No anomaly detection — analytics describe but don't *decide*.
3. Journal input is manual-heavy; no quick-capture / prefilled templates.
4. No risk-management guardrails (lot size, max risk, R:R validation).
5. No goals / KPIs / streaks — nothing pulls the trader back.
6. Backtest → live → journal is not a connected pipeline.
7. No external API access for users (addressed by `API_KEYS.md`).
8. No mobile experience, no scheduled review routine.
9. Unowned data export — no full JSON backup / account portability.
10. No alerts (drawdown thresholds, missed session, revenge-trade detection).

---

## Proposed Approach

Three workstreams, in dependency order:

1. **A — Fix existing friction (retention + usability)** — onboard, quick-capture, guided data quality.
2. **B — Add "decide + act" intelligence (perceived value)** — risk guardrails, anomaly alerts, goals, AI review that *produces* a plan, not just prose.
3. **C — Data ownership & ecosystem (growth + recall)** — full-account export, external API (per `API_KEYS.md`), review calendar, mobile PWA.

Each improvement below is bite-sized and independently shippable so the team can execute in order and ship incrementally.

---

## Part A — Fix existing friction (retention + usability)

### A1. 60-second guided onboarding
- **What:** After signup, a 5-screen setup that asks for: account balance, risk % per trade, preferred sessions, top 3 pairs, trading style. Auto-seeds a starter playbook and pre-built analytics defaults. Inline "tour" that teaches one dashboard widget at a time.
- **Why:** Docs say onboarding exists (style/experience/balance) but there's no *tutorial on what to do daily*. New traders abandon because nothing tells them what the screens mean. The documented reading order (DEEP_DIVE lines 531-543) is exactly the tour sequence.
- **Effort:** M — **Impact:** High. This is the top churn lever.

### A2. Quick-capture trade entry (drop the form barrier)
- **What:** A one-tap "+" floating action that opens a *minimal* form: symbol, direction, size, entry, exit, R. That's it. Advanced fields (psychology, mistakes, screenshots) become an optional "expand later" that syncs back into the same trade.
- **Why:** Logging is the #1 daily chore. Today it's a full form (Journal → Log Trade with many fields). High-friction entry = traders skip logging = analytics rot. Speed wins.
- **Effort:** S–M — **Impact:** High.

### A3. Trade templates / prefill from watchlist
- **What:** Save a setup ("guilty pullback EURUSD, 1 lot, 1:2 RR") as a template; one click fills the log form.
- **Why:** Recurring strategies make ~80% of a trader's trades. Prefill cuts entry time and improves tag consistency (better analytics).
- **Effort:** S — **Impact:** Medium.

### A4. Data-quality guardrails on input
- **What:** On save, validate: lot size × stop = max risk vs. account %, R-multiple sanity, mismatched direction vs. P&L sign. Flag "this trade risks 3.2% of your account."
- **Why:** Rubbish in = rubbish analytics. Doc admits cleanup/dedup tools exist (reactively); prevent it at entry instead.
- **Effort:** M — **Impact:** High.

### A5. TradingView trade-marker overlay
- **What:** Plot entry/exit/stop markers onto the user's TradingView charts directly from the journal.
- **Why:** Charts exist but are disconnected from logged trades. Visually seeing "what did my setup look like, did I stick to invalidation?" closes the review loop.
- **Effort:** M — **Impact:** Medium-High.

---

## Part B — Decide + act intelligence (perceived value)

### B1. AI trade review that *produces an action plan*
- **What:** Upgrade AI Chat's trade review (already in docs) from prose to a structured deliverable: verdict (A/B/C grade), 3 concrete "next time" rules, a computed R-risk report, and a button to *insert the rule into the playbook verbatim*.
- **Why:** Today AI "analyzes and helps"; it doesn't change behavior. Turning reflection into editable rules closes the loop and makes the playbook a living artifact instead of a static list.
- **Effort:** M — **Impact:** High.

### B2. Automated anomaly detection ("Journal Doctor")
- **What:** Background job scans new trades and flags: revenge trading (loss → oversized next trade), tilt streaks, session deviation, risk creep, strategy drift. Surfaces via dashboard banner + AI Chat.
- **Why:** The psychology tab *describes* tilt but never says "this just happened, log off." Proactive = differentiated. Reuses existing psychology/mistake data.
- **Effort:** L — **Impact:** High.

### B3. Risk guardrail enforcement
- **What:** A daily risk budget (max loss/day, max trades/day, max size). Soft-block on exceeding. Configurable per user.
- **Why:** Trading journals exist to prevent account blowup. Being the tool that *stops the bad trade* (not just records it) is the single strongest value prop.
- **Effort:** M — **Impact:** Very High.

### B4. Goals, KPIs & streaks
- **What:** User sets weekly goals (e.g. "execute 10 A+ setups, ≤ 1 EMOTIONAL mistake, +2R net"). Dashboard shows progress bars + a 7-day streak.
- **Why:** Genuinely useful habit-forming; drives daily return visits. No tool in this app currently pulls users back on a cadence.
- **Effort:** M — **Impact:** Medium-High.

### B5. Daily/weekly auto-generated review digest
- **What:** Scheduled email or in-app report: "This week you made +3R in NY session on EURUSD, but slipped 4× after lunch." Auto-generated from existing analytics.
- **Why:** Most users won't click through 9 analytics tabs manually. Delivering the summary *to* them drives return + perceived intelligence.
- **Effort:** M — **Impact:** High.

---

## Part C — Data ownership & ecosystem (growth + recall)

### C1. Full-account JSON backup & restore (portability)
- **What:** One-tap export of *everything* (trades, notes, playbook, settings) as JSON; and a matching import/restore. Separate from the per-report CSV/PDF export.
- **Why:** Docs advertise CSV/PDF report export but nothing backs up the whole account. Trust + lock-in reduction. Also enables A7/API round-trips.
- **Effort:** S–M — **Impact:** Medium (low effort, high trust).

### C2. External API access (per `API_KEYS.md`)
- **What:** Ship the scoped PAT system + Edge Function so users can query/write their journal from Claude Code, Hermes, Codex, scripts.
- **Why:** This is the explicit user ask of the session. Enables power/quant workflow, AI-assisted journaling from agents, and integrations. Already designed — build it.
- **Effort:** L — **Impact:** High (differentiator, zero marginal infrastructure).

### C3. Review calendar / scheduled journaling routine
- **What:** A "Review" home tab with a cadence (pre-market scan, post-trade review, end-of-week). Guided checklist, hooks into notebook + AI chat.
- **Why:** Journaling is only valuable when routine. The docs even recommend a reading sequence — formalize it as a scheduled, guided routine.
- **Effort:** M — **Impact:** Medium-High.

### C4. Mobile / PWA
- **What:** Make the app installable (PWA) and pinch-friendly for at least trade entry + dashboard.
- **Why:** Traders often aren't at the desktop when forcing/sizing decisions happen; MT5 bridge is desktop-only, but *viewing* should be pocket-sized.
- **Effort:** L — **Impact:** Medium (broadens reach).

### C5. Broker integration (finish the half-built surface)
- **What:** The Broker section exists but shows "under maintenance." Either ship it (read positions from a broker API and auto-log) or remove it.
- **Why:** A half-built nav item reads as broken to users and erodes trust in the whole app.
- **Effort:** L — **Impact:** Medium.

### C6. Community / shared playbooks (watchlist)
- **What:** Let Premium users publish/import playbooks and setup templates.
- **Why:** Network effects + content marketing. Defer — add only after C1..C5.
- **Effort:** L — **Impact:** Medium (growth later).

---

## Files likely to change (when executed)

| Workstream | Likely targets |
|---|---|
| A1 onboarding | `src/onboarding/`, Welcome tour component, `src/context/OnboardingContext.tsx` |
| A2 quick-capture | `src/components/trade/QuickCapture.tsx`, Dashboard FAB |
| A3 templates | `src/components/trade/Templates.tsx`, add `playbook`/`trade_templates` table |
| A4 guardrails | `src/lib/riskValidation.ts`, trade create/edit form |
| A5 chart markers | `src/components/charts/` TradingView overlay, bridge data |
| B1 AI action plan | `src/ai/` chat handler, playbook mutation |
| B2 anomaly detection | `supabase/functions/journal-doctor/`, dashboard banner |
| B3 risk budget | `src/lib/riskBudget.ts`, `user_settings` table |
| B4 goals/streaks | `src/components/goals/`, `goals` table |
| B5 review digest | `supabase/functions/digest-email/`, cron |
| C1 backup | `supabase/functions/export-account/`, settings UI |
| C2 API | Per `API_KEYS.md`: `api_keys`, `api_key_audit` tables; `supabase/functions/jfx-api/` |
| C3 review calendar | `src/components/review/`, nav item |
| C4 PWA | Vite PWA plugin, manifest, service worker |
| C5 broker | broker adapter, settings UI |
| C6 community | Shared playbook endpoints, GDPR-review on visibility |

---

## Suggested execution order (MVP slice first)

**Wave 1 (retention — do first):** A1, A2, A4 → stop abandonment, clean data.
**Wave 2 (value):** B3, B1, B5 → risk safety + AI that acts + auto-digest.
**Wave 3 (ecosystem):** C2 (API), C1 (backup), C3 (review calendar).
**Wave 4 (growth, optional):** A5, A3, C4, C5, C6.

**Why this order:** Fix the daily chore (A) before adding intelligence (B), and prove data is ownable (C1/C2) before any growth push. Each wave is independently shippable — no forced coupling.

---

## Tests / Validation (when executed)

- A2/A3: entry-time test — new logged trade appears in Analytics within the same session; prefill produces identical fields.
- A4/B3: risk rule unit tests (`riskValidation`, `riskBudget`) — oversized trade is blocked with correct message.
- B1: AI review returns a playbook `INSERT` and the rule appears in Playbook tab.
- B2: fixture trade set triggers exactly one dashboard banner.
- C1: export JSON re-imports to a byte-identical account (round-trip test).
- C2: `curl` with a valid `jfx_pat_*` token returns user-scoped trades; revoked token → 401.

---

## Risks & Open Questions

| Risk | Mitigation |
|---|---|
| Over-engineering early signals (B2) | Ship rules engine on existing trade fields; don't build ML in v1 |
| AI cost on B1/B5 | Batch via cron; token cap per request; only Premium for AI-generated playbook writes |
| PWA vs. native (C4) | Ship PWA first (cheap); native only if retention data justifies |
| External API abuse (C2) | Per-key rate limits + scopes + audit (already in `API_KEYS.md`) |
| Feature overload hurting simplicity | User-profile preference: simple/low-friction. Every feature gets a plan-tier gate |

**Open questions to decide before executing:**
1. Should Free-tier users get API keys / AI review, or is that Premium-only?
2. Is the MT5 desktop bridge (existing) the primary sync path, or should web-first broker sync (C5) take priority?
3. Target audience: retail forex beginners (flows → A4/A5/B1/B3) or advanced quants (flows → C2/B2)? Current docs skew beginner; API skews advanced. Pick the wedge.
4. Is there a real DB/user base to validate against before Wave 2?

---

## Handoff

Ready to execute using **subagent-driven-development** — dispatch one subagent per task in the order above, TDD each, review after every spec + code-quality gate. Start with Wave 1 (A1 → A2 → A4) unless the open questions change the wedge.